# TASK-020: PC Monitor — Lock Screen Detection + UNLOCK

**Status**: todo
**Priority**: high
**Phase**: 3 — PC Monitor

## Description
Detect when the Windows desktop is locked and send the UNLOCK command to the Pico. This is the primary unlock mechanism (daemon-orchestrated, reliable timing).

## Acceptance Criteria
- [ ] `monitor/lock_detector.py` — detect locked desktop
  - Method: `OpenInputDesktop()` / session change notification
  - Subscribe to `WTS_SESSION_LOCK` / `WTS_SESSION_UNLOCK` events
  - Or poll-based: `GetForegroundWindow()` returns None when locked
- [ ] On lock detected + schedule is active:
  1. Wait `timing.wake_wait_sec` (for display to render lock screen)
  2. Send UNLOCK over serial → Pico types PIN + Enter
  3. Wait for unlock confirmation (up to `timing.retry_interval_sec`)
  4. If still locked → retry (up to `timing.retry_count` times)
  5. Log result
- [ ] On unlock detected:
  - Update state, log success
- [ ] Respects `apps.lock_screen` toggle:
  - If disabled in Pico config → don't auto-unlock
- [ ] Does NOT fire for manual user locks (e.g., Win+L while user is present):
  - Only fires if close to scheduled time (within 5 min window)
  - Or if PC just woke from sleep (detect via system power event)
- [ ] Distinguishes wake-from-sleep lock vs user-initiated lock

## Notes
- `WTSRegisterSessionNotification` gives lock/unlock events without polling
- Or use `SystemEvents.SessionSwitch` via ctypes
- The "only near scheduled time" guard prevents annoying behavior if user manually locks
- Alternative: always unlock (user plugged in the Pico = they want automation)
  - Configurable: `auto_unlock: always | scheduled_only` (default: always)
- Sleep/wake detection: `WM_POWERBROADCAST` / `PBT_APMRESUMEAUTOMATIC`
