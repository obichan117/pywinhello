"""Tests for PIN entry orchestration."""

from unittest.mock import MagicMock, patch

from pywinhello.pin import enter_pin


class TestEnterPin:
    @patch("pywinhello.pin.dialog")
    def test_dialog_not_found(self, mock_dialog):
        mock_dialog.wait_for_dialog.return_value = False
        event = enter_pin("1234", _keyboard=MagicMock())
        assert event.error == "Windows Security dialog not found"
        assert not event.pin_sent

    @patch("pywinhello.pin.dialog")
    def test_pin_mode_success(self, mock_dialog):
        mock_dialog.wait_for_dialog.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.focus.return_value = True
        mock_dialog.wait_for_dismiss.return_value = True

        mock_kb = MagicMock()
        event = enter_pin("1234", _keyboard=mock_kb)

        assert event.pin_sent
        assert event.dialog_dismissed
        assert event.owner_exe == "test.exe"
        mock_kb.type_text.assert_called_once_with("1234")
        assert mock_kb.press_key.call_count == 1
        mock_kb.press_key.assert_called_with("ENTER")

    @patch("pywinhello.pin.dialog")
    def test_fingerprint_mode_sends_escape(self, mock_dialog):
        mock_dialog.wait_for_dialog.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.focus.return_value = True
        mock_dialog.is_foreground.return_value = True
        mock_dialog.wait_for_dismiss.side_effect = [False, True]

        mock_kb = MagicMock()
        event = enter_pin("1234", _keyboard=mock_kb)

        assert event.pin_sent
        assert event.error == "fingerprint_mode"
        mock_kb.type_text.assert_called_once_with("1234")
        mock_kb.press_key.assert_any_call("ENTER")
        mock_kb.press_key.assert_any_call("ESCAPE")

    @patch("pywinhello.pin.dialog")
    def test_focus_lost_aborts_without_typing(self, mock_dialog):
        """If another window steals focus, PIN must NOT be typed."""
        mock_dialog.wait_for_dialog.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.focus.return_value = True
        mock_dialog.is_foreground.return_value = False  # focus stolen

        mock_kb = MagicMock()
        event = enter_pin("1234", _keyboard=mock_kb)

        assert not event.pin_sent
        assert "lost focus" in event.error
        mock_kb.type_text.assert_not_called()

    @patch("pywinhello.pin.dialog")
    def test_focus_lost_then_recovered(self, mock_dialog):
        """If focus is lost but recovered on retry, PIN should be sent."""
        mock_dialog.wait_for_dialog.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.focus.return_value = True
        # First check fails, second (after re-focus) succeeds, third (final gate) succeeds
        mock_dialog.is_foreground.side_effect = [False, True, True]
        mock_dialog.wait_for_dismiss.return_value = True

        mock_kb = MagicMock()
        event = enter_pin("1234", _keyboard=mock_kb)

        assert event.pin_sent
        assert event.dialog_dismissed
        assert event.error is None
