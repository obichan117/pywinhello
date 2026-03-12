"""Tests for Windows Security dialog detection."""

from unittest.mock import patch

from pywinhello import dialog


class TestDialogDetection:
    @patch("ctypes.windll.user32.FindWindowW", return_value=12345)
    def test_is_visible_true(self, _mock):
        assert dialog.is_visible() is True

    @patch("ctypes.windll.user32.FindWindowW", return_value=0)
    def test_is_visible_false(self, _mock):
        assert dialog.is_visible() is False

    @patch("pywinhello.dialog.is_visible")
    def test_wait_for_dialog_immediate(self, mock_visible):
        mock_visible.return_value = True
        assert dialog.wait_for_dialog(timeout=1.0) is True

    @patch("pywinhello.dialog.is_visible")
    def test_wait_for_dialog_timeout(self, mock_visible):
        mock_visible.return_value = False
        assert dialog.wait_for_dialog(timeout=0.1, poll_interval=0.05) is False

    @patch("pywinhello.dialog.is_visible")
    def test_wait_for_dismiss(self, mock_visible):
        mock_visible.return_value = False
        assert dialog.wait_for_dismiss(timeout=1.0) is True

    @patch("pywinhello.dialog.is_visible")
    def test_wait_for_dismiss_timeout(self, mock_visible):
        mock_visible.return_value = True
        assert dialog.wait_for_dismiss(timeout=0.1, poll_interval=0.05) is False
