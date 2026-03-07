# TASK-003: Dialog Owner Detection Tests

**Status**: todo
**Priority**: medium

## Description
Add unit tests for `dialog.get_owner_exe()` — the process detection logic using GetWindow(GW_OWNER) → GetWindowThreadProcessId → OpenProcess → QueryFullProcessImageNameW.

## Acceptance Criteria
- [ ] Test successful owner exe detection (mock ctypes chain)
- [ ] Test no dialog returns None
- [ ] Test no owner window returns None
- [ ] Test OpenProcess failure returns None
