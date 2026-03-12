"""Monitor subsystem — USB lifecycle, lock detection, hello detection, scheduling.

The MonitorService is the main orchestrator that ties together:
- USB watcher: detects Pico plug/unplug
- Lock detector: sends UNLOCK on lock screen detection
- Hello detector: sends HELLO on Windows Security dialog detection
- Scheduler sync: creates/deletes Windows Task Scheduler tasks
- Auto-updater: checks GitHub for software/firmware updates

Backward compatibility: ``HelloMonitor`` (v1 API) is re-exported here so that
``from pywinhello.monitor import HelloMonitor`` continues to work. The v1 class
lives in ``monitor/_v1_hello.py`` (relocated from the original ``monitor.py``
when this directory became a package).
"""

from pywinhello.monitor._v1_hello import HelloMonitor
from pywinhello.monitor.service import MonitorService

__all__ = [
    "HelloMonitor",
    "MonitorService",
]
