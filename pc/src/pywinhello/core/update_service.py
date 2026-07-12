"""GitHub release check and on-device FLASH trigger, extracted from the
settings GUI's version_info panel.

Software update is a version comparison against the latest GitHub release
tag. Firmware update triggers the Pico's own FLASH self-update over serial —
this does not stream a firmware image (see gui/settings/version_info.py for
the original GUI behavior this mirrors).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from pywinhello.monitor.updater import get_current_version
from pywinhello.serial.protocol import Command, SerialProtocol

logger = logging.getLogger(__name__)

_GITHUB_RELEASES_URL = "https://api.github.com/repos/obichan117/pywinhello/releases/latest"


@dataclass(frozen=True)
class UpdateCheckResult:
    current_version: str
    latest_version: str | None
    has_software_update: bool
    has_firmware_update: bool
    error: str | None = None


def check_for_update() -> UpdateCheckResult:
    current_version = get_current_version()
    try:
        with urllib.request.urlopen(_GITHUB_RELEASES_URL, timeout=10) as response:
            data = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        return UpdateCheckResult(
            current_version=current_version,
            latest_version=None,
            has_software_update=False,
            has_firmware_update=False,
            error=str(e),
        )

    latest_tag = data.get("tag_name", "").lstrip("v")
    has_software_update = bool(latest_tag) and latest_tag != current_version.replace("-dev", "")

    assets = data.get("assets", [])
    has_firmware_update = any(asset.get("name", "").endswith(".uf2") for asset in assets)

    return UpdateCheckResult(
        current_version=current_version,
        latest_version=latest_tag or None,
        has_software_update=has_software_update,
        has_firmware_update=has_firmware_update,
    )


def apply_firmware_update(protocol: SerialProtocol) -> bool:
    resp = protocol.send(Command.FLASH)
    return resp.ok


__all__ = ["UpdateCheckResult", "apply_firmware_update", "check_for_update"]
