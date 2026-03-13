# TASK-014: Firmware Boot Unlock — Cold Boot Detection + Blind Type

**Status**: todo
**Priority**: high
**Phase**: 2 — Firmware Features

## Description
Detect cold USB enumeration (PC just booted or rebooted) and perform blind PIN entry on the lock screen. This handles the case where no daemon is running yet (login screen after boot/reboot).

## Acceptance Criteria
- [ ] Detect cold boot vs USB suspend/resume:
  - Cold boot: USB power was absent → now present (fresh enumeration)
  - S3 wake: USB bus was suspended → resumed (NOT a cold boot)
  - Track USB connection state to distinguish
- [ ] Boot unlock sequence:
  1. Wait `boot_wait_sec` (default 45s, configurable)
  2. Send Shift keystroke (wake lock screen, harmless)
  3. Wait 2s
  4. Send Shift again (ensure PIN field focused)
  5. Wait 2s
  6. Type PIN + Enter
  7. Wait 5s
  8. If no UNLOCK command received from daemon within 10s: retry once
- [ ] Sequence is skippable:
  - If daemon sends UNLOCK before boot_wait expires → cancel blind-type, let daemon orchestrate
  - If daemon sends STATUS check → respond normally, cancel blind-type
- [ ] Boot unlock only fires if PIN is stored (no PIN = no action)
- [ ] Log entry written: BOOT_UNLOCK + SUCCESS/FAIL + duration
- [ ] Configurable via `timing.boot_wait_sec` in config.json

## Notes
- On most desktops, USB stays powered during S3 sleep — cold enum = real reboot
- On some laptops, USB loses power during S3 — may false-trigger boot unlock
  - Acceptable: worst case, Pico types PIN on an already-unlocked desktop (harmless, just random text)
  - Or: daemon sends cancel before boot_wait expires
- The Shift keystroke is the "test keystroke" approach from our discussion
- Two attempts (with spacing) covers slow-boot PCs
