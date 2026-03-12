"""Serial protocol for v2 Pico communication.

Provides device detection, command/response protocol, and firmware flashing
over USB CDC serial.
"""

from pywinhello.serial.device import PicoDevice
from pywinhello.serial.protocol import SerialProtocol

__all__ = [
    "PicoDevice",
    "SerialProtocol",
]
