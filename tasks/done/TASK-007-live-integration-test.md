# TASK-007: Live Integration Test

**Status**: todo
**Priority**: high

## Description
Create a live integration test that validates the full flow: detect dialog → identify owner → enter PIN → confirm dismissal. Requires actual Pico W connected and a way to trigger Windows Hello.

## Acceptance Criteria
- [ ] `tests/integration/test_live_pin_entry.py`
- [ ] Test enter_pin() with real Pico
- [ ] Test get_owner_exe() with real dialog
- [ ] Test HelloMonitor.handle_next() end-to-end
- [ ] Skipped by default (requires hardware + dialog)
