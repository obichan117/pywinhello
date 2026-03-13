"""WMI-based USB plug/unplug detection for Pico devices.

Uses Win32_DeviceChangeEvent (or __InstanceOperationEvent on Win32_PnPEntity)
to detect USB device insertion and removal without polling.

On non-Windows platforms, falls back to a polling-based approach using pyserial
port enumeration (for development/testing).
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from pywinhello.models import PICO_VID
from pywinhello.serial.device import find_pico_port

logger = logging.getLogger(__name__)

# VID:PID match string for WMI queries (VID from models.py — single source of truth)
_PICO_VID_HEX = f"VID_{PICO_VID:04X}"


class USBWatcher:
    """Watches for Pico USB plug/unplug events.

    Uses WMI on Windows for callback-based event detection.
    Falls back to polling on non-Windows platforms.

    Usage::

        def on_connect(port: str) -> None:
            print(f"Pico connected on {port}")

        def on_disconnect() -> None:
            print("Pico disconnected")

        watcher = USBWatcher(on_connect=on_connect, on_disconnect=on_disconnect)
        watcher.start()
        # ... later ...
        watcher.stop()
    """

    def __init__(
        self,
        on_connect: Callable[[str], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
        poll_interval: float = 2.0,
    ) -> None:
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_port: str | None = None
        self._wmi_watcher: Any = None

    @property
    def is_running(self) -> bool:
        """Whether the watcher thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start watching for USB events in a background thread."""
        if self.is_running:
            logger.warning("USBWatcher already running")
            return

        self._stop_event.clear()

        if sys.platform == "win32":
            self._thread = threading.Thread(
                target=self._wmi_watch_loop,
                name="usb-watcher",
                daemon=True,
            )
        else:
            self._thread = threading.Thread(
                target=self._poll_watch_loop,
                name="usb-watcher-poll",
                daemon=True,
            )

        self._thread.start()
        logger.info("USBWatcher started")

    def stop(self) -> None:
        """Stop watching for USB events."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("USBWatcher stopped")

    def check_now(self) -> str | None:
        """Check if a Pico is currently connected.

        Returns:
            COM port name if found, None otherwise.
        """
        return find_pico_port()

    def _wmi_watch_loop(self) -> None:
        """Watch for USB events using WMI (Windows only)."""
        try:
            import pythoncom

            pythoncom.CoInitialize()
            try:
                self._wmi_watch_inner()
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            logger.warning("pythoncom not available, falling back to polling")
            self._poll_watch_loop()

    def _wmi_watch_inner(self) -> None:
        """Inner WMI watch loop (COM already initialized)."""
        try:
            import wmi

            c = wmi.WMI()

            # Watch for device change events
            # EventType: 2 = device arrival, 3 = device removal
            watcher = c.watch_for(
                notification_type="operation",
                wmi_class="Win32_PnPEntity",
                delay_secs=1,
            )
            self._wmi_watcher = watcher

            # Check initial state
            self._check_and_notify()

            while not self._stop_event.is_set():
                try:
                    event = watcher(timeout_ms=int(self._poll_interval * 1000))
                    # A PnP event occurred — check if it's our device
                    device_id = getattr(event, "DeviceID", "") or ""
                    if _PICO_VID_HEX in device_id.upper():
                        logger.debug("WMI PnP event for Pico device: %s", device_id)
                        # Brief delay for port enumeration to catch up
                        time.sleep(0.5)
                        self._check_and_notify()
                except Exception as e:
                    err_str = str(e)
                    if "timed out" in err_str.lower() or "x_wmi_timed_out" in err_str.lower():
                        # Normal timeout — check state periodically as safety net
                        self._check_and_notify()
                    else:
                        logger.error("WMI watch error: %s", e)
                        time.sleep(1.0)

        except Exception as e:
            logger.error("WMI watcher failed: %s, falling back to polling", e)
            self._poll_watch_loop()

    def _poll_watch_loop(self) -> None:
        """Fallback polling-based watch loop."""
        # Check initial state
        self._check_and_notify()

        while not self._stop_event.is_set():
            self._stop_event.wait(self._poll_interval)
            if not self._stop_event.is_set():
                self._check_and_notify()

    def _check_and_notify(self) -> None:
        """Check current Pico state and fire callbacks on change."""
        current_port = self.check_now()

        if current_port and self._last_port is None:
            # Device connected
            self._last_port = current_port
            logger.info("Pico connected on %s", current_port)
            if self._on_connect:
                try:
                    self._on_connect(current_port)
                except Exception:
                    logger.exception("on_connect callback error")

        elif not current_port and self._last_port is not None:
            # Device disconnected
            self._last_port = None
            logger.info("Pico disconnected")
            if self._on_disconnect:
                try:
                    self._on_disconnect()
                except Exception:
                    logger.exception("on_disconnect callback error")
