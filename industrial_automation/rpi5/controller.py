"""
controller.py — Closed-loop control state machine for the RPi5.

State diagram:
                ┌──────────┐
         ┌──────►  IDLE    ├──── object detected ──►┐
         │      └──────────┘                        │
         │                                          ▼
         │      ┌──────────┐                ┌──────────────┐
         └──────┤ RELEASING│◄─ grip done ───┤   GRIPPING   │
                └──────────┘                └──────────────┘

The loop runs every POLL_INTERVAL_S seconds.
"""

import time
import logging
from enum import Enum, auto

from sensors    import object_present
from spi_master import SPIMaster, RSP_GRIPPING, RSP_RELEASING, RSP_ERROR

logger = logging.getLogger(__name__)

# How often the control loop polls sensors and gripper status (seconds)
POLL_INTERVAL_S       = 0.1

# How long to wait for the Nucleo to confirm a state transition (seconds)
TRANSITION_TIMEOUT_S  = 3.0

# Minimum time (seconds) to hold the gripper closed before releasing.
# Prevents an immediate release when RSP_GRIPPING is seen at the first poll.
GRIP_DWELL_S = 0.5


class State(Enum):
    IDLE      = auto()
    GRIPPING  = auto()
    RELEASING = auto()


class Controller:
    """Closed-loop controller: sense → decide → actuate → verify."""

    def __init__(self, spi: SPIMaster):
        self._spi   = spi
        self._state = State.IDLE
        self._t0    = 0.0        # timestamp of last state transition

    # ---------------------------------------------------------------------- #
    # Public interface
    # ---------------------------------------------------------------------- #
    def run(self):
        """Blocking control loop. Exits on KeyboardInterrupt."""
        logger.info("Controller started — entering IDLE state.")
        try:
            while True:
                self._tick()
                time.sleep(POLL_INTERVAL_S)
        except KeyboardInterrupt:
            logger.info("Shutdown requested. Sending RELEASE before exit.")
            self._spi.send_release()

    # ---------------------------------------------------------------------- #
    # Internal state machine
    # ---------------------------------------------------------------------- #
    def _tick(self):
        if self._state == State.IDLE:
            self._handle_idle()
        elif self._state == State.GRIPPING:
            self._handle_gripping()
        elif self._state == State.RELEASING:
            self._handle_releasing()

    def _handle_idle(self):
        if object_present():
            logger.info("Object detected — sending GRIP command.")
            rsp = self._spi.send_grip()
            # send_grip() now returns the actual IO-Link result:
            #   RSP_GRIPPING (0x01) — IO-Link cycle succeeded, gripper closing
            #   RSP_ERROR    (0xFF) — IO-Link timeout or CRC failure
            #   RSP_IDLE     (0x00) — unexpected but non-fatal; retry next tick
            if rsp == RSP_ERROR:
                logger.error("Nucleo reported error on GRIP command (0x%02X).", rsp)
            else:
                logger.info("GRIP command accepted (Nucleo RSP=0x%02X).", rsp)
                self._transition(State.GRIPPING)

    def _handle_gripping(self):
        # Use request_status() which sends 0x00 — Nucleo ignores it and returns
        # the last spi_tx_byte without triggering a new IO-Link cycle.  This
        # avoids the CMD_STATUS side-effect of sending IOLINK_PD_RELEASE over
        # IO-Link while the gripper is still closing.
        rsp = self._spi.request_status()
        logger.debug("GRIPPING — Nucleo status: 0x%02X", rsp)

        if rsp == RSP_GRIPPING:
            # Only release after the minimum dwell time has elapsed.
            if (time.time() - self._t0) < GRIP_DWELL_S:
                return
            logger.info("Gripper closed — object gripped. Sending RELEASE.")
            release_rsp = self._spi.send_release()
            if release_rsp == RSP_ERROR:
                logger.error("Nucleo reported error on RELEASE command.")
            else:
                self._transition(State.RELEASING)
        elif rsp == RSP_ERROR:
            logger.error("Nucleo error while gripping. Returning to IDLE.")
            self._transition(State.IDLE)
        elif self._timed_out():
            logger.warning("Grip transition timeout. Returning to IDLE.")
            self._spi.send_release()
            self._transition(State.IDLE)

    def _handle_releasing(self):
        rsp = self._spi.request_status()
        logger.debug("RELEASING — Nucleo status: 0x%02X", rsp)

        if rsp == RSP_RELEASING:
            logger.info("Gripper opened — cycle complete. Returning to IDLE.")
            self._transition(State.IDLE)
        elif rsp == RSP_ERROR:
            logger.error("Nucleo error while releasing. Returning to IDLE.")
            self._transition(State.IDLE)
        elif self._timed_out():
            logger.warning("Release transition timeout. Returning to IDLE.")
            self._transition(State.IDLE)

    # ---------------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------------- #
    def _transition(self, new_state: State):
        logger.info("State: %s → %s", self._state.name, new_state.name)
        self._state = new_state
        self._t0    = time.time()

    def _timed_out(self) -> bool:
        return (time.time() - self._t0) > TRANSITION_TIMEOUT_S
