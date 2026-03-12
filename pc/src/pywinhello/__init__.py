"""pywinhello — Raspberry Pi Pico as a physical key for Windows Hello automation.

v2 architecture:
- Pico firmware (C): stores PIN, types via USB HID
- PC monitor: detects lock/dialogs, sends serial commands
- Settings GUI: reads/writes Pico config over serial

v1 API (still available during migration):
- ``enter_pin(pin)`` — immediate one-shot PIN entry
- ``handle_next(pin_map)`` — wait for next dialog, enter PIN, return result
- ``serve(pin_map)`` — daemon loop, handles all dialogs
- ``HIDKeyboard`` — raw serial HID bridge
"""

from pywinhello.config import load_config
from pywinhello.hid import HIDKeyboard
from pywinhello.models import AppConfig, AuthEvent, MonitorConfig
from pywinhello.monitor import HelloMonitor
from pywinhello.pin import enter_pin

__all__ = [
    "AppConfig",
    "AuthEvent",
    "HelloMonitor",
    "HIDKeyboard",
    "MonitorConfig",
    "enter_pin",
    "load_config",
]
