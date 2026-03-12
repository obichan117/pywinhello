# TASK-021: PC Monitor — Refactor Windows Hello Detection + App Whitelist

**Status**: todo
**Priority**: high
**Phase**: 3 — PC Monitor

## Description
Refactor the existing v1 WinEvent hook-based Windows Hello dialog detection to support the per-app whitelist stored on Pico. Move from env var PIN to serial HELLO command.

## Acceptance Criteria
- [ ] Existing `monitor.py` / `dialog.py` / `pin.py` logic refactored into `monitor/hello_detector.py`
- [ ] WinEvent hook for Windows Security dialog (preserved from v1)
- [ ] On dialog detected:
  1. Identify owner process (existing `get_owner_exe()` logic)
  2. Check app whitelist from Pico config (`apps` dict)
  3. If app is disabled → ignore dialog
  4. If app is enabled → focus dialog (existing focus guards) → send HELLO → Pico types PIN
  5. Wait for dismiss (existing logic)
  6. Handle fingerprint mode (existing ESCAPE fallback)
  7. Log result
- [ ] New apps auto-discovered:
  - If dialog owner is not in whitelist → add to Pico config as enabled by default
  - Send SET_CONFIG to update Pico
  - Log: "New app detected: chrome.exe (enabled)"
- [ ] PIN no longer read from env var or registry — always from Pico via HELLO command
- [ ] Focus guards preserved (3-layer verification from v1)
- [ ] All existing v1 dialog/pin tests refactored and passing

## Notes
- The core WinEvent + focus guard logic is proven and solid — don't break it
- Main change: PIN source (env var → Pico serial) and app filtering
- `enter_pin()` becomes `send_hello_command()` — delegates typing to Pico
- The fingerprint mode retry loop stays the same, just uses HELLO instead of TYPE
