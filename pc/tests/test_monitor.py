"""Tests for HelloMonitor."""

from unittest.mock import MagicMock, patch

from pywinhello.models import AppConfig, AuthEvent, MonitorConfig
from pywinhello.monitor import HelloMonitor


def _make_monitor(*apps: AppConfig, **kwargs) -> HelloMonitor:
    return HelloMonitor(MonitorConfig(apps=list(apps), **kwargs))


class TestPinMapLookup:
    def test_known_exe(self):
        mon = _make_monitor(AppConfig(exe="test.exe", pin="1234"))
        cfg = mon._get_app_config("test.exe")
        assert cfg is not None
        assert cfg.pin == "1234"

    def test_unknown_exe(self):
        mon = _make_monitor(AppConfig(exe="test.exe", pin="1234"))
        assert mon._get_app_config("other.exe") is None

    def test_none_exe(self):
        mon = _make_monitor()
        assert mon._get_app_config(None) is None


class TestHandleDialog:
    @patch("pywinhello.monitor.enter_pin")
    @patch("pywinhello.monitor.dialog")
    def test_known_app(self, mock_dialog, mock_enter):
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_enter.return_value = AuthEvent(pin_sent=True, dialog_dismissed=True)

        mon = _make_monitor(AppConfig(exe="test.exe", pin="9999"))
        event = mon._handle_dialog()

        assert event.pin_sent
        mock_enter.assert_called_once_with(
            pin="9999",
            port=None,
            inter_key_delay_ms=50,
        )

    @patch("pywinhello.monitor.enter_pin")
    @patch("pywinhello.monitor.dialog")
    def test_unknown_app_no_env_var(self, mock_dialog, mock_enter):
        """Unknown app with no PYWINHELLO_PIN → ValueError caught, returns error."""
        mock_dialog.get_owner_exe.return_value = "unknown.exe"
        mock_enter.side_effect = ValueError("No PIN provided and PYWINHELLO_PIN environment variable is not set")

        mon = _make_monitor(AppConfig(exe="test.exe", pin="1234"))
        event = mon._handle_dialog()

        assert event.owner_exe == "unknown.exe"
        assert "PYWINHELLO_PIN" in event.error

    @patch("pywinhello.monitor.enter_pin")
    @patch("pywinhello.monitor.dialog")
    def test_custom_hid_port(self, mock_dialog, mock_enter):
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_enter.return_value = AuthEvent()

        mon = _make_monitor(AppConfig(exe="test.exe", pin="1234"), hid_port="COM5")
        mon._handle_dialog()

        mock_enter.assert_called_once()
        assert mock_enter.call_args.kwargs["port"] == "COM5"


class TestHandleNext:
    @patch("pywinhello.monitor.enter_pin")
    @patch("pywinhello.monitor.dialog")
    def test_dialog_already_visible(self, mock_dialog, mock_enter):
        mock_dialog.is_visible.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_enter.return_value = AuthEvent(pin_sent=True, dialog_dismissed=True)

        mon = _make_monitor(AppConfig(exe="test.exe", pin="1234"))
        event = mon.handle_next(timeout=1.0)

        assert event.pin_sent


class TestServe:
    def test_stop_exits_loop(self):
        """serve() exits when stop() is called from handle_next."""
        mon = _make_monitor()

        def fake_handle_next(timeout=60.0):
            mon.stop()
            return AuthEvent(error="Timeout waiting for dialog")

        mon.handle_next = fake_handle_next  # type: ignore[method-assign]
        mon.serve()  # Should return without blocking

    def test_on_event_callback(self):
        """on_event callback is called for non-timeout events."""
        mon = _make_monitor(AppConfig(exe="test.exe", pin="1234"))
        callback = MagicMock()

        call_count = 0

        def fake_handle_next(timeout=60.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return AuthEvent(pin_sent=True, dialog_dismissed=True, owner_exe="test.exe")
            mon.stop()
            return AuthEvent(error="Timeout waiting for dialog")

        mon.handle_next = fake_handle_next  # type: ignore[method-assign]
        mon.serve(on_event=callback)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert event.pin_sent

    def test_timeout_events_skipped(self):
        """Timeout events don't trigger on_event callback."""
        mon = _make_monitor()
        call_count = 0

        def fake_handle_next(timeout=60.0):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                mon.stop()
            return AuthEvent(error="Timeout waiting for dialog")

        mon.handle_next = fake_handle_next  # type: ignore[method-assign]
        callback = MagicMock()
        mon.serve(on_event=callback)

        callback.assert_not_called()
        assert call_count == 3
