"""Wake schedule (time + active days) read/write against a connected Pico.

DAY_KEYS/DEFAULT_DAYS are owned here (single source of truth); gui.constants
canonical, GUI-independent source — gui/constants.py is left untouched pending
a later migration to call this module directly.
"""

from __future__ import annotations

from pywinhello.serial.protocol import SerialProtocol

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_DAYS = ["mon", "tue", "wed", "thu", "fri"]


def format_time(hour: int, minute: int) -> str:
    if not (0 <= hour <= 23):
        raise ValueError(f"Hour out of range 0-23: {hour}")
    if not (0 <= minute <= 59):
        raise ValueError(f"Minute out of range 0-59: {minute}")
    return f"{hour:02d}:{minute:02d}"


def parse_time(time_str: str) -> tuple[int, int]:
    hour_str, sep, minute_str = time_str.partition(":")
    if not sep:
        raise ValueError(f"Invalid time format (expected 'HH:MM'): {time_str}")
    return int(hour_str), int(minute_str)


def parse_days(days: list[str]) -> list[str]:
    """Validate and lowercase day keys against DAY_KEYS."""
    normalized = [day.lower() for day in days]
    unknown = [day for day in normalized if day not in DAY_KEYS]
    if unknown:
        raise ValueError(f"Unknown day(s): {', '.join(unknown)}")
    return normalized


def save_schedule(protocol: SerialProtocol, hour: int, minute: int, days: list[str]) -> None:
    schedule = {"time": format_time(hour, minute), "days": parse_days(days)}
    protocol.set_config({"schedule": schedule})
