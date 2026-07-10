"""Device config read/write and dotted-path patch helpers.

Config lives on the Pico (GET_CONFIG/SET_CONFIG). PIN is never part of it —
see pin_service for PIN registration.
"""

from __future__ import annotations

from typing import Any

from pywinhello.serial.protocol import SerialProtocol


def read_config(protocol: SerialProtocol) -> dict[str, Any]:
    return protocol.get_config()


def write_config(protocol: SerialProtocol, patch: dict[str, Any]) -> None:
    protocol.set_config(patch)


def get_field(config: dict[str, Any], dotted: str) -> Any:
    """Look up a dotted path (e.g. 'schedule.time') in a config dict.

    Raises KeyError if any segment of the path is missing.
    """
    value: Any = config
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"Field not found: {dotted}")
        value = value[part]
    return value


def build_patch(dotted: str, value: Any) -> dict[str, Any]:
    """Build a nested SET_CONFIG patch from a dotted path and a value.

    e.g. build_patch("schedule.time", "08:00") -> {"schedule": {"time": "08:00"}}
    """
    patch: dict[str, Any] = value
    for part in reversed(dotted.split(".")):
        patch = {part: patch}
    return patch


def _coerce_value(raw: str) -> Any:
    """Coerce a raw CLI string into bool/int/float/list/str, in that priority order."""
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if "," in raw:
        return [_coerce_value(item.strip()) for item in raw.split(",")]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def parse_assignment(assignment: str) -> tuple[str, Any]:
    """Parse a CLI assignment like 'schedule.time=08:00' into (dotted_path, coerced_value)."""
    if "=" not in assignment:
        raise ValueError(f"Invalid assignment (expected 'key=value'): {assignment}")
    dotted, raw_value = assignment.split("=", 1)
    dotted = dotted.strip()
    if not dotted:
        raise ValueError(f"Invalid assignment, missing key: {assignment}")
    return dotted, _coerce_value(raw_value.strip())
