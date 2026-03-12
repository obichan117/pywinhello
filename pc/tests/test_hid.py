"""Tests for HIDKeyboard serial protocol."""

from unittest.mock import MagicMock, patch

import pytest


def _make_serial_mock(readline_value: bytes = b"OK\n") -> MagicMock:
    mock_ser = MagicMock()
    mock_ser.is_open = True
    mock_ser.readline.return_value = readline_value
    return mock_ser


@pytest.fixture
def _mock_serial(monkeypatch):
    import sys

    mock_mod = MagicMock()
    mock_tools_mod = MagicMock()
    monkeypatch.setitem(sys.modules, "serial", mock_mod)
    monkeypatch.setitem(sys.modules, "serial.tools", mock_mod.tools)
    monkeypatch.setitem(sys.modules, "serial.tools.list_ports", mock_tools_mod)
    monkeypatch.delitem(sys.modules, "pywinhello.hid", raising=False)
    return mock_mod


@pytest.fixture
def reload_hid(_mock_serial):
    import importlib

    import pywinhello.hid

    importlib.reload(pywinhello.hid)
    return pywinhello.hid.HIDKeyboard, _mock_serial


class TestHIDKeyboard:
    def test_auto_detect_not_found(self, reload_hid):
        HIDKb, _ = reload_hid
        with (
            patch("pywinhello.hid.find_pico_port", return_value=None),
            pytest.raises(ConnectionError, match="Pico not found"),
        ):
            HIDKb()

    def test_send_protocol(self, reload_hid):
        HIDKb, mock_serial = reload_hid
        mock_ser = _make_serial_mock()
        mock_serial.Serial.return_value = mock_ser

        with HIDKb(port="COM3") as kb:
            kb.type_text("1234")
            mock_ser.write.assert_called_with(b"TYPE:1234\n")

            kb.press_key("ENTER")
            mock_ser.write.assert_called_with(b"PRESS:ENTER\n")

    def test_ping(self, reload_hid):
        HIDKb, mock_serial = reload_hid
        mock_ser = _make_serial_mock(b"PONG\n")
        mock_serial.Serial.return_value = mock_ser

        kb = HIDKb(port="COM3")
        assert kb.ping() is True
        kb.close()

    def test_error_response(self, reload_hid):
        HIDKb, mock_serial = reload_hid
        mock_ser = _make_serial_mock(b"ERR:Unknown key: FOO\n")
        mock_serial.Serial.return_value = mock_ser

        kb = HIDKb(port="COM3")
        with pytest.raises(RuntimeError, match="Unknown key: FOO"):
            kb.press_key("FOO")
        kb.close()

    def test_timeout_response(self, reload_hid):
        HIDKb, mock_serial = reload_hid
        mock_ser = _make_serial_mock(b"")
        mock_serial.Serial.return_value = mock_ser

        kb = HIDKb(port="COM3")
        with pytest.raises(TimeoutError, match="No response"):
            kb.press_key("ENTER")
        kb.close()
