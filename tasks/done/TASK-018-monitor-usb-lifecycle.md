# TASK-018: PC Monitor — USB Plug/Unplug Lifecycle

**Status**: todo
**Priority**: high
**Phase**: 3 — PC Monitor

## Description
The monitor background process watches for Pico USB plug/unplug events. Plug in = arm all automation (read config from Pico, create Task Scheduler tasks). Unplug = disarm everything (delete tasks, stop detection loops). Users never manage a "daemon" — they just plug/unplug the device.

## Acceptance Criteria
- [ ] `monitor/usb_watcher.py` — WMI USB device event subscription
  - Detect Pico connect (VID:PID match)
  - Detect Pico disconnect
  - Callback-based (no polling)
- [ ] On Pico connect:
  1. Serial handshake (PING → device info)
  2. Read config from Pico (GET_CONFIG)
  3. Create/update Task Scheduler wake tasks (TASK-019)
  4. Start lock screen detection loop (TASK-020)
  5. Start Windows Hello dialog detection (existing WinEvent hook)
  6. Log: "Pico connected, automation armed"
- [ ] On Pico disconnect:
  1. Delete ALL Task Scheduler tasks (pywinhello-*)
  2. Stop lock/dialog detection loops
  3. Clear in-memory state (no config, no PIN reference)
  4. Return to idle USB scanning
  5. Log: "Pico disconnected, automation disarmed"
- [ ] On startup (monitor.exe launches):
  1. Check if Pico already plugged in → if yes, arm
  2. If no Pico → idle scan mode
- [ ] `monitor/service.py` — main orchestrator
  - Ties together USB watcher, lock detector, hello detector, scheduler sync
  - Clean shutdown on process exit
- [ ] Startup registration (Windows Startup folder item)
- [ ] Minimal resource usage when idle (< 5MB RAM, ~0% CPU)

## Notes
- WMI: `Win32_DeviceChangeEvent` or `__InstanceCreationEvent` on `Win32_PnPEntity`
- Alternative: `wmi` Python package or `pywin32` for device notifications
- The monitor is `pywinhello-monitor.exe` (PyInstaller single-file)
- No system tray, no visible window — completely invisible background process
- Startup item: shortcut in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`
