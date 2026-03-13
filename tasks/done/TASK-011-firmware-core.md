# TASK-011: Firmware Core — C/Pico SDK Scaffolding

**Status**: todo
**Priority**: high
**Phase**: 1 — Foundation

## Description
Create the C firmware project using the Pico SDK. This is the foundation for all firmware features. Implements USB HID keyboard and the serial command protocol (replacing CircuitPython code.py).

## Acceptance Criteria
- [ ] CMakeLists.txt with Pico SDK, TinyUSB, LittleFS dependencies
- [ ] `main.c` — init USB, serial, main loop
- [ ] `hid.c/h` — USB HID keyboard report sending
  - Type individual characters (digits 0-9 for PIN)
  - Press special keys (Enter, Escape, Tab, Shift)
  - Configurable inter-key delay
- [ ] `serial_proto.c/h` — text-based serial protocol handler
  - Parse `COMMAND:payload\n` format
  - Respond `OK:response\n` or `ERR:message\n`
  - Commands: PING, TYPE, PRESS, UNLOCK, HELLO, STATUS
- [ ] USB HID descriptor configured for keyboard device
- [ ] USB CDC serial configured for host communication
- [ ] Dual interface: HID + CDC on same USB connection
- [ ] Builds for both RP2040 (Pico/Pico W) and RP2350 (Pico 2/Pico 2 W)
- [ ] Firmware binary < 256KB
- [ ] Basic serial echo test passes

## Notes
- TinyUSB is bundled with Pico SDK — use `tinyusb_device` CMake target
- HID report descriptor: standard keyboard (usage page 0x01, usage 0x06)
- Serial protocol is backward-compatible extension of v1 (TYPE, PRESS, PING still work)
- UNLOCK = type stored PIN + Enter; HELLO = type stored PIN only
- PIN storage is in TASK-012; here just wire up the commands to call storage
