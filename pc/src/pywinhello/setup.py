"""First-run firmware setup — flash .uf2 to Pico in BOOTSEL mode.

When a Pico is held in BOOTSEL mode and plugged in, it appears as a USB mass
storage drive named "RPI-RP2". Flashing is a simple file copy of the .uf2
firmware to this drive. The Pico reboots automatically after the copy.

Usage::

    from pywinhello.setup import flash_uf2, find_bootsel_drive

    drive = find_bootsel_drive()
    if drive:
        flash_uf2(drive, "firmware.uf2")
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Name of the USB mass storage volume when Pico is in BOOTSEL mode
_BOOTSEL_VOLUME_NAME = "RPI-RP2"

# How long to wait for Pico to reboot after flashing (seconds)
_REBOOT_WAIT = 5.0

# Max time to wait for the BOOTSEL drive to appear
_DRIVE_DETECT_TIMEOUT = 30.0


def find_bootsel_drive() -> Path | None:
    """Find the RPI-RP2 drive (Pico in BOOTSEL mode).

    Scans Windows drive letters D: through Z: for a volume named RPI-RP2.

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


def get_bundled_firmware() -> Path | None:
    """Get the path to the bundled .uf2 firmware file.

    Looks in the package's ``_data/firmware/`` directory for a .uf2 file.
    This is populated by CI/CD when building the installer.

    Returns:
        Path to the .uf2 file, or ``None`` if not bundled.
    """
    try:
        import importlib.resources as resources

        data_dir = resources.files("pywinhello") / "_data" / "firmware"
        for item in data_dir.iterdir():
            if str(item).endswith(".uf2"):
                return Path(str(item))
    except (ImportError, FileNotFoundError, TypeError):
        pass

    # Fallback: check relative to this file
    local = Path(__file__).parent / "_data" / "firmware"
    if local.is_dir():
        uf2_files = list(local.glob("*.uf2"))
        if uf2_files:
            return uf2_files[0]

    return None
