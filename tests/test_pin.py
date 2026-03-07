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
    def test_fingerprint_fallback(self, mock_dialog):
        mock_dialog.wait_for_dialog.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.focus.return_value = True
        mock_dialog.wait_for_dismiss.side_effect = [False, True]

        mock_kb = MagicMock()
        event = enter_pin("1234", _keyboard=mock_kb)

        assert event.pin_sent
        assert event.dialog_dismissed
        # type_text: first attempt + second attempt
        assert mock_kb.type_text.call_count == 2
        # press_key: ENTER (1st), ESCAPE (fallback), ENTER (2nd)
        assert mock_kb.press_key.call_count == 3
        mock_kb.press_key.assert_any_call("ENTER")
        mock_kb.press_key.assert_any_call("ESCAPE")

    @patch("pywinhello.pin.dialog")
    def test_both_attempts_fail(self, mock_dialog):
        mock_dialog.wait_for_dialog.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.focus.return_value = True
        mock_dialog.wait_for_dismiss.return_value = False

        mock_kb = MagicMock()
        event = enter_pin("1234", _keyboard=mock_kb)

        assert event.pin_sent
        assert not event.dialog_dismissed
        assert "still open" in event.error

    @patch("pywinhello.pin.dialog")
    def test_custom_pin_select_keys(self, mock_dialog):
        mock_dialog.wait_for_dialog.return_value = True
        mock_dialog.get_owner_exe.return_value = "test.exe"
        mock_dialog.focus.return_value = True
        mock_dialog.wait_for_dismiss.side_effect = [False, True]

        mock_kb = MagicMock()
        enter_pin("1234", pin_select_keys=["TAB", "TAB", "ENTER"], _keyboard=mock_kb)

        mock_kb.press_key.assert_any_call("TAB")
        mock_kb.press_key.assert_any_call("ENTER")
