"""Pico device detection, handshake, and connection lifecycle.

Reuses VID:PID detection logic from ``pywinhello.hid`` and adds v2 protocol
support with connection state management and automatic reconnection.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

from pywinhello.hid import find_pico_port
from pywinhello.serial.protocol import PingInfo, SerialProtocol

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """Device connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class DeviceInfo:
    """Discovered Pico device information."""

    port: str
    """COM port name (e.g. 'COM8')."""

    ping_info: PingInfo
    """Parsed PING response with protocol version, device type, firmware version."""

    connected_at: float = field(default_factory=time.time)
    """Timestamp when the device was connected."""


class PicoDevice:
    """Manages connection to a Pico over serial with v2 protocol support.

    Handles auto-detection, handshake, connection state, and reconnection.

    Usage::

        device = PicoDevice()
        device.connect()       # auto-detect + handshake
        info = device.info     # DeviceInfo after successful connect
        device.protocol.hello()
        device.disconnect()

    Or as context manager::

        with PicoDevice() as device:
            device.protocol.hello()
    """

    def __init__(
        self,
        port: str | None = None,
        baud_rate: int = 115200,
        reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0,
    ) -> None:
        self._port: str | None = port
        self._baud_rate = baud_rate
        self._reconnect_attempts = reconnect_attempts
        self._reconnect_delay = reconnect_delay

        self._protocol: SerialProtocol | None = None
        self._info: DeviceInfo | None = None
        self._state = ConnectionState.DISCONNECTED
        self._lock = threading.Lock()

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Whether the device is connected and handshake completed."""
        return self._state == ConnectionState.CONNECTED

    @property
    def protocol(self) -> SerialProtocol:
        """The serial protocol handler. Raises if not connected."""
        if self._protocol is None or not self.is_connected:
            raise ConnectionError("Pico is not connected. Call connect() first.")
        return self._protocol

    @property
    def info(self) -> DeviceInfo | None:
        """Device info from the last successful handshake."""
        return self._info

    def detect_port(self) -> str | None:
        """Auto-detect the Pico COM port by VID:PID.

        Returns:
            COM port name or None if not found.
        """
        return find_pico_port()

    def connect(self) -> DeviceInfo:
        """Connect to the Pico and perform handshake.

        Auto-detects the port if not specified. Sends PING to verify
        the device and read protocol version / firmware info.

        Returns:
            DeviceInfo with device metadata.

        Raises:
            ConnectionError: If device not found or handshake fails.
        """
        with self._lock:
            self._state = ConnectionState.CONNECTING

            port = self._port or self.detect_port()
            if port is None:
                self._state = ConnectionState.ERROR
                raise ConnectionError("Pico not found. Is it connected?")

            try:
                proto = SerialProtocol(port=port, baud_rate=self._baud_rate)
                ping_info = proto.ping()

                self._protocol = proto
                self._info = DeviceInfo(port=port, ping_info=ping_info)
                self._state = ConnectionState.CONNECTED

                logger.info(
                    "Pico connected on %s — protocol v%d, %s, firmware %s",
                    port,
                    ping_info.protocol_version,
                    ping_info.device_type,
                    ping_info.firmware_version,
                )
                return self._info

            except Exception as e:
                self._state = ConnectionState.ERROR
                logger.error("Handshake failed on %s: %s", port, e)
                raise ConnectionError(f"Handshake failed: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from the Pico and clean up."""
        with self._lock:
            if self._protocol is not None:
                try:
                    self._protocol.close()
                except Exception:
                    pass
                self._protocol = None
            self._info = None
            self._state = ConnectionState.DISCONNECTED
            logger.info("Pico disconnected")

    def reconnect(self) -> DeviceInfo:
        """Attempt to reconnect with retry logic.

        Disconnects first, then tries to connect up to ``reconnect_attempts`` times
        with ``reconnect_delay`` between attempts.

        Returns:
            DeviceInfo on successful reconnection.

        Raises:
            ConnectionError: If all reconnection attempts fail.
        """
        self.disconnect()

        last_error: Exception | None = None
        for attempt in range(1, self._reconnect_attempts + 1):
            try:
                logger.info("Reconnection attempt %d/%d", attempt, self._reconnect_attempts)
                return self.connect()
            except ConnectionError as e:
                last_error = e
                if attempt < self._reconnect_attempts:
                    time.sleep(self._reconnect_delay)

        raise ConnectionError(
            f"Failed to reconnect after {self._reconnect_attempts} attempts: {last_error}"
        )

    def ensure_connected(self) -> DeviceInfo:
        """Ensure the device is connected, reconnecting if needed.

        Returns:
            DeviceInfo for the connected device.
        """
        if self.is_connected:
            # Verify connection is still alive
            try:
                self._protocol.ping()  # type: ignore[union-attr]
                return self._info  # type: ignore[return-value]
            except Exception:
                logger.warning("Connection lost, attempting reconnect")

        return self.reconnect()

    def __enter__(self) -> PicoDevice:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.disconnect()
