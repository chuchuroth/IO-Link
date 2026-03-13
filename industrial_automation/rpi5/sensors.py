"""
sensors.py — HC-SR04 ultrasonic and HC-SR501 PIR sensor drivers.

Pin mapping (from pin_mapping.md §4):
  HC-SR04: Trig → GPIO 23, Echo → GPIO 24 (3.3 V via voltage divider)
  HC-SR501: Out  → GPIO 25
"""

import time
import RPi.GPIO as GPIO

# --------------------------------------------------------------------------- #
# GPIO pin numbers (BCM numbering)
# --------------------------------------------------------------------------- #
TRIG_PIN  = 23
ECHO_PIN  = 24
PIR_PIN   = 25

# HC-SR04 constants
SOUND_SPEED_CM_PER_S = 34300.0          # cm/s at ~20 °C
TRIGGER_PULSE_S      = 0.00001          # 10 µs trigger pulse
ECHO_TIMEOUT_S       = 0.04             # 40 ms → max ~680 cm range
OBJECT_THRESHOLD_CM  = 30.0             # detect objects closer than 30 cm


def setup():
    """Initialise GPIO. Call once at startup."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    GPIO.setup(PIR_PIN,  GPIO.IN)


def cleanup():
    """Release GPIO resources. Call at shutdown."""
    GPIO.cleanup()


# --------------------------------------------------------------------------- #
# HC-SR04 — ultrasonic distance sensor
# --------------------------------------------------------------------------- #
def read_distance_cm() -> float | None:
    """
    Trigger one ultrasonic measurement and return distance in centimetres.
    Returns None on timeout (no echo received within ECHO_TIMEOUT_S).
    """
    # Send 10 µs trigger pulse
    GPIO.output(TRIG_PIN, GPIO.HIGH)
    time.sleep(TRIGGER_PULSE_S)
    GPIO.output(TRIG_PIN, GPIO.LOW)

    # Wait for echo to go HIGH (pulse start)
    deadline = time.time() + ECHO_TIMEOUT_S
    while GPIO.input(ECHO_PIN) == GPIO.LOW:
        if time.time() > deadline:
            return None
    pulse_start = time.time()

    # Wait for echo to go LOW (pulse end)
    deadline = time.time() + ECHO_TIMEOUT_S
    while GPIO.input(ECHO_PIN) == GPIO.HIGH:
        if time.time() > deadline:
            return None
    pulse_end = time.time()

    elapsed = pulse_end - pulse_start
    distance = (elapsed * SOUND_SPEED_CM_PER_S) / 2.0
    return distance


def object_detected_ultrasonic() -> bool:
    """Return True when an object is closer than OBJECT_THRESHOLD_CM."""
    dist = read_distance_cm()
    if dist is None:
        return False
    return dist < OBJECT_THRESHOLD_CM


# --------------------------------------------------------------------------- #
# HC-SR501 — passive infrared (PIR) motion sensor
# --------------------------------------------------------------------------- #
def object_detected_pir() -> bool:
    """Return True when the PIR sensor reports motion/presence."""
    return GPIO.input(PIR_PIN) == GPIO.HIGH


# --------------------------------------------------------------------------- #
# Combined detection
# --------------------------------------------------------------------------- #
def object_present() -> bool:
    """
    Fuse both sensors: report presence when EITHER sensor triggers.
    In a production system you would require agreement from both sensors.
    """
    return object_detected_ultrasonic() or object_detected_pir()
