"""HelloMonitor — WinEvent hook daemon for automatic PIN entry.

Watches for Windows Security dialog creation via SetWinEventHook
(EVENT_OBJECT_CREATE) and automatically enters the correct PIN based
on which process triggered the dialog.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import threading
import time
from collections.abc import Callable

from pywinhello import dialog
from pywinhello.models import AppConfig, AuthEvent, MonitorConfig
from pywinhello.pin import enter_pin

logger = logging.getLogger(__name__)

# Win32 event constants
_EVENT_OBJECT_CREATE = 0x8000
_WINEVENT_OUTOFCONTEXT = 0x0000

# Callback type for SetWinEventHook
_WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,  # hWinEventHook
    wintypes.DWORD,  # event
    wintypes.HWND,  # hwnd
    ctypes.c_long,  # idObject
    ctypes.c_long,  # idChild
    wintypes.DWORD,  # idEventThread
    wintypes.DWORD,  # dwmsEventTime
)


class HelloMonitor:
    """Monitors for Windows Hello dialogs and enters PINs automatically.

    Uses SetWinEventHook for instant, zero-polling detection.

    Usage::

        config = MonitorConfig(apps=[
            AppConfig(exe="MarketSpeed2.exe", pin="1234"),
        ])
        monitor = HelloMonitor(config)

        # One-shot: wait for next dialog
        event = monitor.handle_next(timeout=60.0)

        # Daemon: handle all dialogs
        monitor.serve(on_event=lambda e: print(e))
    """

    def __init__(self, config: MonitorConfig) -> None:
        self._config = config
        self._pin_map: dict[str, AppConfig] = {app.exe: app for app in config.apps}
        self._stop_event = threading.Event()
        self._hook_handle: int | None = None
        self._dialog_detected = threading.Event()

    def _get_app_config(self, exe: str | None) -> AppConfig | None:
        """Look up config for a process exe name."""
        if exe is None:
            return None
        return self._pin_map.get(exe)

    def _handle_dialog(self) -> AuthEvent:
        """Handle a detected Windows Hello dialog."""
        owner_exe = dialog.get_owner_exe()
        app_cfg = self._get_app_config(owner_exe)

        if app_cfg is None:
            logger.info("No PIN configured for %s, skipping", owner_exe)
            return AuthEvent(
                owner_exe=owner_exe,
                error=f"No PIN configured for {owner_exe}",
            )

        return enter_pin(
            pin=app_cfg.pin,
            port=self._config.hid_port,
            inter_key_delay_ms=self._config.inter_key_delay_ms,
            pin_select_keys=app_cfg.pin_select_keys,
        )

    def handle_next(self, timeout: float = 60.0) -> AuthEvent:
        """Wait for the next Windows Hello dialog and handle it.

        Blocks until a dialog appears or timeout is reached.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            AuthEvent with the outcome.
        """
        # Check if dialog is already visible
        if dialog.is_visible():
            return self._handle_dialog()

        # Set up WinEvent hook to detect dialog creation
        self._dialog_detected.clear()

        def _hook_callback(
            hook: int,
            event: int,
            hwnd: int,
            id_object: int,
            id_child: int,
            event_thread: int,
            event_time: int,
        ) -> None:
            # Check if the created window is a credential dialog
            class_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, class_buf, 256)
            if class_buf.value == dialog._CREDENTIAL_DIALOG_CLASS:
                self._dialog_detected.set()

        # Must keep reference to prevent GC
        callback = _WINEVENTPROC(_hook_callback)

        hook = ctypes.windll.user32.SetWinEventHook(
            _EVENT_OBJECT_CREATE,
            _EVENT_OBJECT_CREATE,
            0,
            callback,
            0,
            0,
            _WINEVENT_OUTOFCONTEXT,
        )
        if not hook:
            logger.error("Failed to set WinEvent hook")
            return AuthEvent(error="Failed to set WinEvent hook")

        try:
            # Pump messages until dialog detected or timeout
            start = time.time()
            msg = wintypes.MSG()
            while time.time() - start < timeout:
                if self._dialog_detected.is_set():
                    time.sleep(0.5)  # Brief settle time
                    return self._handle_dialog()

                # PeekMessage to process hook callbacks
                if ctypes.windll.user32.PeekMessageW(
                    ctypes.byref(msg),
                    0,
                    0,
                    0,
                    1,  # PM_REMOVE
                ):
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.01)

            return AuthEvent(error="Timeout waiting for dialog")

        finally:
            ctypes.windll.user32.UnhookWinEvent(hook)

    def serve(
        self,
        on_event: Callable[[AuthEvent], None] | None = None,
    ) -> None:
        """Run as a daemon, handling all Windows Hello dialogs.

        Blocks until ``stop()`` is called.

        Args:
            on_event: Optional callback invoked after each dialog is handled.
        """
        logger.info("HelloMonitor serving — press Ctrl+C to stop")
        self._stop_event.clear()

        while not self._stop_event.is_set():
            event = self.handle_next(timeout=5.0)
            if event.error and "Timeout" in event.error:
                continue  # Normal timeout, keep looping
            if on_event:
                on_event(event)

        logger.info("HelloMonitor stopped")

    def stop(self) -> None:
        """Signal the serve loop to stop."""
        self._stop_event.set()
