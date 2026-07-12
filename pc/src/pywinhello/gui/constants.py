"""Shared constants for the GUI subsystem."""

from __future__ import annotations

# Day keys are owned by core.schedule_service (single source of truth); re-exported
# here so existing GUI imports keep working.
from pywinhello.core.schedule_service import DAY_KEYS, DEFAULT_DAYS

# PIN validation
MIN_PIN_LENGTH = 4

__all__ = ["DAY_KEYS", "DEFAULT_DAYS", "MIN_PIN_LENGTH", "validate_pin"]


def validate_pin(pin: str, confirm: str | None = None) -> str | None:
    """Validate a PIN entry.

    Args:
        pin: The PIN string.
        confirm: Optional confirmation string (must match pin).

    Returns:
        Error i18n key if invalid, None if valid.
    """
    if not pin:
        return "wizard.step3.pin_empty"
    if len(pin) < MIN_PIN_LENGTH:
        return "wizard.step3.pin_too_short"
    if confirm is not None and pin != confirm:
        return "wizard.step3.pin_mismatch"
    return None
