"""PIN validation and registration against a connected Pico.

PIN is stored on-device only (encrypted /pin.enc) — never part of GET_CONFIG/
SET_CONFIG, and never logged here.
"""

from __future__ import annotations

from pywinhello.serial.protocol import SerialProtocol

MIN_PIN_LENGTH = 4


def validate_pin(pin: str) -> None:
    """Raise ValueError with a plain human message if the PIN is invalid."""
    if not pin:
        raise ValueError("PIN cannot be empty.")
    if len(pin) < MIN_PIN_LENGTH:
        raise ValueError(f"PIN must be at least {MIN_PIN_LENGTH} characters.")


def register_pin(protocol: SerialProtocol, pin: str) -> None:
    validate_pin(pin)
    protocol.setup_pin(pin)
