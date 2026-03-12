"""Tests for PicoDevice detection and connection lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pywinhello.serial.device import ConnectionState, DeviceInfo, PicoDevice
from pywinhello.serial.protocol import PingInfo


def _mock_protocol(ping_response: PingInfo | None = None) -> MagicMock:
    """Create a mock SerialProtocol."""
    proto = MagicMock()
    proto.is_open = True
    if ping_response is None:
        ping_response = PingInfo(protocol_version=2, device_type="rp2040", firmware_version="1.0.0")
    proto.ping.return_value = ping_response
    return proto


class TestPicoDeviceInit:
    def test_initial_state(self):
        device = PicoDevice()
        assert device.state == ConnectionState.DISCONNECTED
        assert device.is_connected is False
        assert device.info is None

    def test_protocol_raises_when_disconnected(self):
        device = PicoDevice()
        with pytest.raises(ConnectionError, match="not connected"):
            _ = device.protocol


class TestPicoDeviceConnect:
    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_auto_detect_connect(self, mock_find, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice()
        info = device.connect()

        assert device.is_connected
        assert device.state == ConnectionState.CONNECTED
        assert info.port == "COM8"
        assert info.ping_info.protocol_version == 2
        assert info.ping_info.device_type == "rp2040"
        mock_find.assert_called_once()

    @patch("pywinhello.serial.device.SerialProtocol")
    def test_explicit_port_connect(self, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice(port="COM5")
        info = device.connect()

        assert info.port == "COM5"
        mock_proto_cls.assert_called_with(port="COM5", baud_rate=115200)

    @patch("pywinhello.serial.device.find_pico_port", return_value=None)
    def test_no_device_found(self, mock_find):
        device = PicoDevice()
        with pytest.raises(ConnectionError, match="not found"):
            device.connect()
        assert device.state == ConnectionState.ERROR

    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_handshake_failure(self, mock_find, mock_proto_cls):
        mock_proto = MagicMock()
        mock_proto.ping.side_effect = TimeoutError("No response")
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice()
        with pytest.raises(ConnectionError, match="Handshake failed"):
            device.connect()
        assert device.state == ConnectionState.ERROR

    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_v1_firmware_connect(self, mock_find, mock_proto_cls):
        """v1 firmware returns plain PONG without metadata."""
        mock_proto = _mock_protocol(
            PingInfo(protocol_version=1, device_type="unknown", firmware_version="0.0.0")
        )
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice()
        info = device.connect()

        assert info.ping_info.protocol_version == 1
        assert info.ping_info.device_type == "unknown"


class TestPicoDeviceDisconnect:
    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_disconnect(self, mock_find, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice()
        device.connect()
        device.disconnect()

        assert device.state == ConnectionState.DISCONNECTED
        assert device.info is None
        mock_proto.close.assert_called_once()

    def test_disconnect_when_not_connected(self):
        device = PicoDevice()
        device.disconnect()  # Should not raise
        assert device.state == ConnectionState.DISCONNECTED


class TestPicoDeviceReconnect:
    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_reconnect_success(self, mock_find, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice(reconnect_delay=0.01)
        device.connect()

        # Simulate reconnect
        info = device.reconnect()
        assert device.is_connected
        assert info.port == "COM8"

    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value=None)
    def test_reconnect_all_attempts_fail(self, mock_find, mock_proto_cls):
        device = PicoDevice(reconnect_attempts=2, reconnect_delay=0.01)

        with pytest.raises(ConnectionError, match="Failed to reconnect after 2 attempts"):
            device.reconnect()

    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port")
    def test_reconnect_succeeds_on_second_try(self, mock_find, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        # First attempt: no port. Second: found.
        mock_find.side_effect = [None, "COM8"]

        device = PicoDevice(reconnect_attempts=3, reconnect_delay=0.01)
        info = device.reconnect()

        assert info.port == "COM8"
        assert mock_find.call_count == 2


class TestPicoDeviceEnsureConnected:
    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_already_connected_and_alive(self, mock_find, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice()
        device.connect()

        info = device.ensure_connected()
        assert info.port == "COM8"
        # PING called twice: once in connect(), once in ensure_connected()
        assert mock_proto.ping.call_count == 2

    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_connection_lost_reconnects(self, mock_find, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        device = PicoDevice(reconnect_delay=0.01)
        device.connect()

        # Simulate connection loss on verification ping
        mock_proto.ping.side_effect = [TimeoutError("lost"), _mock_protocol().ping.return_value]
        mock_proto_cls.return_value = _mock_protocol()

        info = device.ensure_connected()
        assert device.is_connected


class TestPicoDeviceContextManager:
    @patch("pywinhello.serial.device.SerialProtocol")
    @patch("pywinhello.serial.device.find_pico_port", return_value="COM8")
    def test_context_manager(self, mock_find, mock_proto_cls):
        mock_proto = _mock_protocol()
        mock_proto_cls.return_value = mock_proto

        with PicoDevice() as device:
            assert device.is_connected

        assert device.state == ConnectionState.DISCONNECTED
        mock_proto.close.assert_called()
