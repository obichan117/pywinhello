# TASK-016: Firmware Pico W Features — NTP + Scheduled Wake

**Status**: todo
**Priority**: medium
**Phase**: 2 — Firmware Features

## Description
Pico W-specific features: WiFi connection, NTP time sync, and independent scheduled wake. These are enhancements over the non-W baseline — Task Scheduler is still the primary wake mechanism.

## Acceptance Criteria
- [ ] WiFi connection using stored SSID/password from config.json
  - Connect on boot, reconnect on drop
  - Graceful failure (no WiFi = features disabled, not crashed)
- [ ] NTP clock sync via `pool.ntp.org`
  - Sync on WiFi connect
  - Re-sync every 6 hours
  - Fallback: if NTP fails, scheduled wake is disabled (rely on Task Scheduler)
- [ ] Scheduled wake:
  1. Calculate next wake time from schedule config + current NTP time
  2. At scheduled time, send USB HID keystroke (Shift) → triggers USB remote wakeup → PC wakes from S3
  3. Wait `wake_wait_sec` for daemon UNLOCK command
  4. If no UNLOCK within 30s → fallback blind-type (same as boot unlock minus long wait)
  5. Log: SCHEDULE_WAKE event
- [ ] WiFi config serial commands:
  - SET_CONFIG handles `wifi.ssid` and `wifi.password` fields
  - WiFi credentials stored in config.json on Pico flash
- [ ] STATUS command includes WiFi state (connected/disconnected/disabled)
- [ ] USB remote wakeup enabled in HID descriptor

## Notes
- USB remote wakeup: TinyUSB supports this via `tud_remote_wakeup()` — sends resume signal on USB bus
- PC must have "Allow this device to wake the computer" enabled (setup.exe configures this)
- NTP gives ~1 second accuracy — fine for "wake at 07:45" use case
- Schedule stored as time + days, Pico calculates next occurrence
- The 30s timeout before fallback blind-type gives daemon time to start after S3 resume
