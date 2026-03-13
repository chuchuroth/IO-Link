"""
test_cycle.py — One-shot integration test for the closed-loop system.

Sequence:
  1. SPI STATUS  → confirm Nucleo is responding
  2. SPI GRIP    → command gripper to close; poll until RSP_GRIPPING
  3. SPI RELEASE → command gripper to open;  poll until RSP_RELEASING
  4. Print pass/fail summary

Run:  sudo python3 test_cycle.py
"""

import time
import sys

import spidev

# --------------------------------------------------------------------------- #
# Constants (must match spi_master.py / main.h)
# --------------------------------------------------------------------------- #
CMD_GRIP    = 0x01
CMD_RELEASE = 0x02
CMD_STATUS  = 0x03

RSP_IDLE      = 0x00
RSP_GRIPPING  = 0x01
RSP_RELEASING = 0x02
RSP_ERROR     = 0xFF

RSP_NAMES = {
    RSP_IDLE:      "IDLE",
    RSP_GRIPPING:  "GRIPPING",
    RSP_RELEASING: "RELEASING",
    RSP_ERROR:     "ERROR",
}

POLL_INTERVAL_S  = 0.1
POLL_TIMEOUT_S   = 5.0
SPI_SETUP_DELAY  = 0.000010   # 10 µs

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def rsp_name(b):
    return RSP_NAMES.get(b, f"0x{b:02X}")

def transfer(spi, cmd):
    time.sleep(SPI_SETUP_DELAY)
    return spi.xfer2([cmd])[0]

def poll_for(spi, expected, timeout=POLL_TIMEOUT_S):
    """Send CMD_STATUS repeatedly until expected response or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        rsp = transfer(spi, CMD_STATUS)
        print(f"    status → {rsp_name(rsp)}")
        if rsp == expected:
            return True
        if rsp == RSP_ERROR:
            print("    [!] Nucleo reported ERROR")
            return False
        time.sleep(POLL_INTERVAL_S)
    return False

# --------------------------------------------------------------------------- #
# Test
# --------------------------------------------------------------------------- #
def main():
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1_000_000
    spi.mode = 0

    passed = 0
    failed = 0

    # ------------------------------------------------------------------ #
    # Step 1: STATUS — confirm Nucleo is alive
    # ------------------------------------------------------------------ #
    print("\n[1/3] STATUS check...")
    rsp = transfer(spi, CMD_STATUS)
    print(f"  Nucleo responded: {rsp_name(rsp)}")
    if rsp != RSP_ERROR:
        print("  PASS — Nucleo is reachable via SPI")
        passed += 1
    else:
        print("  FAIL — Nucleo returned ERROR")
        failed += 1

    # ------------------------------------------------------------------ #
    # Step 2: GRIP — close the gripper
    # ------------------------------------------------------------------ #
    print("\n[2/3] GRIP command...")
    rsp = transfer(spi, CMD_GRIP)
    print(f"  Immediate response: {rsp_name(rsp)}  (expected IDLE — Nucleo pre-loads previous state)")
    # Give Nucleo time to complete the IO-Link cycle (~2 ms) before polling
    time.sleep(0.05)
    print(f"  Polling for RSP_GRIPPING (timeout {POLL_TIMEOUT_S}s)...")
    if poll_for(spi, RSP_GRIPPING):
        print("  PASS — Gripper confirmed GRIPPING")
        passed += 1
    else:
        print("  FAIL — Gripper did not confirm GRIPPING within timeout")
        failed += 1

    # ------------------------------------------------------------------ #
    # Step 3: RELEASE — open the gripper
    # ------------------------------------------------------------------ #
    print("\n[3/3] RELEASE command...")
    rsp = transfer(spi, CMD_RELEASE)
    print(f"  Immediate response: {rsp_name(rsp)}  (expected GRIPPING — Nucleo pre-loads previous state)")
    time.sleep(0.05)
    print(f"  Polling for RSP_RELEASING (timeout {POLL_TIMEOUT_S}s)...")
    if poll_for(spi, RSP_RELEASING):
        print("  PASS — Gripper confirmed RELEASING")
        passed += 1
    else:
        print("  FAIL — Gripper did not confirm RELEASING within timeout")
        failed += 1

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    spi.close()
    print(f"\n{'='*40}")
    print(f"Result: {passed}/3 passed, {failed} failed")
    print('='*40)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
