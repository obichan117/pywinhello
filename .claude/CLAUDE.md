# pywinhello

Raspberry Pi Pico as a physical "key" for Windows Hello automation. Plug in = automation on, unplug = off.

End-user Windows app + C firmware — GUI setup wizard, PIN on device, auto-updates.

## Quick Start

```bash
uv sync                          # Install deps
uv run pytest                    # Run unit tests
uv run ruff check                # Lint
cd pc && uv run mkdocs build --strict  # Build docs
```

## Architecture

```
pywinhello/
├── firmware/                    # C (Pico SDK)
│   ├── CMakeLists.txt
│   ├── src/
│   │   ├── main.c              # Init USB, serial, main loop
│   │   ├── hid.c               # TinyUSB HID keyboard
│   │   ├── storage.c           # LittleFS config/PIN/log
│   │   ├── serial_proto.c      # Serial command handler
│   │   ├── crypto.c            # AES-256 PIN encryption (mbedtls)
│   │   ├── wifi.c              # CYW43 + NTP (W only, auto-detected)
│   │   ├── scheduler.c         # Wake timer (W only)
│   │   └── bootloader.c        # OTA serial flash updates
│   └── include/
├── pc/                          # Python — monitor + settings GUI
│   ├── src/pywinhello/
│   │   ├── monitor/            # Background process
│   │   │   ├── usb_watcher.py  # WMI USB plug/unplug events
│   │   │   ├── lock_detector.py    # Win32 lock screen detection
│   │   │   ├── hello_detector.py   # WinEvent Windows Security hook
│   │   │   ├── scheduler_sync.py   # Task Scheduler create/delete
│   │   │   ├── updater.py         # GitHub release auto-updater
│   │   │   └── service.py         # Main orchestrator loop
│   │   ├── serial/
│   │   │   ├── protocol.py    # Serial command/response
│   │   │   ├── device.py      # Pico detection + handshake
│   │   │   └── flasher.py     # OTA firmware push
│   │   ├── gui/
│   │   │   ├── app.py         # CustomTkinter root
│   │   │   ├── constants.py   # Shared constants (PIN validation, day keys)
│   │   │   ├── wizard/        # First-run setup steps
│   │   │   ├── settings/      # Settings panel tabs
│   │   │   ├── tests/         # Notepad test, lock test
│   │   │   └── i18n/          # ja.json, en.json
│   │   ├── setup/             # BOOTSEL detection + firmware flashing
│   │   ├── dialog.py          # Windows Security detection
│   │   └── models.py          # Dataclasses
│   ├── tests/
│   └── pyproject.toml
├── installer/
│   ├── pywinhello.iss          # Inno Setup script
│   └── assets/                 # Icons, license
├── .github/workflows/          # CI/CD
└── pyproject.toml              # Workspace root
```

## Core Design Principles

- **Pico = physical key**: PIN, schedule, timing, app whitelist, logs ALL stored on Pico flash
- **PC stores nothing**: monitor is a thin bridge, settings app reads/writes Pico over serial
- **Plug in = armed, unplug = disarmed**: Task Scheduler tasks created/deleted on USB events
- **Single firmware**: auto-detects W vs non-W by probing CYW43 chip
- **Beginner-first**: Japanese GUI, no CLI, no config files, no daemon concept exposed

## Serial Protocol

```
PC → Pico:
  PING                    → OK:pywinhello,1.0.0,pico_w
  GET_CONFIG              → OK:<config.json>
  SET_CONFIG:<json>       → OK
  SETUP_PIN:<pin>         → OK
  CLEAR                   → OK (wipe everything)
  UNLOCK                  → OK (type PIN + Enter for lock screen)
  HELLO                   → OK (type PIN for Windows Hello dialog)
  GET_LOG                 → OK:<base64 log>
  FLASH:<size>            → READY (then binary stream)
  REBOOT                  → OK (enter BOOTSEL mode for UF2 flashing)
  STATUS                  → OK:pin=yes,schedule=07:45,wifi=ok
```

## Key Technical Details

- **UIPI bypass**: Credential Dialog blocks SendInput; USB HID bypasses
- **Focus guards**: 3-layer verification before PIN typing (prevents leak)
- **Two-pass PIN**: try PIN → fingerprint fallback → ESCAPE → retry
- **WinEvent hooks**: `EVENT_OBJECT_CREATE` for zero-polling dialog detection
- **Pico USB IDs**: VID=0x239A, PIDs={0x8058, 0x8120, 0x80F4, 0x8150, 0x8160}

## Task Tracking

```
tasks/
├── done/        # TASK-001 to TASK-029 (all complete)
├── todo/        # (empty)
└── in-progress/ # Currently active
```

## Testing

- 219 unit tests, all pass
- 4-layer strategy (unit → hardware integration → OS state → firmware on-device)
- `--import-mode=importlib` required in pytest config
- Hardware tests marked `@pytest.mark.hardware`, excluded from CI
