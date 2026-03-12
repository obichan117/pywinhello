"""Tests for serial protocol encoding/decoding."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pywinhello.serial.protocol import (
    Command,
    PingInfo,
    Response,
    SerialProtocol,
    encode_command,
    parse_ping,
    parse_response,
)


class TestEncodeCommand:
    def test_simple_command(self):
        assert encode_command(Command.PING) == b"PING\n"

    def test_command_with_payload(self):
        assert encode_command(Command.SETUP_PIN, "1234") == b"SETUP_PIN:1234\n"

    def test_type_command(self):
        assert encode_command(Command.TYPE, "hello") == b"TYPE:hello\n"

    def test_flash_command_with_size(self):
        assert encode_command(Command.FLASH, "65536") == b"FLASH:65536\n"

    def test_set_config_json(self):
        config = {"pin": "1234", "schedule": {"time": "07:45"}}
        payload = json.dumps(config, separators=(",", ":"))
        result = encode_command(Command.SET_CONFIG, payload)
        assert result == f"SET_CONFIG:{payload}\n".encode()

    def test_none_payload(self):
        assert encode_command(Command.GET_CONFIG, None) == b"GET_CONFIG\n"


class TestParseResponse:
    def test_ok(self):
        resp = parse_response("OK")
        assert resp.ok is True
        assert resp.data == ""

    def test_ok_with_data(self):
        resp = parse_response('OK:{"pin":true}')
        assert resp.ok is True
        assert resp.data == '{"pin":true}'

    def test_pong(self):
        resp = parse_response("PONG")
        assert resp.ok is True
        assert resp.data == ""

    def test_pong_v2(self):
        resp = parse_response("PONG:v2:rp2040:1.0.0")
        assert resp.ok is True
        assert resp.data == "v2:rp2040:1.0.0"

    def test_ready(self):
        resp = parse_response("READY")
        assert resp.ok is True
        assert resp.data == ""

    def test_error(self):
        resp = parse_response("ERR:Unknown command")
        assert resp.ok is False
        assert resp.data == "Unknown command"

    def test_empty(self):
        resp = parse_response("")
        assert resp.ok is False
        assert resp.data == "empty response"

    def test_whitespace_stripped(self):
        resp = parse_response("  OK  \n")
        assert resp.ok is True
        assert resp.data == ""

    def test_unknown_format(self):
        resp = parse_response("SOMETHING_ELSE")
        assert resp.ok is True
        assert resp.data == "SOMETHING_ELSE"

    def test_json_property(self):
        resp = parse_response('OK:{"key":"value"}')
        assert resp.json == {"key": "value"}

    def test_json_property_no_data(self):
        resp = parse_response("OK")
        with pytest.raises(ValueError, match="no data payload"):
            _ = resp.json


class TestParsePing:
    def test_v1_pong(self):
        resp = Response(raw="PONG", ok=True, data="")
        info = parse_ping(resp)
        assert info.protocol_version == 1
        assert info.device_type == "unknown"
        assert info.firmware_version == "0.0.0"

    def test_v2_full(self):
        resp = Response(raw="PONG:v2:rp2040:1.0.0", ok=True, data="v2:rp2040:1.0.0")
        info = parse_ping(resp)
        assert info.protocol_version == 2
        assert info.device_type == "rp2040"
        assert info.firmware_version == "1.0.0"

    def test_v2_rp2350(self):
        resp = Response(raw="PONG:v2:rp2350:2.1.0", ok=True, data="v2:rp2350:2.1.0")
        info = parse_ping(resp)
        assert info.protocol_version == 2
        assert info.device_type == "rp2350"
        assert info.firmware_version == "2.1.0"

    def test_error_response(self):
        resp = Response(raw="ERR:timeout", ok=False, data="timeout")
        with pytest.raises(ValueError, match="PING failed"):
            parse_ping(resp)

    def test_partial_v2(self):
        resp = Response(raw="PONG:rp2040", ok=True, data="rp2040")
        info = parse_ping(resp)
        assert info.device_type == "rp2040"


def _make_serial_mock(readline_value: bytes = b"OK\n") -> MagicMock:
    mock_ser = MagicMock()
    mock_ser.is_open = True
    mock_ser.readline.return_value = readline_value
    return mock_ser


class TestSerialProtocol:
    @patch("pywinhello.serial.protocol.pyserial")
    def test_send_command(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"OK\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        resp = proto.send(Command.CLEAR)

        assert resp.ok is True
        mock_ser.write.assert_called_with(b"CLEAR\n")
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_send_with_payload(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"OK\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        resp = proto.send(Command.SETUP_PIN, "9876")

        mock_ser.write.assert_called_with(b"SETUP_PIN:9876\n")
        assert resp.ok
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_send_timeout(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        with pytest.raises(TimeoutError, match="No response"):
            proto.send(Command.PING)
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_send_error_response(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"ERR:no pin configured\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        resp = proto.send(Command.HELLO)

        assert resp.ok is False
        assert resp.data == "no pin configured"
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_send_checked_raises(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"ERR:not ready\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        with pytest.raises(RuntimeError, match="HELLO failed: not ready"):
            proto.send_checked(Command.HELLO)
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_ping(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"PONG:v2:rp2040:1.2.3\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        info = proto.ping()

        assert info.protocol_version == 2
        assert info.device_type == "rp2040"
        assert info.firmware_version == "1.2.3"
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_get_config(self, mock_pyserial):
        config = {"pin": True, "schedule": {"time": "07:45"}}
        mock_ser = _make_serial_mock(f"OK:{json.dumps(config)}\n".encode())
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        result = proto.get_config()

        assert result == config
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_set_config(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"OK\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        proto.set_config({"schedule": {"time": "08:00"}})

        written = mock_ser.write.call_args[0][0].decode()
        assert written.startswith("SET_CONFIG:")
        assert "08:00" in written
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_status(self, mock_pyserial):
        status = {"uptime": 3600, "pin_configured": True}
        mock_ser = _make_serial_mock(f"OK:{json.dumps(status)}\n".encode())
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        result = proto.status()

        assert result["uptime"] == 3600
        assert result["pin_configured"] is True
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_flash_begin(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"READY\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        resp = proto.flash_begin(65536)

        assert resp.ok
        mock_ser.write.assert_called_with(b"FLASH:65536\n")
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_flash_begin_not_ready(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"ERR:busy\n")
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        with pytest.raises(RuntimeError, match="FLASH did not return READY"):
            proto.flash_begin(65536)
        proto.close()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_close_and_not_open(self, mock_pyserial):
        mock_ser = _make_serial_mock()
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        proto.close()
        mock_ser.close.assert_called_once()

    @patch("pywinhello.serial.protocol.pyserial")
    def test_send_when_closed(self, mock_pyserial):
        mock_ser = _make_serial_mock()
        mock_ser.is_open = False
        mock_pyserial.Serial.return_value = mock_ser

        proto = SerialProtocol(port="COM8")
        with pytest.raises(ConnectionError, match="not open"):
            proto.send(Command.PING)

    @patch("pywinhello.serial.protocol.pyserial")
    def test_context_manager(self, mock_pyserial):
        mock_ser = _make_serial_mock(b"OK\n")
        mock_pyserial.Serial.return_value = mock_ser

        with SerialProtocol(port="COM8") as proto:
            proto.send(Command.CLEAR)

        mock_ser.close.assert_called_once()


class TestCommandEnum:
    def test_all_v2_commands_exist(self):
        expected = {
            "PING", "GET_CONFIG", "SET_CONFIG", "SETUP_PIN", "CLEAR",
            "UNLOCK", "HELLO", "GET_LOG", "FLASH", "STATUS",
        }
        actual = {c.value for c in Command if c.value in expected}
        assert actual == expected

    def test_v1_backward_compat(self):
        assert Command.TYPE.value == "TYPE"
        assert Command.PRESS.value == "PRESS"
        assert Command.COMBO.value == "COMBO"
        assert Command.DELAY.value == "DELAY"
