"""pywinhello — Raspberry Pi Pico as a physical key for Windows Hello automation.

Architecture:
- Pico firmware (C): stores PIN encrypted, types via USB HID
- PC monitor: detects lock screens / Hello dialogs, sends serial commands
- Settings GUI: reads/writes Pico config over serial
"""

from pywinhello.models import AuthEvent, BoardVariant
from pywinhello.monitor import MonitorService
from pywinhello.serial import PicoDevice, SerialProtocol, find_pico_port
from pywinhello.setup.detect import detect

__all__ = [
    "AuthEvent",
    "BoardVariant",
    "MonitorService",
    "PicoDevice",
    "SerialProtocol",
    "detect",
    "find_pico_port",
]
