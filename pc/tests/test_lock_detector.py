"""Tests for lock detection — mock ctypes/Win32 APIs."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from pywinhello.monitor.lock_detector import (
    LockConfig,
    LockDetector,
    UnlockMode,
    is_desktop_locked,
)


class TestLockConfig:
    def test_defaults(self):
        config = LockConfig()
        assert config.enabled is True
        assert config.mode == UnlockMode.ALWAYS
        assert config.retry_count == 3

    def test_from_pico_config_basic(self):
        config = LockConfig.from_pico_config({
            "apps": {"lock_screen": {"enabled": True, "mode": "always"}},
            "timing": {"wake_wait_sec": 5.0, "retry_count": 5},
        })
        assert config.enabled is True
        assert config.mode == UnlockMode.ALWAYS
        assert config.wake_wait_sec == 5.0
        assert config.retry_count == 5

    def test_from_pico_config_disabled(self):
        config = LockConfig.from_pico_config({
            "apps": {"lock_screen": False},
        })
        assert config.enabled is False

    def test_from_pico_config_scheduled_only(self):
        config = LockConfig.from_pico_config({
            "apps": {"lock_screen": {"enabled": True, "mode": "scheduled_only"}},
        })
        assert config.mode == UnlockMode.SCHEDULED_ONLY

    def test_from_pico_config_empty(self):
        config = LockConfig.from_pico_config({})
        assert config.enabled is True  # Default
        assert config.mode == UnlockMode.ALWAYS

    def test_from_pico_config_invalid_mode(self):
        config = LockConfig.from_pico_config({
            "apps": {"lock_screen": {"mode": "invalid_mode"}},
        })
        assert config.mode == UnlockMode.ALWAYS  # Fallback


class TestIsDesktopLocked:
    @patch("pywinhello.monitor.lock_detector.sys")
    def test_non_windows(self, mock_sys):
        mock_sys.platform = "linux"
        assert is_desktop_locked() is False

    @patch("pywinhello.monitor.lock_detector.sys")
    def test_windows_unlocked(self, mock_sys):
        mock_sys.platform = "win32"
        mock_ctypes = MagicMock()
        # OpenInputDesktop returns non-zero handle (desktop is accessible)
        mock_ctypes.windll.user32.OpenInputDesktop.return_value = 12345

        with patch("pywinhello.monitor.lock_detector.ctypes", mock_ctypes):
            assert is_desktop_locked() is False
            mock_ctypes.windll.user32.CloseDesktop.assert_called_with(12345)

    @patch("pywinhello.monitor.lock_detector.sys")
    def test_windows_locked(self, mock_sys):
        mock_sys.platform = "win32"
        mock_ctypes = MagicMock()
        # OpenInputDesktop returns 0 (locked)
        mock_ctypes.windll.user32.OpenInputDesktop.return_value = 0

        with patch("pywinhello.monitor.lock_detector.ctypes", mock_ctypes):
            assert is_desktop_locked() is True

    @patch("pywinhello.monitor.lock_detector.sys")
    def test_exception_returns_false(self, mock_sys):
        mock_sys.platform = "win32"
        mock_ctypes = MagicMock()
        mock_ctypes.windll.user32.OpenInputDesktop.side_effect = OSError("access denied")
        with patch("pywinhello.monitor.lock_detector.ctypes", mock_ctypes):
            # Should not raise, returns False
            assert is_desktop_locked() is False


class TestLockDetector:
    def test_disabled_config_skips_start(self):
        protocol = MagicMock()
        config = LockConfig(enabled=False)
        detector = LockDetector(protocol, config)

        detector.start()
        assert not detector.is_running

    def test_start_stop(self):
        protocol = MagicMock()
        config = LockConfig(enabled=True)
        detector = LockDetector(protocol, config)

        with patch("pywinhello.monitor.lock_detector.is_desktop_locked", return_value=False):
            detector.start()
            assert detector.is_running
            detector.stop()
            assert not detector.is_running

    @patch("pywinhello.monitor.lock_detector.is_desktop_locked")
    def test_lock_triggers_unlock(self, mock_locked):
        protocol = MagicMock()
        config = LockConfig(
            enabled=True,
            mode=UnlockMode.ALWAYS,
            wake_wait_sec=0.01,
            retry_interval_sec=0.01,
            retry_count=1,
        )

        # Sequence: not locked, then locked, then unlocked
        mock_locked.side_effect = [False, True, False, False, False, False, False, False]

        detector = LockDetector(protocol, config, poll_interval=0.02)
        detector.start()
        time.sleep(0.5)
        detector.stop()

        protocol.unlock.assert_called()

    @patch("pywinhello.monitor.lock_detector.is_desktop_locked")
    def test_scheduled_only_mode_blocks(self, mock_locked):
        """In scheduled_only mode with no schedule times, unlock should not fire."""
        protocol = MagicMock()
        config = LockConfig(
            enabled=True,
            mode=UnlockMode.SCHEDULED_ONLY,
            wake_wait_sec=0.01,
        )

        mock_locked.side_effect = [False, True, True, True, True, True, True, True]

        detector = LockDetector(protocol, config, schedule_times=[], poll_interval=0.02)
        detector.start()
        time.sleep(0.3)
        detector.stop()

        protocol.unlock.assert_not_called()

    def test_trigger_unlock_disabled(self):
        protocol = MagicMock()
        config = LockConfig(enabled=False)
        detector = LockDetector(protocol, config)

        detector.trigger_unlock()
        protocol.unlock.assert_not_called()

    @patch("pywinhello.monitor.lock_detector.is_desktop_locked")
    def test_retry_on_failure(self, mock_locked):
        protocol = MagicMock()
        protocol.unlock.side_effect = [RuntimeError("serial error"), None]
        config = LockConfig(
            enabled=True,
            mode=UnlockMode.ALWAYS,
            wake_wait_sec=0.01,
            retry_interval_sec=0.01,
            retry_count=2,
        )

        # Lock detected, stays locked through retries, then unlocks
        mock_locked.side_effect = [False, True, True, True, False, False, False, False, False]

        detector = LockDetector(protocol, config, poll_interval=0.02)
        detector.start()
        time.sleep(0.8)
        detector.stop()

        assert protocol.unlock.call_count >= 1


class TestLockDetectorNearSchedule:
    def test_near_schedule_true(self):
        protocol = MagicMock()
        config = LockConfig(mode=UnlockMode.SCHEDULED_ONLY)
        detector = LockDetector(protocol, config, schedule_times=["07:45"])

        # Mock current time to be near 07:45
        now = time.localtime()
        current_str = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        detector._schedule_times = [current_str]
        assert detector._is_near_schedule() is True

    def test_near_schedule_false(self):
        protocol = MagicMock()
        config = LockConfig(mode=UnlockMode.SCHEDULED_ONLY)
        detector = LockDetector(protocol, config, schedule_times=["03:00"])

        # Unless it's actually 3am, this should be False
        now = time.localtime()
        current_minutes = now.tm_hour * 60 + now.tm_min
        sched_minutes = 3 * 60
        if abs(current_minutes - sched_minutes) > 5:
            assert detector._is_near_schedule() is False

    def test_near_schedule_no_times(self):
        protocol = MagicMock()
        config = LockConfig(mode=UnlockMode.SCHEDULED_ONLY)
        detector = LockDetector(protocol, config, schedule_times=[])
        assert detector._is_near_schedule() is False
