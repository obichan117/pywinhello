"""MonitorService — main orchestrator for the pywinhello background process.

Ties together:
- USB watcher: detects Pico plug/unplug
- Serial protocol: communicates with Pico
- Lock detector: sends UNLOCK on lock screen
- Hello detector: sends HELLO on Windows Security dialog
- Scheduler sync: creates/deletes Windows Task Scheduler tasks
- Auto-updater: checks GitHub for updates

Lifecycle:
- On startup: check if Pico already plugged in, arm if so
- On Pico connect: handshake, read config, arm all subsystems
- On Pico disconnect: disarm everything, delete tasks, idle scan
- On shutdown: clean up all resources
"""

from __future__ import annotations

import atexit
import logging
import threading
from typing import Any

from pywinhello.serial.device import PicoDevice

logger = logging.getLogger(__name__)


class MonitorService:
    """Main background service orchestrator.

    Usage::

        service = MonitorService()
        service.start()  # blocks until stop() or KeyboardInterrupt

    Or non-blocking::

        service = MonitorService()
        service.start_async()
        # ... do other things ...
        service.stop()
    """

    def __init__(self) -> None:
        self._device = PicoDevice()
        self._config: dict[str, Any] = {}
        self._stop_event = threading.Event()
        self._armed = False

        # Subsystem references (created on arm, destroyed on disarm)
        self._usb_watcher: Any = None
        self._lock_detector: Any = None
        self._hello_detector: Any = None
        self._updater: Any = None

    @property
    def is_armed(self) -> bool:
        """Whether automation subsystems are active."""
        return self._armed

    @property
    def device(self) -> PicoDevice:
        """The Pico device handle."""
        return self._device

    @property
    def config(self) -> dict[str, Any]:
        """Last-read Pico configuration."""
        return self._config

    def start(self) -> None:
        """Start the monitor service (blocking).

        Starts USB watching and blocks until ``stop()`` is called
        or KeyboardInterrupt.
        """
        logger.info("MonitorService starting...")
        atexit.register(self._cleanup)

        self._start_usb_watcher()

        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
        finally:
            self.stop()

    def start_async(self) -> None:
        """Start the monitor service (non-blocking).

        Starts USB watching in background threads. Call ``stop()`` to shut down.
        """
        logger.info("MonitorService starting (async)...")
        atexit.register(self._cleanup)
        self._start_usb_watcher()

    def stop(self) -> None:
        """Stop the monitor service and clean up all resources."""
        logger.info("MonitorService stopping...")
        self._stop_event.set()
        self._disarm()
        self._stop_usb_watcher()
        logger.info("MonitorService stopped")

    def _start_usb_watcher(self) -> None:
        """Initialize and start the USB watcher."""
        from pywinhello.monitor.usb_watcher import USBWatcher

        self._usb_watcher = USBWatcher(
            on_connect=self._on_pico_connect,
            on_disconnect=self._on_pico_disconnect,
        )
        self._usb_watcher.start()

    def _stop_usb_watcher(self) -> None:
        """Stop the USB watcher."""
        if self._usb_watcher is not None:
            self._usb_watcher.stop()
            self._usb_watcher = None

    def _on_pico_connect(self, port: str) -> None:
        """Called when a Pico is detected via USB.

        1. Serial handshake (PING)
        2. Read config (GET_CONFIG)
        3. Arm all subsystems
        """
        logger.info("Pico detected on %s, arming automation...", port)

        try:
            # Connect and handshake
            self._device = PicoDevice(port=port)
            info = self._device.connect()
            logger.info(
                "Handshake OK: protocol v%d, %s, firmware %s",
                info.ping_info.protocol_version,
                info.ping_info.device_type,
                info.ping_info.firmware_version,
            )

            # Read config from Pico (v2 only)
            if info.ping_info.protocol_version >= 2:
                self._config = self._device.protocol.get_config()
                logger.debug("Pico config: %s", self._config)
            else:
                self._config = {}
                logger.info("v1 firmware — no config available")

            self._arm()
            logger.info("Pico connected, automation armed")

        except Exception:
            logger.exception("Failed to arm after Pico connect")

    def _on_pico_disconnect(self) -> None:
        """Called when the Pico is unplugged.

        1. Disarm all subsystems
        2. Delete Task Scheduler tasks
        3. Clear in-memory state
        """
        logger.info("Pico disconnected, disarming automation...")
        self._disarm()
        self._device.disconnect()
        self._config = {}
        logger.info("Pico disconnected, automation disarmed")

    def _arm(self) -> None:
        """Activate all automation subsystems."""
        if self._armed:
            self._disarm()

        protocol = self._device.protocol

        # 1. Sync Task Scheduler
        try:
            from pywinhello.monitor.scheduler_sync import sync_schedule

            sync_schedule(self._config)
        except Exception:
            logger.exception("Failed to sync schedule")

        # 2. Start lock detector
        try:
            from pywinhello.monitor.lock_detector import LockConfig, LockDetector

            lock_config = LockConfig.from_pico_config(self._config)
            schedule_times = []
            schedule = self._config.get("schedule", {})
            if schedule.get("time"):
                schedule_times.append(schedule["time"])

            self._lock_detector = LockDetector(
                protocol=protocol,
                config=lock_config,
                schedule_times=schedule_times,
            )
            self._lock_detector.start()
        except Exception:
            logger.exception("Failed to start lock detector")

        # 3. Start hello detector
        try:
            from pywinhello.monitor.hello_detector import AppWhitelist, HelloDetector

            whitelist = AppWhitelist.from_pico_config(self._config)
            self._hello_detector = HelloDetector(
                protocol=protocol,
                whitelist=whitelist,
                on_new_app=self._on_new_app_discovered,
            )
            self._hello_detector.start()
        except Exception:
            logger.exception("Failed to start hello detector")

        # 4. Start auto-updater
        try:
            from pywinhello.monitor.updater import AutoUpdater

            device_info = self._device.info
            self._updater = AutoUpdater(
                protocol=protocol,
                device_type=device_info.ping_info.device_type if device_info else None,
                firmware_version=(
                    device_info.ping_info.firmware_version if device_info else None
                ),
            )
            self._updater.start()
        except Exception:
            logger.exception("Failed to start auto-updater")

        self._armed = True

    def _disarm(self) -> None:
        """Deactivate all automation subsystems."""
        # Stop subsystems in reverse order
        if self._updater is not None:
            try:
                self._updater.stop()
            except Exception:
                logger.debug("Error stopping updater", exc_info=True)
            self._updater = None

        if self._hello_detector is not None:
            try:
                self._hello_detector.stop()
            except Exception:
                logger.debug("Error stopping hello detector", exc_info=True)
            self._hello_detector = None

        if self._lock_detector is not None:
            try:
                self._lock_detector.stop()
            except Exception:
                logger.debug("Error stopping lock detector", exc_info=True)
            self._lock_detector = None

        # Delete all scheduled tasks
        try:
            from pywinhello.monitor.scheduler_sync import delete_all_tasks

            delete_all_tasks()
        except Exception:
            logger.debug("Error deleting tasks", exc_info=True)

        self._armed = False

    def _on_new_app_discovered(self, exe: str) -> None:
        """Called when HelloDetector discovers a new app.

        Updates the Pico config with the new app entry.
        """
        if not self._device.is_connected:
            return

        try:
            # Update local config
            apps = self._config.setdefault("apps", {})
            if exe not in apps:
                apps[exe] = True
                # Push updated config to Pico
                self._device.protocol.set_config(self._config)
                logger.info("Updated Pico config with new app: %s", exe)
        except Exception:
            logger.debug("Failed to update Pico config for new app: %s", exe, exc_info=True)

    def _cleanup(self) -> None:
        """Cleanup handler for atexit."""
        if self._armed:
            self._disarm()
        self._device.disconnect()
