"""First-run setup — detect Pico state, flash firmware, verify.

Handles every possible Pico state: BOOTSEL mode, running pywinhello,
running unknown firmware, or not connected. Selects the correct firmware
binary based on board variant (Pico / Pico W / Pico 2 / Pico 2 W).

Setup flow (fully automated for target users):
  1. Blank Pico   → auto-enters BOOTSEL → flash UF2 → verify
  2. pywinhello   → check version → OTA if outdated → verify
  3. OTA fails    → REBOOT to BOOTSEL → flash UF2 → verify
  4. Unknown fw   → try REBOOT → fall back to BOOTSEL instructions

Usage::

    from pywinhello.setup import provision, detect

    result = provision()  # auto-detect → flash → verify
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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

# Bundled firmware version — must match FW_VERSION_STRING in pywinhello.h
BUNDLED_FW_VERSION = "1.0.0"

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


def _needs_update(device_version: str | None) -> bool:
    """Check if the device firmware is older than the bundled version."""
    if not device_version or device_version == "0.0.0":
        return True
    try:
        device_parts = tuple(int(x) for x in device_version.split("."))
        bundled_parts = tuple(int(x) for x in BUNDLED_FW_VERSION.split("."))
        return device_parts < bundled_parts
    except ValueError:
        return True


def _reboot_and_flash_uf2(
    port: str,
    board: BoardVariant,
    search_dir: Path | None,
    progress: ProgressCallback,
) -> ProvisionResult:
    """Send REBOOT command, wait for BOOTSEL drive, flash UF2."""
    from pywinhello.serial.protocol import SerialProtocol

    progress("Rebooting Pico to BOOTSEL mode...", 0.3)
    try:
        proto = SerialProtocol(port=port)
        proto.reboot_to_bootsel()
    except Exception:
        logger.debug("REBOOT command failed on %s", port, exc_info=True)
        return ProvisionResult(
            success=False,
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=board,
            message=(
                "Could not reboot Pico automatically. "
                "Hold BOOTSEL while plugging in to enter flash mode."
            ),
        )

    progress("Waiting for BOOTSEL drive...", 0.4)
    drive = wait_for_bootsel_drive(timeout=10.0)
    if drive is None:
        return ProvisionResult(
            success=False,
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=board,
            message="Pico rebooted but BOOTSEL drive did not appear.",
        )

    return _flash_bootsel(drive, board, search_dir, progress)


def _flash_bootsel(
    drive: Path,
    board: BoardVariant,
    search_dir: Path | None,
    progress: ProgressCallback,
) -> ProvisionResult:
    """Flash UF2 to a BOOTSEL drive and verify."""
    fw_path = get_firmware_path(board, search_dir)
    if fw_path is None:
        return ProvisionResult(
            success=False,
            state=DeviceState.BOOTSEL,
            board=board,
            message=f"No firmware found for {board.value}.",
        )

    progress(f"Flashing {fw_path.name}...", 0.5)
    flash_uf2(drive, fw_path, wait_reboot=True)

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


def _ota_update(
    port: str,
    board: BoardVariant,
    search_dir: Path | None,
    progress: ProgressCallback,
) -> ProvisionResult:
    """Update firmware over serial using the OTA FLASH command."""
    from pywinhello.serial.flasher import flash_and_verify
    from pywinhello.serial.protocol import SerialProtocol

    fw_path = get_firmware_path(board, search_dir)
    if fw_path is None:
        return ProvisionResult(
            success=False,
            state=DeviceState.RUNNING_PYWINHELLO,
            board=board,
            message=f"No firmware found for {board.value}.",
        )

    progress(f"Updating firmware via OTA ({fw_path.name})...", 0.3)

    def _on_flash_progress(sent: int, total: int) -> None:
        # Map flash progress to 0.3–0.8 range
        frac = sent / total if total else 0
        progress(f"Flashing... {frac:.0%}", 0.3 + frac * 0.5)

    try:
        proto = SerialProtocol(port=port)
        result = flash_and_verify(
            proto,
            fw_path,
            expected_version=BUNDLED_FW_VERSION,
            on_progress=_on_flash_progress,
        )
        proto.close()
    except Exception as e:
        logger.warning("OTA update failed: %s", e, exc_info=True)
        return ProvisionResult(
            success=False,
            state=DeviceState.RUNNING_PYWINHELLO,
            board=board,
            message=f"OTA update failed: {e}",
        )

    if result.success:
        progress("Update complete!", 1.0)
        return ProvisionResult(
            success=True,
            state=DeviceState.RUNNING_PYWINHELLO,
            board=board,
            firmware_version=BUNDLED_FW_VERSION,
            message=f"Updated to pywinhello v{BUNDLED_FW_VERSION}.",
        )

    return ProvisionResult(
        success=False,
        state=DeviceState.RUNNING_PYWINHELLO,
        board=board,
        message=f"OTA update failed: {result.error}",
    )


def provision(
    firmware_dir: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> ProvisionResult:
    """Detect Pico state, flash firmware if needed, and verify.

    Fully automated for these cases:
      - Blank Pico (auto-BOOTSEL) → flash UF2
      - pywinhello running, outdated → OTA update via FLASH command
      - OTA fails → REBOOT to BOOTSEL → flash UF2

    Falls back to BOOTSEL instructions only for Picos running
    unknown third-party firmware that doesn't respond to REBOOT.

    Args:
        firmware_dir: Optional directory containing .uf2 files. If ``None``,
            searches package data and dev fallback locations.
        on_progress: Optional callback for GUI progress updates.

    Returns:
        ProvisionResult with success status and details.
    """
    progress = on_progress or _noop_progress
    search_dir = Path(firmware_dir) if firmware_dir else None

    progress("Detecting Pico...", 0.0)
    device = detect()

    # ── Nothing found ────────────────────────────────────────────────
    if device.state == DeviceState.NOT_FOUND:
        return ProvisionResult(
            success=False,
            state=device.state,
            message="No Pico detected. Please connect your Pico and try again.",
        )

    # ── BOOTSEL mode (blank Pico or button held) ─────────────────────
    if device.state == DeviceState.BOOTSEL:
        board = device.board
        if board is None:
            return ProvisionResult(
                success=False,
                state=device.state,
                message="Could not identify board variant from BOOTSEL drive.",
            )

        progress(f"Detected {board.value} in BOOTSEL mode", 0.2)
        drive = Path(device.drive)  # type: ignore[arg-type]
        return _flash_bootsel(drive, board, search_dir, progress)

    # ── Running pywinhello ───────────────────────────────────────────
    if device.state == DeviceState.RUNNING_PYWINHELLO:
        assert device.board is not None
        assert device.port is not None

        if not _needs_update(device.firmware_version):
            progress("Firmware is up to date", 1.0)
            return ProvisionResult(
                success=True,
                state=device.state,
                board=device.board,
                firmware_version=device.firmware_version,
                message=f"Pico is running pywinhello v{device.firmware_version}.",
            )

        progress("Firmware update available...", 0.2)

        # Try OTA first (seamless, no reboot needed)
        ota_result = _ota_update(
            device.port, device.board, search_dir, progress,
        )
        if ota_result.success:
            return ota_result

        # OTA failed — fall back to REBOOT → BOOTSEL → UF2
        logger.warning("OTA failed, falling back to REBOOT → BOOTSEL")
        return _reboot_and_flash_uf2(
            device.port, device.board, search_dir, progress,
        )

    # ── Unknown firmware ─────────────────────────────────────────────
    assert device.state == DeviceState.UNKNOWN_FIRMWARE
    assert device.port is not None

    # Try REBOOT anyway — might be old pywinhello that partially works
    board = device.board
    if board is not None:
        reboot_result = _reboot_and_flash_uf2(
            device.port, board, search_dir, progress,
        )
        if reboot_result.success:
            return reboot_result

    return ProvisionResult(
        success=False,
        state=device.state,
        board=device.board,
        message=(
            "Pico is running unknown firmware. "
            "Hold BOOTSEL while plugging in to enter flash mode."
        ),
    )


__all__ = [
    "BUNDLED_FW_VERSION",
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
