# TASK-006: Pico Setup CLI Command

**Status**: todo
**Priority**: low

## Description
Add a `pywinhello setup-pico` CLI command that guides users through flashing CircuitPython and copying firmware files to the Pico. Migrate from jp-trading's `tools/pico_setup.py`.

## Acceptance Criteria
- [ ] `pywinhello setup-pico` command
- [ ] Detects Pico in BOOTSEL mode (UF2 drive)
- [ ] Downloads CircuitPython UF2 (or prompts user)
- [ ] Copies boot.py, code.py, adafruit_hid to CIRCUITPY
- [ ] Verifies with ping after setup
