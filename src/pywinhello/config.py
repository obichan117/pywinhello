"""YAML configuration loader for pywinhello."""

from __future__ import annotations

from pathlib import Path

from pywinhello.models import AppConfig, MonitorConfig


def load_config(path: str | Path) -> MonitorConfig:
    """Load MonitorConfig from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        MonitorConfig populated from the file.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If required fields are missing or invalid.
    """
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required for config loading. "
            "Install with: pip install pywinhello[cli]"
        ) from None

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(raw).__name__}")

    raw_apps = raw.get("apps", [])
    if not isinstance(raw_apps, list):
        raise ValueError("'apps' must be a list")

    apps: list[AppConfig] = []
    for i, entry in enumerate(raw_apps):
        if not isinstance(entry, dict):
            raise ValueError(f"apps[{i}] must be a mapping")
        if "exe" not in entry:
            raise ValueError(f"apps[{i}] missing required field 'exe'")
        if "pin" not in entry:
            raise ValueError(f"apps[{i}] missing required field 'pin'")
        apps.append(
            AppConfig(
                exe=entry["exe"],
                pin=str(entry["pin"]),
                pin_select_keys=entry.get("pin_select_keys", ["ESCAPE"]),
            )
        )

    return MonitorConfig(
        apps=apps,
        hid_port=raw.get("hid_port"),
        inter_key_delay_ms=raw.get("inter_key_delay_ms", 50),
        dialog_wait_timeout=raw.get("dialog_wait_timeout", 5.0),
    )
