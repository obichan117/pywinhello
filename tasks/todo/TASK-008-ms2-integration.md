# TASK-008: Refactor pyrakuten-ms2 to Use pywinhello

**Status**: todo
**Priority**: high

## Description
Replace the internal HID bridge and win_security modules in pyrakuten-ms2 with pywinhello as a dependency. The LoginService._send_pin_via_hid() should use pywinhello.enter_pin() instead of directly managing HIDKeyboard and dialog detection.

## Acceptance Criteria
- [ ] Add pywinhello as optional dep in pyrakuten-ms2
- [ ] Refactor _send_pin_via_hid() to use pywinhello.enter_pin()
- [ ] Remove _internal/hid/bridge.py and _internal/hid/win_security.py
- [ ] Update unit tests in test_login_hid.py
- [ ] All 861+ ms2 tests still pass
- [ ] Live test: MS2 passkey login still works end-to-end

## Notes
This should be done AFTER pywinhello is published to PyPI or at least installable from git.
