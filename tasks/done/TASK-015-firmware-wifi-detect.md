# TASK-015: Firmware WiFi Auto-Detection

**Status**: todo
**Priority**: high
**Phase**: 2 — Firmware Features

## Description
Single firmware binary that auto-detects whether it's running on a W (WiFi) or non-W Pico variant. Enables/disables WiFi features accordingly. Users never need to choose a firmware variant.

## Acceptance Criteria
- [ ] On boot, attempt CYW43 WiFi chip initialization
  - Success → set `device` to "pico_w" or "pico_2_w", enable WiFi features
  - Failure → set `device` to "pico" or "pico_2", disable WiFi features
- [ ] RP2040 vs RP2350 detection (Pico 1 vs Pico 2 family)
- [ ] Device type reported in PING response and STATUS
- [ ] WiFi-dependent features gracefully disabled on non-W:
  - NTP clock sync → disabled
  - Scheduled wake → disabled (rely on Task Scheduler)
  - WiFi config in config.json → ignored
- [ ] Single .uf2 binary works on all variants
  - Or: two binaries (RP2040 + RP2350) if architecture requires it, but same feature set
- [ ] Detection result cached after first boot (don't re-probe every power cycle)

## Notes
- CYW43 init on non-W Pico returns error immediately — no hang, no crash
- RP2040 and RP2350 have different instruction sets — may need separate builds
  - If so: `firmware_rp2040.uf2` (Pico + Pico W) and `firmware_rp2350.uf2` (Pico 2 + Pico 2 W)
  - WiFi detection is same logic in both builds
- Setup.exe can detect chip type from USB PID and flash correct binary
