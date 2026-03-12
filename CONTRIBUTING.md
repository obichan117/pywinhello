# Contributing to pywinhello

## Architecture

```
pywinhello/
├── firmware/           # C (Pico SDK) — USB HID keyboard + encrypted storage
│   ├── CMakeLists.txt
│   ├── src/            # C source files
│   └── include/        # Header files
├── pc/                 # Python — monitor daemon + settings GUI
│   ├── src/pywinhello/
│   │   ├── monitor/    # Background: USB watcher, lock/dialog detection, updater
│   │   ├── serial/     # Pico communication: protocol, device, flasher
│   │   ├── gui/        # CustomTkinter: wizard, settings, tests, i18n
│   │   ├── dialog.py   # Windows Security dialog detection (ctypes)
│   │   ├── pin.py      # Focus guards + orchestration
│   │   └── hid.py      # v1 serial HID bridge (legacy)
│   └── tests/
├── installer/          # Inno Setup installer script
└── .github/workflows/  # CI/CD
```

## Building from Source

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Pico SDK](https://github.com/raspberrypi/pico-sdk) (for firmware)
- ARM GCC toolchain (`arm-none-eabi-gcc`)
- [Inno Setup](https://jrsoftware.org/isinfo.php) (for installer, Windows only)

### PC Software

```bash
cd pc
uv sync --extra dev
uv run pytest tests/ --import-mode=importlib --ignore=tests/integration -v
uv run ruff check src/ tests/
uv run mypy src/pywinhello/
```

### Firmware

```bash
export PICO_SDK_PATH=/path/to/pico-sdk
cd firmware
mkdir build && cd build
cmake .. -DPICO_BOARD=pico_w
make -j$(nproc)
# Output: pywinhello_firmware.uf2
```

### Installer

```bash
# Build executables first
cd pc
pip install pyinstaller
pyinstaller --onefile --noconsole --name pywinhello-monitor src/pywinhello/monitor/service.py
pyinstaller --onefile --noconsole --name pywinhello src/pywinhello/gui/app.py

# Build installer
iscc installer/pywinhello.iss
# Output: installer/Output/pywinhello_setup.exe
```

## Serial Protocol

Text-based, one command per line over USB CDC serial.

### Commands (PC → Pico)

| Command | Response | Description |
|---------|----------|-------------|
| `PING` | `OK:pywinhello,<version>,<device>` | Health check |
| `STATUS` | `OK:pin=yes\|no,schedule=HH:MM,wifi=ok\|off\|disabled` | Quick status |
| `GET_CONFIG` | `OK:<json>` | Read full config from flash |
| `SET_CONFIG:<json>` | `OK` | Write config to flash |
| `SETUP_PIN:<pin>` | `OK` | Encrypt and store PIN |
| `CLEAR` | `OK` | Wipe PIN + config + log |
| `UNLOCK` | `OK` | Type stored PIN + Enter (lock screen) |
| `HELLO` | `OK` | Type stored PIN (Windows Hello dialog) |
| `GET_LOG` | `OK:<base64>` | Read event log |
| `FLASH:<size>` | `READY` then binary stream | OTA firmware update |

### Events (Pico → PC, unsolicited)

| Event | Description |
|-------|-------------|
| `EVENT:SCHEDULE_WAKE` | Pico W woke the PC (scheduled) |
| `EVENT:BOOT_UNLOCK:<result>` | Boot blind-type completed |

### Config JSON Schema

```json
{
  "version": 2,
  "firmware": "1.0.0",
  "device": "pico_w",
  "locale": "ja",
  "schedule": {
    "time": "07:45",
    "days": [1, 2, 3, 4, 5]
  },
  "timing": {
    "boot_wait_sec": 45,
    "wake_wait_sec": 5,
    "keystroke_ms": 50,
    "retry_count": 3,
    "retry_interval_sec": 10,
    "dialog_wait_sec": 1
  },
  "apps": {
    "lock_screen": true,
    "MarketSpeed2.exe": true,
    "chrome.exe": true
  }
}
```

## Testing

### Layers

1. **Unit tests** — `uv run pytest pc/tests/` (CI, no hardware)
2. **Hardware integration** — `pc/tests/integration/` (requires Pico connected)
3. **OS state tests** — `pc/tests/manual/` (requires sleep/lock transitions)
4. **Firmware tests** — `firmware/tests/` (on-device via SWD)

### Running unit tests

```bash
cd pc
uv run pytest tests/ --import-mode=importlib --ignore=tests/integration -v
```

## Release Process

1. Update version in `pc/pyproject.toml` and firmware `include/pywinhello.h`
2. Commit: `git commit -m "Release vX.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin main --tags`
5. GitHub Actions builds and creates release automatically
