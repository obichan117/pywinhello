# TASK-013: PC Serial Protocol — Extend for v2

**Status**: todo
**Priority**: high
**Phase**: 1 — Foundation

## Description
Extend the existing `hid.py` serial module to support all v2 commands. Refactor into `pc/src/pywinhello/serial/` package with device detection, protocol handler, and firmware flasher.

## Acceptance Criteria
- [ ] `serial/protocol.py` — command/response encoding
  - Send command, wait for OK/ERR response
  - Timeout handling per command
  - All v2 commands: PING, GET_CONFIG, SET_CONFIG, SETUP_PIN, CLEAR, UNLOCK, HELLO, GET_LOG, FLASH, STATUS
- [ ] `serial/device.py` — Pico detection and handshake
  - Auto-detect by VID:PID (existing logic from hid.py)
  - Handshake: PING → parse device type, firmware version
  - Connection state management (connected/disconnected)
  - Reconnection on serial errors
- [ ] `serial/flasher.py` — OTA firmware push (stub for now, implemented in TASK-018)
- [ ] Backward-compatible with v1 firmware (TYPE, PRESS, PING still work)
- [ ] Thread-safe serial access (existing Lock pattern preserved)
- [ ] Unit tests for protocol encoding/decoding
- [ ] Unit tests for device detection (mocked pyserial)

## Notes
- Existing `hid.py` has good patterns: find_pico_port(), Lock(), timeout handling
- Refactor don't rewrite — move existing logic into new structure
- GET_CONFIG returns full JSON — parse into Python dataclass on PC side
- SETUP_PIN:<pin> — PC sends cleartext over local USB serial, acceptable trust model
