"""Monitor subsystem — USB lifecycle, lock detection, hello detection, scheduling.

The MonitorService is the main orchestrator that ties together:
- USB watcher: detects Pico plug/unplug
- Lock detector: sends UNLOCK on lock screen detection
- Hello detector: sends HELLO on Windows Security dialog detection
- Scheduler sync: creates/deletes Windows Task Scheduler tasks
- Auto-updater: checks GitHub for software/firmware updates
"""

from pywinhello.monitor.service import MonitorService
from pywinhello.monitor.usb_watcher import USBWatcher

__all__ = [
    "MonitorService",
    "USBWatcher",
]
