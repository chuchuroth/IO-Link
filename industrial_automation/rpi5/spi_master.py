"""
spi_master.py — SPI master driver for RPi5 → NUCLEO-F746ZG communication.

Hardware mapping (from pin_mapping.md §1):
  MOSI  GPIO 10 (Pin 19) ↔ PA7
  MISO  GPIO  9 (Pin 21) ↔ PA6
  SCLK  GPIO 11 (Pin 23) ↔ PA5
  CS    GPIO  8 (Pin 24) ↔ PA4

SPI framing (1-byte command / 1-byte response):
  Commands (RPi5 → Nucleo):
    CMD_GRIP    = 0x01
    CMD_RELEASE = 0x02
    CMD_STATUS  = 0x03

  Responses (Nucleo → RPi5):
    RSP_IDLE      = 0x00
    RSP_GRIPPING  = 0x01
    RSP_RELEASING = 0x02
    RSP_ERROR     = 0xFF
"""

import spidev
import time

# --------------------------------------------------------------------------- #
# Command / response constants  (shared with Nucleo firmware)
# --------------------------------------------------------------------------- #
CMD_GRIP    = 0x01
CMD_RELEASE = 0x02
CMD_STATUS  = 0x03

RSP_IDLE      = 0x00
RSP_GRIPPING  = 0x01
RSP_RELEASING = 0x02
RSP_ERROR     = 0xFF

# --------------------------------------------------------------------------- #
# SPI bus parameters
# --------------------------------------------------------------------------- #
SPI_BUS         = 0       # /dev/spidev0.x
SPI_DEVICE      = 0       # CE0 → GPIO 8
SPI_MAX_SPEED   = 1_000_000  # 1 MHz — conservative for long wires
SPI_MODE        = 0       # CPOL=0, CPHA=0

# Delay after asserting CS before transfer (µs → s)
_SETUP_DELAY_S = 0.000010   # 10 µs — give Nucleo SPI slave time to prepare

# Time to wait after sending a command for the Nucleo to complete one IO-Link
# cycle (echo-flush + device response at 38400 baud, worst-case 10 ms HAL
# timeout + HAL overhead → use 20 ms).
_IOLINK_CYCLE_S = 0.020


class SPIMaster:
    """Thin wrapper around spidev for command/response exchange with the Nucleo."""

    def __init__(self):
        self._spi = spidev.SpiDev()
        self._spi.open(SPI_BUS, SPI_DEVICE)
        self._spi.max_speed_hz = SPI_MAX_SPEED
        self._spi.mode = SPI_MODE

    def close(self):
        self._spi.close()

    def _transfer(self, command: int) -> int:
        """Send one byte and return the simultaneously received response byte."""
        time.sleep(_SETUP_DELAY_S)
        result = self._spi.xfer2([command & 0xFF])
        return result[0]

    def _read_response(self) -> int:
        """Read the response pre-loaded by the last command.

        The Nucleo SPI slave pre-loads spi_tx_byte *before* each transfer, so
        the result of processing command N only becomes available on transfer
        N+1.  Sending 0x00 is safe: the Nucleo explicitly ignores 0x00 bytes
        and re-arms with the same spi_tx_byte unchanged.

        Caller must have already waited _IOLINK_CYCLE_S for the IO-Link cycle
        to complete before calling this.
        """
        return self._transfer(0x00)

    # ---------------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------------- #
    def send_grip(self) -> int:
        """Command the Nucleo to close the gripper.

        Sends CMD_GRIP, waits for the IO-Link cycle to complete, then reads
        the actual result via a dummy 0x00 transfer.
        Returns RSP_GRIPPING on success, RSP_ERROR on IO-Link failure.
        """
        self._transfer(CMD_GRIP)       # send command; returned byte is stale
        time.sleep(_IOLINK_CYCLE_S)    # wait for IO-Link cycle
        return self._read_response()   # returns result of CMD_GRIP

    def send_release(self) -> int:
        """Command the Nucleo to open the gripper.

        Sends CMD_RELEASE, waits for IO-Link cycle, reads actual result.
        Returns RSP_RELEASING on success, RSP_ERROR on IO-Link failure.
        """
        self._transfer(CMD_RELEASE)
        time.sleep(_IOLINK_CYCLE_S)
        return self._read_response()

    def request_status(self) -> int:
        """Read current gripper status without triggering a new IO-Link cycle.

        Sends 0x00 (ignored by Nucleo) and returns whatever spi_tx_byte was
        pre-loaded from the last completed command.  Does NOT run iolink_cycle,
        so repeated calls do not interfere with the gripper's motion state.
        """
        return self._transfer(0x00)
