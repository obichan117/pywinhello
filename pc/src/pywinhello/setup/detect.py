"""Pico state detection — probe USB for device state and board variant.

Detection priority:
1. BOOTSEL drive (RPI-RP2 mass storage) → parse INFO_UF2.TXT
2. CDC serial with VID:PID match → PING for firmware info
3. VID:PID match but PING fails → unknown firmware
4. Nothing found → not connected
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from serial.tools import list_ports

from pywinhello.models import BOARD_BY_PID, PICO_VID, BoardVariant

logger = logging.getLogger(__name__)


class DeviceState(Enum):
    """Possible Pico states during setup."""

    BOOTSEL = "bootsel"
    RUNNING_PYWINHELLO = "running_pywinhello"
    UNKNOWN_FIRMWARE = "unknown_firmware"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class DetectedDevice:
    """Result of probing USB for a Pico device."""

    state: DeviceState
    board: BoardVariant | None = None
    port: str | None = None
    drive: str | None = None
    firmware_version: str | None = None


def _detect_bootsel() -> DetectedDevice | None:
    """Check for a Pico in BOOTSEL mode (RPI-RP2 mass storage)."""
    from pywinhello.setup.bootsel import find_bootsel_drive, parse_board_info

    drive = find_bootsel_drive()
    if drive is None:
        return None

    board = parse_board_info(drive)
    return DetectedDevice(
        state=DeviceState.BOOTSEL,
        board=board,
        drive=str(drive),
    )


def _detect_serial() -> DetectedDevice | None:
    """Check for a Pico on CDC serial (VID:PID match + PING)."""
    ports = list_ports.comports()
    pico_pids = set(BOARD_BY_PID.keys())

    candidates = [p for p in ports if p.vid == PICO_VID and p.pid in pico_pids]
    if not candidates:
        # Fallback: VID-only match
        candidates = [p for p in ports if p.vid == PICO_VID]

    if not candidates:
        return None

    best = max(candidates, key=lambda p: p.device)
    board_from_pid = BOARD_BY_PID.get(best.pid) if best.pid else None

    # Try PING to confirm pywinhello firmware
    try:
        from pywinhello.serial.protocol import SerialProtocol

        proto = SerialProtocol(port=best.device)
        try:
            ping_info = proto.ping()
            # Resolve board from PING device_type (more reliable than PID)
            board = _board_from_device_type(ping_info.device_type) or board_from_pid
            return DetectedDevice(
                state=DeviceState.RUNNING_PYWINHELLO,
                board=board,
                port=best.device,
                firmware_version=ping_info.firmware_version,
            )
        finally:
            proto.close()
    except Exception:
        logger.debug("PING failed on %s — unknown firmware", best.device)
        return DetectedDevice(
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=board_from_pid,
            port=best.device,
        )


def _board_from_device_type(device_type: str) -> BoardVariant | None:
    """Map a PING device_type string to a BoardVariant."""
    try:
        return BoardVariant(device_type)
    except ValueError:
        return None


def detect() -> DetectedDevice:
    """Probe USB and return the current Pico state.

    Checks in priority order: BOOTSEL → serial → not found.
    """
    # 1. BOOTSEL mode?
    result = _detect_bootsel()
    if result is not None:
        logger.info("Detected Pico in BOOTSEL mode: %s", result)
        return result

    # 2. Serial (running firmware)?
    result = _detect_serial()
    if result is not None:
        logger.info("Detected Pico on serial: %s", result)
        return result

    # 3. Nothing found
    logger.info("No Pico detected")
    return DetectedDevice(state=DeviceState.NOT_FOUND)
