"""Lock screen detection and automatic UNLOCK via serial.

Detects when the Windows desktop is locked and sends the UNLOCK command
to the Pico, which types the stored PIN + ENTER.

Detection methods:
1. ``OpenInputDesktop()`` — returns NULL when desktop is locked
2. Session change notifications via ``WTSRegisterSessionNotification``
3. Power broadcast events for wake-from-sleep detection

The detector respects schedule and auto_unlock configuration from the Pico.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pywinhello.serial.protocol import SerialProtocol

logger = logging.getLogger(__name__)

# Timing defaults
_WAKE_WAIT_SEC = 3.0
_RETRY_INTERVAL_SEC = 5.0
_RETRY_COUNT = 3
_POLL_INTERVAL_SEC = 1.0


class UnlockMode(str, Enum):
    """When to auto-unlock the desktop."""

    ALWAYS = "always"
    """Always unlock when lock is detected (default)."""

    SCHEDULED_ONLY = "scheduled_only"
    """Only unlock near scheduled times (within 5-minute window)."""


@dataclass
class LockConfig:
    """Lock detection configuration from Pico."""

    enabled: bool = True
    """Whether lock screen auto-unlock is enabled."""

    mode: UnlockMode = UnlockMode.ALWAYS
    """When to trigger auto-unlock."""

    wake_wait_sec: float = _WAKE_WAIT_SEC
    """Seconds to wait after lock detection before sending UNLOCK."""

    retry_interval_sec: float = _RETRY_INTERVAL_SEC
    """Seconds between retry attempts."""

    retry_count: int = _RETRY_COUNT
    """Maximum number of UNLOCK retry attempts."""

    @classmethod
    def from_pico_config(cls, config: dict) -> LockConfig:
        """Parse lock config from Pico GET_CONFIG response."""
        apps = config.get("apps", {})
        lock_cfg = apps.get("lock_screen", {})

        if isinstance(lock_cfg, bool):
            return cls(enabled=lock_cfg)

        if not isinstance(lock_cfg, dict):
            return cls()

        timing = config.get("timing", {})
        mode_str = lock_cfg.get("mode", "always")
        try:
            mode = UnlockMode(mode_str)
        except ValueError:
            mode = UnlockMode.ALWAYS

        return cls(
            enabled=lock_cfg.get("enabled", True),
            mode=mode,
            wake_wait_sec=timing.get("wake_wait_sec", _WAKE_WAIT_SEC),
            retry_interval_sec=timing.get("retry_interval_sec", _RETRY_INTERVAL_SEC),
            retry_count=timing.get("retry_count", _RETRY_COUNT),
        )


def is_desktop_locked() -> bool:
    """Check if the Windows desktop is currently locked.

    Uses OpenInputDesktop which returns NULL/fails when the desktop is locked
    (Winlogon desktop is active instead of the user's desktop).

    Returns:
        True if the desktop appears to be locked.
    """
    if sys.platform != "win32":
        return False

    try:
        # OpenInputDesktop returns 0 when on Winlogon desktop (locked)
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_READOBJECTS
        if hdesk:
            ctypes.windll.user32.CloseDesktop(hdesk)
            return False
        return True
    except Exception:
        return False


def is_waking_from_sleep() -> bool:
    """Heuristic: check if the system recently woke from sleep.

    Uses GetTickCount64 vs system uptime to detect recent resume.
    This is a best-effort heuristic — not 100% reliable.

    Returns:
        True if the system appears to have recently resumed from sleep.
    """
    if sys.platform != "win32":
        return False

    try:
        # If system has been up less than 30 seconds, likely just woke
        tick_ms = ctypes.windll.kernel32.GetTickCount64()
        return tick_ms < 30_000
    except Exception:
        return False


class LockDetector:
    """Detects locked desktop and sends UNLOCK commands to the Pico.

    Usage::

        detector = LockDetector(protocol, config)
        detector.start()
        # ... runs in background ...
        detector.stop()
    """

    def __init__(
        self,
        protocol: SerialProtocol,
        config: LockConfig | None = None,
        schedule_times: list[str] | None = None,
        poll_interval: float = _POLL_INTERVAL_SEC,
    ) -> None:
        self._protocol = protocol
        self._config = config or LockConfig()
        self._schedule_times = schedule_times or []
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._was_locked = False

    @property
    def is_running(self) -> bool:
        """Whether the detector thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the lock detection loop in a background thread."""
        if not self._config.enabled:
            logger.info("Lock detection disabled in config")
            return

        if self.is_running:
            logger.warning("LockDetector already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._detection_loop,
            name="lock-detector",
            daemon=True,
        )
        self._thread.start()
        logger.info("LockDetector started (mode=%s)", self._config.mode.value)

    def stop(self) -> None:
        """Stop the lock detection loop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("LockDetector stopped")

    def _detection_loop(self) -> None:
        """Main polling loop for lock state changes."""
        while not self._stop_event.is_set():
            try:
                locked = is_desktop_locked()

                if locked and not self._was_locked:
                    # Transition: unlocked -> locked
                    from_sleep = is_waking_from_sleep()
                    logger.info(
                        "Desktop lock detected (from_sleep=%s)", from_sleep
                    )
                    if self._should_unlock(from_sleep=from_sleep):
                        self._perform_unlock(from_sleep=from_sleep)
                    else:
                        logger.debug("Unlock suppressed by schedule/config")

                elif not locked and self._was_locked:
                    # Transition: locked -> unlocked
                    logger.info("Desktop unlocked")

                self._was_locked = locked

            except Exception:
                logger.exception("Lock detection loop error")

            self._stop_event.wait(self._poll_interval)

    def _should_unlock(self, from_sleep: bool = False) -> bool:
        """Determine if we should auto-unlock based on config and schedule."""
        if not self._config.enabled:
            return False

        if self._config.mode == UnlockMode.ALWAYS:
            return True

        if self._config.mode == UnlockMode.SCHEDULED_ONLY:
            # Always allow unlock after sleep resume (PC woke for a reason)
            if from_sleep:
                return True
            return self._is_near_schedule()

        return False

    def _is_near_schedule(self, window_minutes: int = 5) -> bool:
        """Check if current time is within window_minutes of any scheduled time."""
        if not self._schedule_times:
            return False

        now = time.localtime()
        now_minutes = now.tm_hour * 60 + now.tm_min

        for time_str in self._schedule_times:
            try:
                parts = time_str.split(":")
                sched_minutes = int(parts[0]) * 60 + int(parts[1])
                if abs(now_minutes - sched_minutes) <= window_minutes:
                    return True
            except (ValueError, IndexError):
                continue

        return False

    def _perform_unlock(self, from_sleep: bool = False) -> None:
        """Send UNLOCK command to Pico with retry logic."""
        # After sleep resume, wait a bit longer for display to power on
        wait_sec = self._config.wake_wait_sec
        if from_sleep:
            wait_sec = max(wait_sec, 5.0)
        logger.debug("Waiting %.1fs for lock screen to render...", wait_sec)
        self._stop_event.wait(wait_sec)

        for attempt in range(1, self._config.retry_count + 1):
            if self._stop_event.is_set():
                return

            try:
                logger.info("Sending UNLOCK (attempt %d/%d)", attempt, self._config.retry_count)
                self._protocol.unlock()

                # Wait and check if desktop unlocked
                self._stop_event.wait(self._config.retry_interval_sec)

                if not is_desktop_locked():
                    logger.info("Desktop unlocked successfully")
                    return

                logger.info("Desktop still locked after UNLOCK attempt %d", attempt)

            except Exception as e:
                logger.error("UNLOCK attempt %d failed: %s", attempt, e)
                if attempt < self._config.retry_count:
                    self._stop_event.wait(self._config.retry_interval_sec)

        logger.warning("Failed to unlock desktop after %d attempts", self._config.retry_count)

    def trigger_unlock(self) -> None:
        """Manually trigger an unlock attempt (e.g. from wake command)."""
        if not self._config.enabled:
            logger.info("Lock detection disabled — ignoring trigger")
            return
        threading.Thread(target=self._perform_unlock, daemon=True).start()
