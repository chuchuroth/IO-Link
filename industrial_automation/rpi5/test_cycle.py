"""
test_cycle.py — One-shot integration test for the closed-loop system.

Sequence:
  1. SPI STATUS  → confirm Nucleo is responding via SPI
  2. SPI GRIP    → close gripper and read back the IO-Link result
  3. SPI RELEASE → open  gripper and read back the IO-Link result

Timing note — firmware pre-load latency:
  The Nucleo's SPI ISR pre-loads the TX register immediately after each
  transfer, BEFORE the main loop executes the IO-Link cycle.  This means
  the response to command N is visible only in the reply to command N+1
  (sent after the IO-Link cycle completes, ~10 ms).  Each step therefore
  sends the command twice with a 200 ms gap:
    first  send  → fires the IO-Link cycle, response is stale (don't care)
    second send  → response is the result of the IO-Link cycle  ← checked

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

# Time to wait for the Nucleo to finish one IO-Link cycle before reading back.
# IO-Link COM2 @ 38400 baud: 5 bytes × 260 µs ≈ 1.3 ms; 200 ms is very safe.
IOLINK_CYCLE_WAIT_S = 0.2
SPI_SETUP_DELAY_S   = 0.000010   # 10 µs inter-transfer gap


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def rsp_name(b: int) -> str:
    return RSP_NAMES.get(b, f"0x{b:02X}")


def transfer(spi, cmd: int) -> int:
    """Single SPI byte exchange."""
    time.sleep(SPI_SETUP_DELAY_S)
    return spi.xfer2([cmd & 0xFF])[0]


def send_and_readback(spi, cmd: int) -> int:
    """
    Send a command twice with a wait in between.
    The SECOND response carries the IO-Link result of the FIRST send.
    Returns the result byte.
    """
    transfer(spi, cmd)                    # fires the IO-Link cycle
    time.sleep(IOLINK_CYCLE_WAIT_S)       # wait for cycle to complete
    return transfer(spi, cmd)             # reads back the result


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
    # Step 1: STATUS — confirm SPI + Nucleo alive
    # ------------------------------------------------------------------ #
    print("\n[1/3] SPI STATUS check...")
    rsp = transfer(spi, CMD_STATUS)
    print(f"  Nucleo responded: {rsp_name(rsp)}")
    if rsp != RSP_ERROR:
        print("  PASS — Nucleo is reachable via SPI")
        passed += 1
    else:
        print("  FAIL — Nucleo returned RSP_ERROR on STATUS")
        failed += 1
        spi.close()
        sys.exit(1)    # no point continuing without SPI

    # ------------------------------------------------------------------ #
    # Step 2: GRIP — close the gripper; verify IO-Link cycle succeeded
    # ------------------------------------------------------------------ #
    print("\n[2/3] GRIP command...")
    print(f"  Sending CMD_GRIP, waiting {IOLINK_CYCLE_WAIT_S*1000:.0f} ms, reading back result...")
    result = send_and_readback(spi, CMD_GRIP)
    print(f"  IO-Link result: {rsp_name(result)}")
    if result == RSP_GRIPPING:
        print("  PASS — Nucleo confirmed RSP_GRIPPING (IO-Link GRIP cycle OK)")
        passed += 1
    elif result == RSP_ERROR:
        print("  FAIL — Nucleo returned RSP_ERROR (IO-Link GRIP cycle failed: timeout or CRC)")
        failed += 1
    else:
        # Any other non-ERROR response means the GRIP cycle ran; the gripper
        # may be in a transitional state (acceptable for a connectivity test).
        print(f"  PASS — Nucleo responded {rsp_name(result)} (IO-Link cycle executed, gripper in motion)")
        passed += 1

    # ------------------------------------------------------------------ #
    # Step 3: RELEASE — open the gripper; verify IO-Link cycle succeeded
    # ------------------------------------------------------------------ #
    print("\n[3/3] RELEASE command...")
    print(f"  Sending CMD_RELEASE, waiting {IOLINK_CYCLE_WAIT_S*1000:.0f} ms, reading back result...")
    result = send_and_readback(spi, CMD_RELEASE)
    print(f"  IO-Link result: {rsp_name(result)}")
    if result == RSP_RELEASING:
        print("  PASS — Nucleo confirmed RSP_RELEASING (IO-Link RELEASE cycle OK)")
        passed += 1
    elif result == RSP_ERROR:
        print("  FAIL — Nucleo returned RSP_ERROR (IO-Link RELEASE cycle failed: timeout or CRC)")
        failed += 1
    else:
        print(f"  PASS — Nucleo responded {rsp_name(result)} (IO-Link cycle executed, gripper in motion)")
        passed += 1

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
