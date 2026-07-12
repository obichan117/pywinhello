"""Aggregate device/schedule/monitor status for CLI and GUI display.

Never raises — a missing/unreachable Pico is reflected as device_connected=False,
not an exception.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from pywinhello.monitor.scheduler_sync import _WAKE_TASK_NAME, task_exists
from pywinhello.serial.protocol import SerialProtocol
from pywinhello.setup.detect import DeviceState, detect


@dataclass(frozen=True)
class StatusReport:
    device_connected: bool
    port: str | None
    firmware_version: str | None
    pin_set: bool
    schedule_armed: bool
    monitor_running: bool


def _read_pin_set(port: str) -> bool:
    try:
        with SerialProtocol(port=port) as proto:
            status = proto.status()
    except Exception:
        return False
    # Firmware STATUS emits "pin_stored" (serial_proto.c); accept legacy/alt keys defensively.
    for key in ("pin_stored", "pin_set", "has_pin"):
        if key in status:
            return bool(status[key])
    return False


def _is_schedule_armed() -> bool:
    try:
        return task_exists(_WAKE_TASK_NAME)
    except Exception:
        return False


def _is_monitor_running() -> bool:
    """Best-effort check: is the pywinhello monitor process currently running.

    The packaged monitor is pywinhello-monitor.exe (pywinhello.exe is the CLI).
    """
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["tasklist.exe", "/fi", "imagename eq pywinhello-monitor.exe", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return False
    return "pywinhello-monitor.exe" in result.stdout.lower()


def gather_status() -> StatusReport:
    device = detect()
    device_connected = device.state == DeviceState.RUNNING_PYWINHELLO

    pin_set = False
    if device_connected and device.port:
        pin_set = _read_pin_set(device.port)

    return StatusReport(
        device_connected=device_connected,
        port=device.port,
        firmware_version=device.firmware_version,
        pin_set=pin_set,
        schedule_armed=_is_schedule_armed(),
        monitor_running=_is_monitor_running(),
    )
