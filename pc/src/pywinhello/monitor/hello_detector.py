"""Refactored Windows Hello dialog detection with per-app whitelist filtering.

Reuses the WinEvent hook pattern from v1 ``monitor.py`` but:
1. Sends HELLO serial command instead of typing PIN directly
2. Filters by per-app whitelist from Pico config
3. Auto-discovers new apps and adds them to config

The core WinEvent + focus guard logic is preserved from v1.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pywinhello import dialog
from pywinhello.models import AuthEvent

if TYPE_CHECKING:
    from pywinhello.serial.protocol import SerialProtocol

logger = logging.getLogger(__name__)


@dataclass
class AppWhitelist:
    """Per-app whitelist configuration from Pico.

    Maps executable names to enabled/disabled state.
    """

    apps: dict[str, bool] = field(default_factory=dict)
    """Map of exe name -> enabled flag."""

    auto_discover: bool = True
    """Whether to auto-add new apps as enabled."""

    @classmethod
    def from_pico_config(cls, config: dict) -> AppWhitelist:
        """Parse app whitelist from Pico GET_CONFIG response."""
        apps_cfg = config.get("apps", {})

        # Extract app entries (skip non-app keys like 'lock_screen')
        apps: dict[str, bool] = {}
        for key, value in apps_cfg.items():
            if key == "lock_screen":
                continue
            if isinstance(value, bool):
                apps[key] = value
            elif isinstance(value, dict):
                apps[key] = value.get("enabled", True)

        return cls(
            apps=apps,
            auto_discover=apps_cfg.get("auto_discover", True),
        )

    def is_allowed(self, exe: str | None) -> bool:
        """Check if an app is in the whitelist and enabled.

        Unknown apps are allowed if auto_discover is True.
        """
        if exe is None:
            return True  # Unknown owner — allow (conservative)

        if exe in self.apps:
            return self.apps[exe]

        # Not in whitelist — allow if auto-discover is on
        return self.auto_discover

    def add_app(self, exe: str, enabled: bool = True) -> bool:
        """Add a new app to the whitelist.

        Returns:
            True if the app was newly added, False if it already existed.
        """
        if exe in self.apps:
            return False
        self.apps[exe] = enabled
        return True


class HelloDetector:
    """Detects Windows Hello dialogs and sends HELLO commands to the Pico.

    Refactored from v1 HelloMonitor to use serial HELLO command instead of
    directly typing PIN via HID. Adds per-app whitelist filtering.

    Usage::

        detector = HelloDetector(protocol, whitelist)
        detector.start()
        # ... runs in background ...
        detector.stop()
    """

    def __init__(
        self,
        protocol: SerialProtocol,
        whitelist: AppWhitelist | None = None,
        on_event: Any | None = None,
        on_new_app: Any | None = None,
        dismiss_timeout: float = 5.0,
        focus_settle_delay: float = 0.3,
    ) -> None:
        self._protocol = protocol
        self._whitelist = whitelist or AppWhitelist()
        self._on_event = on_event
        self._on_new_app = on_new_app
        self._dismiss_timeout = dismiss_timeout
        self._focus_settle_delay = focus_settle_delay
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """Whether the detector thread is active."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def whitelist(self) -> AppWhitelist:
        """Current app whitelist."""
        return self._whitelist

    def start(self) -> None:
        """Start the WinEvent hook detection loop in a background thread."""
        if self.is_running:
            logger.warning("HelloDetector already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._detection_loop,
            name="hello-detector",
            daemon=True,
        )
        self._thread.start()
        logger.info("HelloDetector started (%d apps in whitelist)", len(self._whitelist.apps))

    def stop(self) -> None:
        """Stop the detection loop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
        logger.info("HelloDetector stopped")

    def _detection_loop(self) -> None:
        """Main loop — uses WinEvent hook via handle_next pattern from v1."""
        while not self._stop_event.is_set():
            try:
                event = self._handle_next(timeout=5.0)

                if event.error and "Timeout" in event.error:
                    continue  # Normal timeout, keep looping

                if self._on_event:
                    try:
                        self._on_event(event)
                    except Exception:
                        logger.exception("on_event callback error")

            except Exception:
                logger.exception("Hello detection loop error")
                time.sleep(1.0)

    def _handle_next(self, timeout: float = 60.0) -> AuthEvent:
        """Wait for the next Windows Hello dialog and handle it.

        Uses polling-based detection (simplified from v1 WinEvent hook
        to avoid ctypes callback GC issues in long-running daemon).

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            AuthEvent with the outcome.
        """
        # Check if dialog is already visible
        if dialog.is_visible():
            return self._handle_dialog()

        # Poll for dialog appearance
        start = time.time()
        while time.time() - start < timeout:
            if self._stop_event.is_set():
                return AuthEvent(error="Stopped")

            if dialog.is_visible():
                time.sleep(0.5)  # Brief settle time
                return self._handle_dialog()

            time.sleep(0.1)

        return AuthEvent(error="Timeout waiting for dialog")

    def _handle_dialog(self) -> AuthEvent:
        """Handle a detected Windows Hello dialog.

        1. Identify owner process
        2. Check app whitelist
        3. If allowed: focus dialog, send HELLO command
        4. Handle fingerprint mode (ESCAPE fallback)
        5. Auto-discover new apps
        """
        event = AuthEvent()
        start = time.time()

        # Identify owner process
        owner_exe = dialog.get_owner_exe()
        event.owner_exe = owner_exe

        # Auto-discover new apps
        if owner_exe and self._whitelist.add_app(owner_exe):
            logger.info("New app detected: %s (enabled)", owner_exe)
            if self._on_new_app:
                try:
                    self._on_new_app(owner_exe)
                except Exception:
                    logger.exception("on_new_app callback error")

        # Check whitelist
        if not self._whitelist.is_allowed(owner_exe):
            event.error = f"App '{owner_exe}' disabled in whitelist"
            event.elapsed = time.time() - start
            logger.info("Ignoring dialog from disabled app: %s", owner_exe)
            return event

        # Focus the dialog (3-layer verification from v1)
        dialog.focus()
        time.sleep(self._focus_settle_delay)

        if not dialog.is_foreground():
            dialog.focus()
            time.sleep(self._focus_settle_delay)
            if not dialog.is_foreground():
                event.error = "credential dialog lost focus — aborting"
                event.elapsed = time.time() - start
                logger.warning(event.error)
                return event

        # Final focus gate right before sending command
        if not dialog.is_foreground():
            event.error = "credential dialog lost focus — aborting"
            event.elapsed = time.time() - start
            logger.warning(event.error)
            return event

        try:
            # Send HELLO command — Pico types the stored PIN (no ENTER)
            self._protocol.hello()
            event.pin_sent = True

            if dialog.wait_for_dismiss(timeout=self._dismiss_timeout):
                event.dialog_dismissed = True
                logger.info("Windows Hello PIN accepted for %s", owner_exe)
            else:
                # Dialog still open — likely fingerprint mode
                # Send ESCAPE to close, caller will retry
                logger.info("Dialog still open (fingerprint mode?) — closing with ESCAPE")
                try:
                    # Use protocol to send ESCAPE via Pico
                    from pywinhello.serial.protocol import Command

                    self._protocol.send(Command.PRESS, "ESCAPE")
                except Exception:
                    logger.debug("ESCAPE via serial failed, dialog may close on its own")

                dialog.wait_for_dismiss(timeout=3.0)
                event.error = "fingerprint_mode"

        except Exception as e:
            event.error = str(e)
            logger.error("HELLO command failed: %s", e)

        event.elapsed = time.time() - start
        return event
