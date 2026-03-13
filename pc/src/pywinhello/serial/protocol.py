"""Command/response encoding for all serial protocol commands.

Protocol is text-based, newline-delimited::

    COMMAND:payload\\n  ->  OK\\n | OK:data\\n | ERR:message\\n

Commands:
    PING          -> PONG:<device>:<version>   (device type + firmware version)
    GET_CONFIG    -> OK:{json}
    SET_CONFIG:{json} -> OK
    SETUP_PIN:{pin}   -> OK
    CLEAR         -> OK
    UNLOCK        -> OK  (Pico types stored PIN + ENTER)
    HELLO         -> OK  (Pico types stored PIN, no ENTER — for Windows Hello)
    GET_LOG       -> OK:{json array}
    FLASH:{size}  -> READY  (then stream binary)
    STATUS        -> OK:{json}
    TYPE:{text}   -> OK  (type arbitrary text)
    PRESS:{key}   -> OK  (press named key)
    COMBO:{k+k}   -> OK  (key combination)
    DELAY:{ms}    -> OK  (set keystroke delay)
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import serial as pyserial

logger = logging.getLogger(__name__)


class Command(StrEnum):
    """All serial protocol commands."""

    # Core commands
    PING = "PING"
    GET_CONFIG = "GET_CONFIG"
    SET_CONFIG = "SET_CONFIG"
    SETUP_PIN = "SETUP_PIN"
    CLEAR = "CLEAR"
    UNLOCK = "UNLOCK"
    HELLO = "HELLO"
    GET_LOG = "GET_LOG"
    FLASH = "FLASH"
    STATUS = "STATUS"

    # HID typing commands (used by monitor for ESCAPE fallback)
    PRESS = "PRESS"


@dataclass(frozen=True)
class Response:
    """Parsed serial response from the Pico."""

    raw: str
    """Full response line as received."""

    ok: bool
    """True if response indicates success."""

    data: str
    """Payload after the status prefix (empty string if none)."""

    @property
    def json(self) -> Any:
        """Parse data as JSON. Raises ValueError on invalid JSON."""
        if not self.data:
            raise ValueError("Response has no data payload")
        return json.loads(self.data)


@dataclass(frozen=True)
class PingInfo:
    """Parsed PING response with device metadata."""

    protocol_version: int
    """Protocol version number."""

    device_type: str
    """Device type string (e.g. 'rp2040', 'rp2350')."""

    firmware_version: str
    """Firmware version string (e.g. '1.0.0')."""


# Default timeouts per command (seconds)
_COMMAND_TIMEOUTS: dict[Command, float] = {
    Command.PING: 2.0,
    Command.GET_CONFIG: 3.0,
    Command.SET_CONFIG: 3.0,
    Command.SETUP_PIN: 2.0,
    Command.CLEAR: 2.0,
    Command.UNLOCK: 5.0,
    Command.HELLO: 5.0,
    Command.GET_LOG: 5.0,
    Command.FLASH: 10.0,
    Command.STATUS: 2.0,
    Command.PRESS: 2.0,
}

_DEFAULT_TIMEOUT = 2.0


def encode_command(command: Command, payload: str | None = None) -> bytes:
    """Encode a command into the wire format.

    Args:
        command: The command to send.
        payload: Optional payload string.

    Returns:
        Encoded bytes ready to write to serial.
    """
    if payload is not None:
        line = f"{command.value}:{payload}\n"
    else:
        line = f"{command.value}\n"
    return line.encode("utf-8")


def parse_response(raw: str) -> Response:
    """Parse a raw response line into a Response object.

    Recognizes these formats:
        PONG             -> ok=True, data=""
        PONG:v2:rp2040   -> ok=True, data="v2:rp2040"
        OK               -> ok=True, data=""
        OK:{json}        -> ok=True, data="{json}"
        READY            -> ok=True, data=""
        ERR:message      -> ok=False, data="message"
    """
    raw = raw.strip()
    if not raw:
        return Response(raw="", ok=False, data="empty response")

    if raw.startswith("ERR:"):
        return Response(raw=raw, ok=False, data=raw[4:])

    if raw == "OK" or raw == "PONG" or raw == "READY":
        return Response(raw=raw, ok=True, data="")

    if raw.startswith("OK:"):
        return Response(raw=raw, ok=True, data=raw[3:])

    if raw.startswith("PONG:"):
        return Response(raw=raw, ok=True, data=raw[5:])

    # Unknown format — treat as success with the whole line as data
    return Response(raw=raw, ok=True, data=raw)


def parse_ping(response: Response) -> PingInfo:
    """Parse a PING response into PingInfo.

    Handles multiple firmware response formats:
    - Legacy: ``PONG`` (no metadata)
    - Colon format: ``PONG:2:rp2040:1.0.0`` (colon-separated)
    - Comma format: ``OK:pico_w,1.0.0`` (comma-separated board + version)

    Args:
        response: The parsed response from a PING command.

    Returns:
        PingInfo with device metadata.
    """
    if not response.ok:
        raise ValueError(f"PING failed: {response.data}")

    if not response.data:
        # Legacy firmware — just PONG with no metadata
        return PingInfo(protocol_version=1, device_type="unknown", firmware_version="0.0.0")

    # Firmware format: "pico_w,1.0.0" (comma-separated, in OK:data)
    if "," in response.data:
        parts = response.data.split(",")
        device_type = parts[0].strip()
        firmware_version = parts[1].strip() if len(parts) >= 2 else "0.0.0"
        return PingInfo(
            protocol_version=2,
            device_type=device_type,
            firmware_version=firmware_version,
        )

    # PONG format: "2:rp2040:1.0.0" (colon-separated with protocol prefix)
    parts = response.data.split(":")
    if len(parts) >= 3:
        try:
            proto = int(parts[0][1:] if parts[0].startswith("v") else parts[0])
        except ValueError:
            proto = 2
        return PingInfo(
            protocol_version=proto,
            device_type=parts[1],
            firmware_version=parts[2],
        )

    # Partial response — just a device type
    device = parts[0] if parts else "unknown"
    return PingInfo(protocol_version=2, device_type=device, firmware_version="0.0.0")


class SerialProtocol:
    """Thread-safe serial protocol handler for Pico communication.

    Wraps a pyserial.Serial connection with command encoding, response parsing,
    and per-command timeout handling.

    Usage::

        proto = SerialProtocol(port="COM8")
        info = proto.ping()
        config = proto.get_config()
        proto.hello()
        proto.close()
    """

    def __init__(
        self,
        port: str,
        baud_rate: int = 115200,
        default_timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._port_name = port
        self._default_timeout = default_timeout
        self._serial = pyserial.Serial(
            port=port,
            baudrate=baud_rate,
            timeout=default_timeout,
            write_timeout=default_timeout,
        )
        self._lock = threading.Lock()
        logger.debug("SerialProtocol connected on %s @ %d baud", port, baud_rate)

    @property
    def port(self) -> str:
        """The COM port name."""
        return self._port_name

    @property
    def is_open(self) -> bool:
        """Whether the serial connection is open."""
        return bool(self._serial and self._serial.is_open)

    def send(self, command: Command, payload: str | None = None) -> Response:
        """Send a command and wait for a response.

        Args:
            command: The command to send.
            payload: Optional payload string.

        Returns:
            Parsed Response object.

        Raises:
            TimeoutError: If no response within the command's timeout.
            ConnectionError: If the serial port is not open.
        """
        if not self.is_open:
            raise ConnectionError("Serial port is not open")

        timeout = _COMMAND_TIMEOUTS.get(command, self._default_timeout)
        data = encode_command(command, payload)

        with self._lock:
            # Set per-command timeout
            self._serial.timeout = timeout
            self._serial.reset_input_buffer()
            self._serial.write(data)
            self._serial.flush()

            raw = self._serial.readline()
            if not raw:
                raise TimeoutError(f"No response from Pico for: {command.value}")

            resp_str = raw.decode("utf-8", errors="replace").strip()
            logger.debug("TX: %s -> RX: %s", data.decode().strip(), resp_str)
            return parse_response(resp_str)

    def send_checked(self, command: Command, payload: str | None = None) -> Response:
        """Send a command and raise on error response.

        Like ``send()`` but raises RuntimeError if the Pico returns ERR.
        """
        resp = self.send(command, payload)
        if not resp.ok:
            raise RuntimeError(f"{command.value} failed: {resp.data}")
        return resp

    # Convenience methods for each command

    def ping(self) -> PingInfo:
        """Send PING and return parsed device info."""
        resp = self.send(Command.PING)
        return parse_ping(resp)

    def get_config(self) -> dict[str, Any]:
        """Read full configuration JSON from Pico."""
        resp = self.send_checked(Command.GET_CONFIG)
        return resp.json  # type: ignore[no-any-return]

    def set_config(self, config: dict[str, Any]) -> None:
        """Write configuration JSON to Pico."""
        payload = json.dumps(config, separators=(",", ":"))
        self.send_checked(Command.SET_CONFIG, payload)

    def setup_pin(self, pin: str) -> None:
        """Store a PIN on the Pico (cleartext over local USB serial)."""
        self.send_checked(Command.SETUP_PIN, pin)

    def clear(self) -> None:
        """Clear stored PIN and reset Pico to factory state."""
        self.send_checked(Command.CLEAR)

    def unlock(self) -> None:
        """Tell Pico to type stored PIN + ENTER (for lock screen)."""
        self.send_checked(Command.UNLOCK)

    def hello(self) -> None:
        """Tell Pico to type stored PIN (for Windows Hello dialog, no ENTER)."""
        self.send_checked(Command.HELLO)

    def get_log(self) -> list[dict[str, Any]]:
        """Read event log entries from Pico."""
        resp = self.send_checked(Command.GET_LOG)
        return resp.json  # type: ignore[no-any-return]

    def status(self) -> dict[str, Any]:
        """Read device status (uptime, PIN configured, etc.)."""
        resp = self.send_checked(Command.STATUS)
        return resp.json  # type: ignore[no-any-return]

    def flash_begin(self, size: int) -> Response:
        """Initiate firmware flash. Returns READY response.

        After receiving READY, the caller should stream the binary data
        using ``write_raw()``.
        """
        resp = self.send(Command.FLASH, str(size))
        if resp.raw.strip() != "READY":
            raise RuntimeError(f"FLASH did not return READY: {resp.raw}")
        return resp

    def write_raw(self, data: bytes) -> None:
        """Write raw bytes to serial (for firmware streaming after FLASH)."""
        with self._lock:
            self._serial.write(data)
            self._serial.flush()

    def read_line(self, timeout: float | None = None) -> str:
        """Read a single line from serial (for flash progress/completion)."""
        with self._lock:
            if timeout is not None:
                self._serial.timeout = timeout
            raw = self._serial.readline()
            if not raw:
                raise TimeoutError("No response from Pico")
            return raw.decode("utf-8", errors="replace").strip()

    def close(self) -> None:
        """Close the serial connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("SerialProtocol disconnected from %s", self._port_name)

    def __enter__(self) -> SerialProtocol:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
