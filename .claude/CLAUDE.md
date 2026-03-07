# pywinhello

Automate Windows Hello PIN entry via USB HID keyboard (Raspberry Pi Pico).

## Quick Start

```bash
uv sync                          # Install deps
uv run pytest                    # Run all 45 unit tests
uv run ruff check                # Lint
uv run mkdocs build --strict     # Build docs
```

## Architecture

```
src/pywinhello/
├── models.py    # AuthEvent, AppConfig, MonitorConfig (dataclasses)
├── hid.py       # HIDKeyboard + find_pico_port (pyserial)
├── dialog.py    # find/focus/wait/get_owner_exe (ctypes win32)
├── pin.py       # enter_pin() — two-pass orchestration
├── monitor.py   # HelloMonitor — WinEvent hook daemon
├── config.py    # load_config() — YAML loader (PyYAML optional)
├── setup.py     # Full Pico setup: UF2 flash, bundle download, firmware copy
├── cli.py       # CLI: serve, ping, setup-pico
└── _data/
    └── firmware/
        ├── boot.py   # CircuitPython boot config (dual CDC)
        └── code.py   # Pico main loop (HID bridge protocol)
```

Dependency graph: `cli → {monitor, setup} → pin → dialog + hid → models`

## Key Technical Details

- **UIPI bypass**: `Credential Dialog Xaml Host` blocks SendInput; Pico USB HID bypasses
- **Two-pass PIN entry**: try PIN directly → fingerprint fallback via pin_select_keys
- **No chooser ENTER**: corrupts WebAuthn assertion
- **Process detection**: `GetWindow(GW_OWNER)` → PID → exe name
- **WinEvent hooks**: `EVENT_OBJECT_CREATE` for zero-polling detection
- **Firmware bundled as package data**: `importlib.resources` resolves `_data/firmware/`
- **Pico USB IDs**: VID=0x239A, PIDs={0x8058, 0x8120, 0x80F4, 0x8150, 0x8160}
- **Protocol**: text over CDC serial — `TYPE:1234\n` → `OK\n`

## Testing

- 45 unit tests, all mock win32/serial deps
- Integration tests in `tests/integration/` (excluded from default pytest)
- `--import-mode=importlib` required in pytest config
