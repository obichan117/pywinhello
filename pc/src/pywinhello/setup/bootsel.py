"""BOOTSEL mode operations — drive detection, board identification, UF2 flashing.

When a Pico is held in BOOTSEL mode and plugged in, it appears as a USB mass
storage drive. The ``INFO_UF2.TXT`` file on that drive identifies the board
chip and capabilities. Flashing is a simple file copy of the .uf2 firmware.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from pywinhello.models import BoardVariant

logger = logging.getLogger(__name__)

_REBOOT_WAIT = 5.0
_DRIVE_DETECT_TIMEOUT = 30.0


def find_bootsel_drive() -> Path | None:
    """Find the RPI-RP2 drive (Pico in BOOTSEL mode).

    Scans Windows drive letters D: through Z: for INFO_UF2.TXT with
    Raspberry Pi content.

    Returns:
        Path to the drive root (e.g. ``Path("E:/")``) or ``None``.
    """
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        info_file = drive / "INFO_UF2.TXT"
        if info_file.exists():
            try:
                content = info_file.read_text(encoding="utf-8", errors="ignore")
                if "RPI-RP2" in content or "Raspberry Pi" in content:
                    logger.info("Found BOOTSEL drive at %s", drive)
                    return drive
            except OSError:
                continue
    return None


def wait_for_bootsel_drive(timeout: float = _DRIVE_DETECT_TIMEOUT) -> Path | None:
    """Wait for the RPI-RP2 drive to appear.

    Args:
        timeout: Maximum seconds to wait.

    Returns:
        Path to the drive or ``None`` if timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        drive = find_bootsel_drive()
        if drive is not None:
            return drive
        time.sleep(0.5)
    return None


def parse_board_info(drive: Path) -> BoardVariant | None:
    """Determine board variant from INFO_UF2.TXT on a BOOTSEL drive.

    Uses a two-axis check:
    - Chip: RP2350 → Pico 2 family, else RP2040 → Pico 1 family
    - WiFi: "Pico W" or "Pico 2 W" in board name → W variant

    Returns:
        BoardVariant or None if the file can't be parsed.
    """
    info_file = drive / "INFO_UF2.TXT"
    try:
        content = info_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    is_rp2350 = "RP2350" in content
    is_wifi = "Pico W" in content or "Pico 2 W" in content

    if is_rp2350:
        return BoardVariant.PICO_2_W if is_wifi else BoardVariant.PICO_2
    return BoardVariant.PICO_W if is_wifi else BoardVariant.PICO


def flash_uf2(
    bootsel_drive: Path,
    firmware_path: str | Path,
    wait_reboot: bool = True,
) -> bool:
    """Copy a .uf2 firmware file to the BOOTSEL drive.

    The Pico automatically reboots after the copy completes.

    Args:
        bootsel_drive: Path to the RPI-RP2 drive root.
        firmware_path: Path to the .uf2 file to flash.
        wait_reboot: Whether to wait for the Pico to reboot.

    Returns:
        True if the copy succeeded.

    Raises:
        FileNotFoundError: If firmware_path does not exist.
    """
    fw_path = Path(firmware_path)
    if not fw_path.exists():
        raise FileNotFoundError(f"Firmware not found: {fw_path}")

    dest = bootsel_drive / fw_path.name
    size = fw_path.stat().st_size

    logger.info("Flashing %s (%d bytes) to %s", fw_path.name, size, bootsel_drive)
    shutil.copy2(fw_path, dest)
    logger.info("Firmware copied, Pico rebooting...")

    if wait_reboot:
        time.sleep(_REBOOT_WAIT)

    return True
