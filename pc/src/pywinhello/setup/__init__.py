"""First-run setup — detect Pico state, flash firmware, verify.

Handles every possible Pico state: BOOTSEL mode, running pywinhello,
running unknown firmware, or not connected. Selects the correct firmware
binary based on board variant (Pico / Pico W / Pico 2 / Pico 2 W).

Usage::

    from pywinhello.setup import provision, detect

    result = provision()  # auto-detect → flash → verify
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from pywinhello.models import BoardVariant
from pywinhello.setup.bootsel import (
    find_bootsel_drive,
    flash_uf2,
    parse_board_info,
    wait_for_bootsel_drive,
)
from pywinhello.setup.detect import DetectedDevice, DeviceState, detect
from pywinhello.setup.firmware import get_firmware_path, list_bundled_firmware

logger = logging.getLogger(__name__)

# Type alias for progress callbacks (message: str, progress: float 0..1)
ProgressCallback = Callable[[str, float], None]


@dataclass(frozen=True)
class ProvisionResult:
    """Result of the provisioning process."""

    success: bool
    state: DeviceState
    board: BoardVariant | None = None
    firmware_version: str | None = None
    message: str = ""


def _noop_progress(message: str, progress: float) -> None:
    pass


def provision(
    firmware_dir: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> ProvisionResult:
    """Detect Pico state, flash firmware if needed, and verify.

    Args:
        firmware_dir: Optional directory containing .uf2 files. If ``None``,
            searches package data and dev fallback locations.
        on_progress: Optional callback for GUI progress updates.

    Returns:
        ProvisionResult with success status and details.
    """
    from pathlib import Path

    progress = on_progress or _noop_progress

    progress("Detecting Pico...", 0.0)
    device = detect()

    if device.state == DeviceState.NOT_FOUND:
        return ProvisionResult(
            success=False,
            state=device.state,
            message="No Pico detected. Please connect your Pico and try again.",
        )

    if device.state == DeviceState.UNKNOWN_FIRMWARE:
        return ProvisionResult(
            success=False,
            state=device.state,
            board=device.board,
            message=(
                "Pico is running unknown firmware. "
                "Hold BOOTSEL while plugging in to enter flash mode."
            ),
        )

    if device.state == DeviceState.RUNNING_PYWINHELLO:
        progress("pywinhello firmware detected", 0.5)
        # Already running — check if OTA update is needed
        # (OTA via serial/flasher is a separate concern, just report status)
        return ProvisionResult(
            success=True,
            state=device.state,
            board=device.board,
            firmware_version=device.firmware_version,
            message=f"Pico is running pywinhello v{device.firmware_version}.",
        )

    # BOOTSEL mode — flash firmware
    assert device.state == DeviceState.BOOTSEL
    board = device.board
    if board is None:
        return ProvisionResult(
            success=False,
            state=device.state,
            message="Could not identify board variant from BOOTSEL drive.",
        )

    progress(f"Detected {board.value} in BOOTSEL mode", 0.2)

    # Find firmware
    search_dir = Path(firmware_dir) if firmware_dir else None
    fw_path = get_firmware_path(board, search_dir)
    if fw_path is None:
        return ProvisionResult(
            success=False,
            state=device.state,
            board=board,
            message=f"No firmware found for {board.value}.",
        )

    # Flash
    drive = Path(device.drive)  # type: ignore[arg-type]
    progress(f"Flashing {fw_path.name}...", 0.4)
    flash_uf2(drive, fw_path, wait_reboot=True)

    # Verify — device should now appear on serial
    progress("Verifying firmware...", 0.8)
    verify = detect()
    if verify.state == DeviceState.RUNNING_PYWINHELLO:
        progress("Setup complete!", 1.0)
        return ProvisionResult(
            success=True,
            state=verify.state,
            board=verify.board,
            firmware_version=verify.firmware_version,
            message=f"Flashed and verified pywinhello v{verify.firmware_version}.",
        )

    return ProvisionResult(
        success=False,
        state=verify.state,
        board=board,
        message="Firmware flashed but verification failed. Pico may still be rebooting.",
    )


__all__ = [
    "DetectedDevice",
    "DeviceState",
    "ProvisionResult",
    "detect",
    "find_bootsel_drive",
    "flash_uf2",
    "get_firmware_path",
    "list_bundled_firmware",
    "parse_board_info",
    "provision",
    "wait_for_bootsel_drive",
]
