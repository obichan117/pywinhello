# TASK-019: PC Monitor — Task Scheduler Sync

**Status**: todo
**Priority**: high
**Phase**: 3 — PC Monitor

## Description
Sync Windows Task Scheduler tasks with the schedule stored on the Pico. Tasks are created on plug, deleted on unplug. Tasks include the "Wake the computer" flag for S3/S4 wake support.

## Acceptance Criteria
- [ ] `monitor/scheduler_sync.py` — create/update/delete scheduled tasks
- [ ] Task creation from Pico config:
  - Task name: `pywinhello-wake`
  - Trigger: daily at `schedule.time` on `schedule.days`
  - Action: `pywinhello-monitor.exe wake` (lightweight command)
  - Flags: "Wake the computer to run this task" enabled
  - Run as current user, run whether logged in or not
- [ ] Task deletion: remove all `pywinhello-*` tasks
- [ ] Idempotent: calling sync with same config doesn't create duplicates
- [ ] Day-of-week mapping: config days [1-5] → Task Scheduler days
- [ ] `wake` CLI command:
  - Called by Task Scheduler when PC wakes
  - If daemon is already running and Pico is connected → signal daemon to start unlock
  - If daemon is not running → log and exit (Startup will launch daemon on login)
- [ ] Power settings configuration (run once during initial setup):
  - Enable wake timers: `powercfg /setacvalueindex ... RTCWAKE 1`
  - Enable USB device wake: DeviceManager setting via PowerShell
- [ ] Unit tests (mock subprocess/schtasks)

## Notes
- Uses `schtasks.exe` (same approach as pyrakuten-ms2 ScheduleService)
- "Run whether user is logged on or not" may require password — evaluate if needed
- Alternative: run only when logged on (simpler, covers most cases since Startup will have the daemon running)
- Power settings require admin elevation — do once during initial setup, not on every plug
