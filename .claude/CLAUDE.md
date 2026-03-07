# pywinhello

Automate Windows Hello PIN entry via USB HID keyboard (Raspberry Pi Pico).

## Quick Start

```bash
uv sync                    # Install dependencies
uv run pytest              # Run tests
uv run ruff check          # Lint
uv run ruff format --check # Format check
uv run mypy src/           # Type check
```

## Architecture

```
pywinhello/
├── src/pywinhello/
│   ├── __init__.py    # Public exports: HelloMonitor, enter_pin, AuthEvent, HIDKeyboard
│   ├── models.py      # Pure data: AuthEvent, AppConfig, MonitorConfig
│   ├── hid.py         # HIDKeyboard + Pico auto-detect (leaf, no win32 deps)
│   ├── dialog.py      # Dialog detection: find, focus, wait, owner process (ctypes)
│   ├── pin.py         # enter_pin() — two-pass orchestration (uses hid + dialog)
│   ├── monitor.py     # HelloMonitor — WinEvent hook + serve/handle_next
│   └── cli.py         # CLI: serve, ping
├── firmware/pico_hid/  # CircuitPython firmware for Pico
├── tests/
├── pyproject.toml
└── config.example.yaml
```

Dependency graph: `cli → monitor → pin → dialog + hid → models`

## Key Technical Details

- **UIPI blocks software input** on `Credential Dialog Xaml Host` — must use physical HID
- **Two-pass PIN entry**: try PIN directly → if dialog still open → send pin_select_keys → re-enter PIN
- **No chooser ENTER**: typing ENTER before PIN submits empty PIN, corrupts WebAuthn assertion
- **Process detection**: `GetWindow(GW_OWNER)` → `GetWindowThreadProcessId` → PID → exe name
- **WinEvent hook**: `SetWinEventHook(EVENT_OBJECT_CREATE)` for instant dialog detection
- **Pico USB IDs**: VID=0x239A, PIDs={0x8058, 0x8120, 0x80F4, 0x8150, 0x8160}
- **Protocol**: text over CDC serial — `TYPE:1234\n` → `OK\n`
