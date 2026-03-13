"""Tests for WinEvent hello detector + app whitelist."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pywinhello.monitor.hello_detector import AppWhitelist, HelloDetector


class TestAppWhitelist:
    def test_empty_whitelist(self):
        wl = AppWhitelist()
        assert wl.apps == {}
        assert wl.auto_discover is True

    def test_from_pico_config(self):
        config = {
            "apps": {
                "MarketSpeed2.exe": True,
                "chrome.exe": False,
                "lock_screen": {"enabled": True},  # Not an app entry
            }
        }
        wl = AppWhitelist.from_pico_config(config)
        assert wl.apps["MarketSpeed2.exe"] is True
        assert wl.apps["chrome.exe"] is False
        assert "lock_screen" not in wl.apps

    def test_from_pico_config_dict_entries(self):
        config = {
            "apps": {
                "test.exe": {"enabled": True},
                "disabled.exe": {"enabled": False},
            }
        }
        wl = AppWhitelist.from_pico_config(config)
        assert wl.apps["test.exe"] is True
        assert wl.apps["disabled.exe"] is False

    def test_from_pico_config_empty(self):
        wl = AppWhitelist.from_pico_config({})
        assert wl.apps == {}

    def test_is_allowed_known_enabled(self):
        wl = AppWhitelist(apps={"test.exe": True})
        assert wl.is_allowed("test.exe") is True

    def test_is_allowed_known_disabled(self):
        wl = AppWhitelist(apps={"test.exe": False})
        assert wl.is_allowed("test.exe") is False

    def test_is_allowed_unknown_auto_discover_on(self):
        wl = AppWhitelist(auto_discover=True)
        assert wl.is_allowed("new.exe") is True

    def test_is_allowed_unknown_auto_discover_off(self):
        wl = AppWhitelist(auto_discover=False)
        assert wl.is_allowed("new.exe") is False

    def test_is_allowed_none_exe(self):
        wl = AppWhitelist(apps={"test.exe": True})
        assert wl.is_allowed(None) is True  # Conservative — allow unknown owner

    def test_add_app_new(self):
        wl = AppWhitelist()
        assert wl.add_app("new.exe") is True
        assert wl.apps["new.exe"] is True

    def test_add_app_existing(self):
        wl = AppWhitelist(apps={"existing.exe": True})
        assert wl.add_app("existing.exe") is False

    def test_add_app_disabled(self):
        wl = AppWhitelist()
        assert wl.add_app("disabled.exe", enabled=False) is True
        assert wl.apps["disabled.exe"] is False


class TestHelloDetectorInit:
    def test_default_init(self):
        on_hello = MagicMock()
        detector = HelloDetector(on_hello=on_hello)
        assert not detector.is_running
        assert detector.whitelist.auto_discover is True

    def test_custom_whitelist(self):
        on_hello = MagicMock()
        wl = AppWhitelist(apps={"test.exe": True}, auto_discover=False)
        detector = HelloDetector(on_hello=on_hello, whitelist=wl)
        assert detector.whitelist.auto_discover is False


class TestHelloDetectorHandleDialog:
    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_allowed_app_sends_hello(self, mock_dialog):
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.is_foreground.return_value = True
        mock_dialog.wait_for_dismiss.return_value = True

        on_hello = MagicMock()
        wl = AppWhitelist(apps={"test.exe": True})
        detector = HelloDetector(on_hello=on_hello, whitelist=wl)

        event = detector._handle_dialog()

        assert event.pin_sent is True
        assert event.dialog_dismissed is True
        assert event.owner_exe == "test.exe"
        on_hello.assert_called_once()

    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_disabled_app_ignored(self, mock_dialog):
        mock_dialog.get_owner_exe.return_value = "blocked.exe"

        on_hello = MagicMock()
        wl = AppWhitelist(apps={"blocked.exe": False})
        detector = HelloDetector(on_hello=on_hello, whitelist=wl)

        event = detector._handle_dialog()

        assert event.error is not None
        assert "disabled" in event.error
        on_hello.assert_not_called()

    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_new_app_auto_discovered(self, mock_dialog):
        mock_dialog.get_owner_exe.return_value = "newapp.exe"
        mock_dialog.is_foreground.return_value = True
        mock_dialog.wait_for_dismiss.return_value = True

        on_hello = MagicMock()
        on_new_app = MagicMock()
        wl = AppWhitelist(auto_discover=True)
        detector = HelloDetector(
            on_hello=on_hello, whitelist=wl, on_new_app=on_new_app
        )

        event = detector._handle_dialog()

        assert event.pin_sent is True
        on_new_app.assert_called_once_with("newapp.exe")
        assert "newapp.exe" in wl.apps

    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_focus_lost_aborts(self, mock_dialog):
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.is_foreground.return_value = False  # Can't get focus

        on_hello = MagicMock()
        wl = AppWhitelist(apps={"test.exe": True})
        detector = HelloDetector(on_hello=on_hello, whitelist=wl, focus_settle_delay=0.01)

        event = detector._handle_dialog()

        assert "lost focus" in event.error
        on_hello.assert_not_called()

    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_fingerprint_mode_escape(self, mock_dialog):
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.is_foreground.return_value = True
        # Dialog doesn't dismiss (fingerprint mode)
        mock_dialog.wait_for_dismiss.side_effect = [False, True]

        on_hello = MagicMock()
        on_escape = MagicMock()
        wl = AppWhitelist(apps={"test.exe": True})
        detector = HelloDetector(on_hello=on_hello, on_escape=on_escape, whitelist=wl)

        event = detector._handle_dialog()

        assert event.pin_sent is True
        assert event.error == "fingerprint_mode"
        on_escape.assert_called_once()

    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_hello_command_failure(self, mock_dialog):
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.is_foreground.return_value = True

        on_hello = MagicMock()
        on_hello.side_effect = RuntimeError("serial error")
        wl = AppWhitelist(apps={"test.exe": True})
        detector = HelloDetector(on_hello=on_hello, whitelist=wl)

        event = detector._handle_dialog()

        assert "serial error" in event.error

    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_none_owner_allowed(self, mock_dialog):
        """Unknown owner process should still be allowed."""
        mock_dialog.get_owner_exe.return_value = None
        mock_dialog.is_foreground.return_value = True
        mock_dialog.wait_for_dismiss.return_value = True

        on_hello = MagicMock()
        detector = HelloDetector(on_hello=on_hello)

        event = detector._handle_dialog()
        assert event.pin_sent is True


class TestHelloDetectorStartStop:
    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_start_stop(self, mock_dialog):
        mock_dialog.is_visible.return_value = False

        on_hello = MagicMock()
        detector = HelloDetector(on_hello=on_hello)

        detector.start()
        assert detector.is_running

        detector.stop()
        assert not detector.is_running

    @patch("pywinhello.monitor.hello_detector.dialog")
    def test_double_start_warns(self, mock_dialog):
        mock_dialog.is_visible.return_value = False

        on_hello = MagicMock()
        detector = HelloDetector(on_hello=on_hello)

        detector.start()
        detector.start()  # Should warn, not crash

        detector.stop()
