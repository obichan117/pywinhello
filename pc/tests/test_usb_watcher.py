"""Tests for USB watcher — mock WMI and pyserial."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from pywinhello.monitor.usb_watcher import USBWatcher

# All patches target the imported name in usb_watcher module
_FIND_PORT = "pywinhello.monitor.usb_watcher.find_pico_port"


class TestUSBWatcherInit:
    def test_initial_state(self):
        watcher = USBWatcher()
        assert watcher.is_running is False

    def test_callbacks_stored(self):
        on_connect = MagicMock()
        on_disconnect = MagicMock()
        watcher = USBWatcher(on_connect=on_connect, on_disconnect=on_disconnect)
        assert watcher._on_connect is on_connect
        assert watcher._on_disconnect is on_disconnect


class TestUSBWatcherCheckNow:
    @patch("pywinhello.monitor.usb_watcher.find_pico_port", return_value="COM8")
    def test_device_present(self, mock_find):
        watcher = USBWatcher()
        assert watcher.check_now() == "COM8"

    @patch("pywinhello.monitor.usb_watcher.find_pico_port", return_value=None)
    def test_no_device(self, mock_find):
        watcher = USBWatcher()
        assert watcher.check_now() is None


class TestUSBWatcherPollLoop:
    @patch("pywinhello.monitor.usb_watcher.find_pico_port")
    def test_connect_callback(self, mock_find):
        """Simulate: no device -> device appears -> callback fires."""
        on_connect = MagicMock()
        # First check: no device. Second: device present.
        mock_find.side_effect = [None, "COM8"]

        watcher = USBWatcher(on_connect=on_connect, poll_interval=0.05)
        # Force poll mode (not WMI)
        watcher._stop_event = threading.Event()
        watcher._thread = threading.Thread(target=watcher._poll_watch_loop, daemon=True)
        watcher._thread.start()

        time.sleep(0.2)
        watcher.stop()

        on_connect.assert_called_with("COM8")

    @patch("pywinhello.monitor.usb_watcher.find_pico_port")
    def test_disconnect_callback(self, mock_find):
        """Simulate: device present -> device removed -> callback fires."""
        on_disconnect = MagicMock()
        # First check: device present. Second: gone.
        mock_find.side_effect = ["COM8", None]

        watcher = USBWatcher(on_disconnect=on_disconnect, poll_interval=0.05)
        watcher._stop_event = threading.Event()
        watcher._thread = threading.Thread(target=watcher._poll_watch_loop, daemon=True)
        watcher._thread.start()

        time.sleep(0.2)
        watcher.stop()

        on_disconnect.assert_called_once()

    @patch("pywinhello.monitor.usb_watcher.find_pico_port")
    def test_no_callback_when_no_change(self, mock_find):
        """No spurious callbacks when state doesn't change."""
        on_connect = MagicMock()
        on_disconnect = MagicMock()
        mock_find.return_value = None  # Always no device

        watcher = USBWatcher(
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            poll_interval=0.05,
        )
        watcher._stop_event = threading.Event()
        watcher._thread = threading.Thread(target=watcher._poll_watch_loop, daemon=True)
        watcher._thread.start()

        time.sleep(0.2)
        watcher.stop()

        on_connect.assert_not_called()
        on_disconnect.assert_not_called()

    @patch("pywinhello.monitor.usb_watcher.find_pico_port")
    def test_connect_then_disconnect(self, mock_find):
        """Full cycle: no device -> connect -> disconnect."""
        on_connect = MagicMock()
        on_disconnect = MagicMock()
        mock_find.side_effect = [None, "COM8", "COM8", None]

        watcher = USBWatcher(
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            poll_interval=0.05,
        )
        watcher._stop_event = threading.Event()
        watcher._thread = threading.Thread(target=watcher._poll_watch_loop, daemon=True)
        watcher._thread.start()

        time.sleep(0.4)
        watcher.stop()

        on_connect.assert_called_once_with("COM8")
        on_disconnect.assert_called_once()

    @patch("pywinhello.monitor.usb_watcher.find_pico_port")
    def test_callback_exception_handled(self, mock_find):
        """Callback errors don't crash the watcher."""
        on_connect = MagicMock(side_effect=RuntimeError("callback error"))
        mock_find.side_effect = [None, "COM8", "COM8"]

        watcher = USBWatcher(on_connect=on_connect, poll_interval=0.05)
        watcher._stop_event = threading.Event()
        watcher._thread = threading.Thread(target=watcher._poll_watch_loop, daemon=True)
        watcher._thread.start()

        time.sleep(0.2)
        watcher.stop()

        # Watcher should still be alive after callback error
        on_connect.assert_called()


class TestUSBWatcherStartStop:
    @patch("pywinhello.monitor.usb_watcher.find_pico_port", return_value=None)
    @patch("pywinhello.monitor.usb_watcher.sys")
    def test_start_stop(self, mock_sys, mock_find):
        mock_sys.platform = "linux"  # Force poll mode for test

        watcher = USBWatcher(poll_interval=0.05)
        watcher.start()
        assert watcher.is_running

        watcher.stop()
        assert not watcher.is_running

    @patch("pywinhello.monitor.usb_watcher.find_pico_port", return_value=None)
    @patch("pywinhello.monitor.usb_watcher.sys")
    def test_double_start_no_error(self, mock_sys, mock_find):
        mock_sys.platform = "linux"

        watcher = USBWatcher(poll_interval=0.05)
        watcher.start()
        watcher.start()  # Should warn but not crash
        watcher.stop()
