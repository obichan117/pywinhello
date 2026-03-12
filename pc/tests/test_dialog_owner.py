"""Tests for dialog owner process detection."""

from unittest.mock import MagicMock, patch

from pywinhello.dialog import get_owner_exe


class TestGetOwnerExe:
    @patch("pywinhello.dialog.find_dialog_hwnd", return_value=0)
    def test_no_dialog(self, _mock):
        assert get_owner_exe() is None

    @patch("pywinhello.dialog.find_dialog_hwnd", return_value=12345)
    def test_no_owner_window(self, _mock):
        with patch("ctypes.windll.user32.GetWindow", return_value=0):
            assert get_owner_exe() is None

    @patch("pywinhello.dialog.find_dialog_hwnd", return_value=12345)
    def test_successful_detection(self, _mock):
        import ctypes

        mock_user32 = MagicMock()
        mock_kernel32 = MagicMock()

        mock_user32.GetWindow.return_value = 67890  # owner hwnd

        def mock_get_thread_pid(hwnd, pid_ref):
            pid_ref._obj.value = 1234

        mock_user32.GetWindowThreadProcessId.side_effect = mock_get_thread_pid
        mock_kernel32.OpenProcess.return_value = 99  # handle

        def mock_query_name(handle, flags, buf, size_ref):
            ctypes.memmove(buf, "C:\\Program Files\\test.exe\0".encode("utf-16-le"), 52)
            size_ref._obj.value = 25
            return True

        mock_kernel32.QueryFullProcessImageNameW.side_effect = mock_query_name
        mock_kernel32.CloseHandle.return_value = True

        with (
            patch("ctypes.windll.user32", mock_user32),
            patch("ctypes.windll.kernel32", mock_kernel32),
        ):
            result = get_owner_exe(hwnd=12345)
            assert result == "test.exe"

    @patch("pywinhello.dialog.find_dialog_hwnd", return_value=12345)
    def test_open_process_failure(self, _mock):
        with (
            patch("ctypes.windll.user32.GetWindow", return_value=67890),
            patch(
                "ctypes.windll.user32.GetWindowThreadProcessId",
                side_effect=lambda hwnd, ref: setattr(ref._obj, "value", 1234),
            ),
            patch("ctypes.windll.kernel32.OpenProcess", return_value=0),
        ):
            assert get_owner_exe() is None
