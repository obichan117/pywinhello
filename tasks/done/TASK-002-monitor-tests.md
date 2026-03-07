# TASK-002: Monitor Unit Tests

**Status**: todo
**Priority**: high

## Description
Add unit tests for HelloMonitor (handle_next, serve, stop, pin_map lookup). The WinEvent hook internals need mocking since they use ctypes win32 calls.

## Acceptance Criteria
- [ ] Test handle_next with dialog already visible
- [ ] Test handle_next timeout
- [ ] Test pin_map lookup by exe name
- [ ] Test unknown exe skipped gracefully
- [ ] Test serve loop stops on stop()
