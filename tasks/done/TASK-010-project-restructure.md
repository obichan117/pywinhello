# TASK-010: Project Restructure for v2

**Status**: todo
**Priority**: high
**Phase**: 1 — Foundation

## Description
Restructure the pywinhello repo for v2 architecture. The project splits into three top-level components: firmware (C/Pico SDK), pc (Python), and installer (Inno Setup). Existing v1 Python code moves under `pc/` and gets refactored in subsequent tasks.

## Acceptance Criteria
- [ ] New directory layout created:
  ```
  pywinhello/
  ├── firmware/           # C/Pico SDK (replaces CircuitPython)
  │   ├── CMakeLists.txt
  │   ├── src/
  │   └── include/
  ├── pc/
  │   ├── src/pywinhello/
  │   │   ├── monitor/       # Background process
  │   │   ├── serial/        # Pico communication
  │   │   ├── gui/           # CustomTkinter settings app
  │   │   └── ...            # Existing modules (dialog, pin, etc.)
  │   ├── tests/
  │   └── pyproject.toml
  ├── installer/
  │   ├── pywinhello.iss
  │   └── assets/
  └── pyproject.toml      # Workspace root
  ```
- [ ] Existing v1 source moved to `pc/src/pywinhello/`
- [ ] Existing tests moved to `pc/tests/`
- [ ] Old `firmware/pico_hid/` (CircuitPython) archived or removed
- [ ] Old `_data/firmware/` bundled CircuitPython removed
- [ ] pyproject.toml updated for new layout
- [ ] All existing v1 tests still pass after move
- [ ] CLAUDE.md updated with new architecture

## Notes
- v1 code (dialog.py, pin.py, monitor.py, hid.py) is kept and refactored incrementally
- CircuitPython firmware is replaced entirely by C firmware (TASK-011)
- config.example.yaml can remain for now, will be removed when config moves to Pico
