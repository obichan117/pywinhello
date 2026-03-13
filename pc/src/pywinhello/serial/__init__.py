"""Serial protocol for Pico communication.

Provides device detection, command/response protocol, and firmware flashing
over USB CDC serial.
"""

from pywinhello.serial.device import ConnectionState, DeviceInfo, PicoDevice, find_pico_port
from pywinhello.serial.flasher import FlashResult, flash_and_verify, flash_firmware
from pywinhello.serial.protocol import (
    Command,
    PingInfo,
    Response,
    SerialProtocol,
    encode_command,
    parse_ping,
    parse_response,
)

__all__ = [
    "Command",
    "ConnectionState",
    "DeviceInfo",
    "FlashResult",
    "PicoDevice",
    "find_pico_port",
    "PingInfo",
    "Response",
    "SerialProtocol",
    "encode_command",
    "flash_and_verify",
    "flash_firmware",
    "parse_ping",
    "parse_response",
]
