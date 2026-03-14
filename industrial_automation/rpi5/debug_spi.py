#!/usr/bin/env python3
"""
debug_spi.py — Step-by-step SPI + gripper diagnostic for the RPi5.

Tests the full chain: RPi5 → SPI → NUCLEO-F746ZG → IO-Link → Zimmer LWR50L-02

Run with:
    sudo python3 debug_spi.py

Stages:
  1. SPI connectivity — send 0x00 bytes, verify Nucleo responds (not all 0x00)
  2. Raw command test  — send each command byte, log raw response
  3. Double-transfer   — send CMD_GRIP + 0x00 follow-up, check result
  4. Grip/release cycle — full GRIP → wait → RELEASE sequence
  5. Poll loop         — continuous status poll for 5 s, showing all responses

Protocol notes:
  - Nucleo SPI slave pre-loads spi_tx_byte BEFORE the transfer, so the response
    to command N only arrives on transaction N+1.
  - Nucleo ignores 0x00 bytes (explicitly handled in app.c) and re-arms with
    the same spi_tx_byte — safe to use as a "read result" byte.
  - CMD_STATUS (0x03) runs iolink_cycle(RELEASE) internally — avoid while
    gripping to prevent an unintended IO-Link RELEASE during grip.
"""

import spidev
import time
import sys

# --------------------------------------------------------------------------- #
# SPI setup
# --------------------------------------------------------------------------- #
SPI_BUS       = 0
SPI_DEVICE    = 0
SPI_SPEED     = 1_000_000
SPI_MODE      = 0

SETUP_DELAY   = 0.000010   # 10 µs inter-transfer setup delay
IOLINK_CYCLE  = 0.020      # 20 ms: covers worst-case IO-Link timeout (10 ms HAL
                            # timeout + echo-flush + HAL overhead)

# --------------------------------------------------------------------------- #
# Protocol constants (must match Nucleo app.c / iolink.h)
# --------------------------------------------------------------------------- #
CMD_GRIP    = 0x01
CMD_RELEASE = 0x02
CMD_STATUS  = 0x03

RSP_IDLE      = 0x00
RSP_GRIPPING  = 0x01
RSP_RELEASING = 0x02
RSP_ERROR     = 0xFF

RSP_NAMES = {
    RSP_IDLE:      "RSP_IDLE      (0x00) — idle / no confirmed state",
    RSP_GRIPPING:  "RSP_GRIPPING  (0x01) — IO-Link GRIP cycle succeeded",
    RSP_RELEASING: "RSP_RELEASING (0x02) — IO-Link RELEASE cycle succeeded",
    RSP_ERROR:     "RSP_ERROR     (0xFF) — IO-Link timeout or CRC failure",
}


# --------------------------------------------------------------------------- #
# Low-level SPI helpers
# --------------------------------------------------------------------------- #
def xfr(spi: spidev.SpiDev, byte: int) -> int:
    time.sleep(SETUP_DELAY)
    return spi.xfer2([byte & 0xFF])[0]


def send_cmd(spi: spidev.SpiDev, cmd: int, label: str) -> int:
    """Send a command, wait for IO-Link cycle, read result via 0x00."""
    stale = xfr(spi, cmd)
    time.sleep(IOLINK_CYCLE)
    result = xfr(spi, 0x00)
    print(f"  TX: 0x{cmd:02X} ({label})")
    print(f"    stale response (ignored): 0x{stale:02X}")
    print(f"    actual result           : 0x{result:02X}  {RSP_NAMES.get(result, '???')}")
    return result


def read_status(spi: spidev.SpiDev) -> int:
    """Read current spi_tx_byte without triggering IO-Link (send 0x00)."""
    return xfr(spi, 0x00)


# --------------------------------------------------------------------------- #
# Diagnostic stages
# --------------------------------------------------------------------------- #
def stage1_connectivity(spi: spidev.SpiDev) -> bool:
    print("\n" + "="*60)
    print("STAGE 1: SPI connectivity (send 0x00 × 5)")
    print("="*60)
    print("  Sending 5 × 0x00 (Nucleo ignores these, returns spi_tx_byte).")
    print("  Expected: 0x00 (RSP_IDLE) if Nucleo just booted, or last cmd result.")
    responses = []
    for i in range(5):
        r = xfr(spi, 0x00)
        responses.append(r)
        print(f"  [{i+1}] TX 0x00 → RX 0x{r:02X}")
        time.sleep(0.01)

    # PASS: we got at least one non-garbage response (SPI lines connected)
    # There's no solid "correct" value, but all-0xFF or all-0x00-stuck suggests wiring issues
    unique = set(responses)
    if len(unique) == 1 and 0xFF in unique:
        print("  ⚠ All responses were 0xFF — MISO may be floating HIGH or Nucleo not running.")
        return False
    print(f"  ✓ SPI appears responsive (responses: {[hex(r) for r in responses]})")
    return True


def stage2_raw_commands(spi: spidev.SpiDev):
    print("\n" + "="*60)
    print("STAGE 2: Raw single-transfer responses (stale by design)")
    print("="*60)
    print("  These show the PRE-LOADED response, not the result of the command.")
    cmds = [(0x00, "dummy"), (CMD_STATUS, "CMD_STATUS"), (0x00, "dummy after STATUS")]
    for byte, label in cmds:
        r = xfr(spi, byte)
        print(f"  TX: 0x{byte:02X} ({label}) → RX: 0x{r:02X} {RSP_NAMES.get(r,'')}")
        time.sleep(0.005)


def stage3_grip(spi: spidev.SpiDev) -> int:
    print("\n" + "="*60)
    print("STAGE 3: CMD_GRIP with double-transfer (fixed protocol)")
    print("="*60)
    print("  Sending CMD_GRIP, sleeping 20ms for IO-Link cycle, reading result.")
    result = send_cmd(spi, CMD_GRIP, "CMD_GRIP")
    if result == RSP_GRIPPING:
        print("  ✓ GRIP accepted — IO-Link cycle to gripper succeeded.")
    elif result == RSP_ERROR:
        print("  ✗ GRIP returned RSP_ERROR — IO-Link timeout or CRC.")
        print("    Check: UART4 wiring, TIOL221EVM EN/WAKE pins, 24V supply to gripper.")
    elif result == RSP_IDLE:
        print("  ⚠ GRIP returned RSP_IDLE — Nucleo may not be running app_init().")
    return result


def stage4_release(spi: spidev.SpiDev) -> int:
    print("\n" + "="*60)
    print("STAGE 4: CMD_RELEASE with double-transfer")
    print("="*60)
    result = send_cmd(spi, CMD_RELEASE, "CMD_RELEASE")
    if result == RSP_RELEASING:
        print("  ✓ RELEASE accepted — IO-Link cycle to gripper succeeded.")
    elif result == RSP_ERROR:
        print("  ✗ RELEASE returned RSP_ERROR — IO-Link timeout or CRC.")
    return result


def stage5_full_cycle(spi: spidev.SpiDev):
    print("\n" + "="*60)
    print("STAGE 5: Full grip → dwell → release cycle")
    print("="*60)

    print("\n  [1/4] Sending RELEASE first to ensure known open state...")
    r = send_cmd(spi, CMD_RELEASE, "CMD_RELEASE (init)")
    time.sleep(0.5)

    print("\n  [2/4] Sending GRIP...")
    r = send_cmd(spi, CMD_GRIP, "CMD_GRIP")
    if r == RSP_ERROR:
        print("  ✗ Aborting — GRIP failed.")
        return

    print("\n  [3/4] Holding grip for 1.0 s (gripper should be closed)...")
    for i in range(10):
        time.sleep(0.1)
        s = read_status(spi)
        print(f"    [{i*100}ms] status: 0x{s:02X} {RSP_NAMES.get(s,'')}")

    print("\n  [4/4] Sending RELEASE...")
    r = send_cmd(spi, CMD_RELEASE, "CMD_RELEASE")
    if r == RSP_RELEASING:
        print("  ✓ Full cycle complete — gripper opened.")
    else:
        print(f"  ⚠ RELEASE result: 0x{r:02X}")


def stage6_poll(spi: spidev.SpiDev, duration_s: float = 5.0):
    print("\n" + "="*60)
    print(f"STAGE 6: Continuous status poll for {duration_s:.0f} s")
    print("="*60)
    print("  Sending 0x00 every 100ms — no IO-Link side effects.")
    deadline = time.time() + duration_s
    prev = None
    while time.time() < deadline:
        s = read_status(spi)
        if s != prev:
            print(f"  Status changed → 0x{s:02X}  {RSP_NAMES.get(s,'???')}")
            prev = s
        time.sleep(0.1)
    print("  Poll complete.")


# --------------------------------------------------------------------------- #
# Summary helper
# --------------------------------------------------------------------------- #
PASS_FAIL = {True: "PASS", False: "FAIL"}

def summary(results: dict):
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for stage, ok in results.items():
        mark = "✓" if ok else "✗"
        print(f"  {mark} {stage}: {PASS_FAIL[ok]}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    print("=== RPi5 → Nucleo → IO-Link SPI Diagnostic ===")
    print(f"SPI: bus={SPI_BUS} device={SPI_DEVICE} speed={SPI_SPEED//1000}kHz mode={SPI_MODE}")

    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEVICE)
    spi.max_speed_hz = SPI_SPEED
    spi.mode = SPI_MODE

    results = {}

    try:
        ok = stage1_connectivity(spi)
        results["Stage 1 — SPI connectivity"] = ok
        if not ok:
            print("\n  SPI layer failed — stopping early. Check wiring.")
            return

        stage2_raw_commands(spi)

        grip_result = stage3_grip(spi)
        results["Stage 3 — CMD_GRIP"] = (grip_result == RSP_GRIPPING)

        time.sleep(0.5)
        release_result = stage4_release(spi)
        results["Stage 4 — CMD_RELEASE"] = (release_result == RSP_RELEASING)

        time.sleep(0.5)
        stage5_full_cycle(spi)
        results["Stage 5 — Full cycle"] = True  # manual inspection

        stage6_poll(spi, duration_s=3.0)

    except KeyboardInterrupt:
        print("\n\nInterrupted — sending RELEASE for safety.")
        send_cmd(spi, CMD_RELEASE, "CMD_RELEASE (safety)")
    finally:
        spi.close()
        print("\nSPI closed.")

    summary(results)

    if all(results.values()):
        print("\nAll stages passed. Run the main controller:")
        print("  sudo python3 main.py")
    else:
        print("\nSome stages failed. Likely causes:")
        if not results.get("Stage 3 — CMD_GRIP"):
            print("  - RSP_ERROR: IO-Link physical layer issue")
            print("    → Check UART4 TX/RX wiring, TIOL221EVM 24V supply, EN/WAKE pins")
            print("    → Verify NUCLEO firmware flash includes app.c + iolink.c fixes")
        if not results.get("Stage 1 — SPI connectivity"):
            print("  - SPI: check MOSI/MISO/SCLK/CS wiring")


if __name__ == "__main__":
    main()
