"""Tests for MonitorService."""

from unittest.mock import MagicMock, patch

from pywinhello.monitor.service import MonitorService


class TestMonitorServiceInit:
    def test_defaults(self):
        service = MonitorService()
        assert service.is_armed is False
        assert service.config == {}

    def test_device_created(self):
        service = MonitorService()
        assert service.device is not None


class TestMonitorServiceLifecycle:
    @patch("pywinhello.monitor.usb_watcher.USBWatcher", autospec=True)
    def test_start_async_creates_watcher(self, mock_watcher_cls):
        service = MonitorService()
        service.start_async()

        mock_watcher_cls.assert_called_once()
        mock_watcher_cls.return_value.start.assert_called_once()
        service.stop()

    @patch("pywinhello.monitor.usb_watcher.USBWatcher", autospec=True)
    def test_stop_disarms(self, mock_watcher_cls):
        service = MonitorService()
        service.start_async()
        service.stop()

        mock_watcher_cls.return_value.stop.assert_called_once()
        assert service.is_armed is False


class TestMonitorServiceCallbacks:
    def test_on_pico_disconnect_disarms(self):
        service = MonitorService()
        service._armed = True
        service._device = MagicMock()

        service._on_pico_disconnect()

        assert service.is_armed is False
        assert service.config == {}
