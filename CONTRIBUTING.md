# Contributing to pywinhello

## What is this system?

pywinhello is a two-part system — C firmware on a Raspberry Pi Pico and a Python background service on Windows — that automates Windows Hello PIN entry via USB HID.

```
┌─ Firmware (C / Pico SDK) ──────────────────────────────────────────┐
│                                                                     │
│  main.c ─── hid.c           USB HID keyboard (types PIN)           │
│          ├── serial_proto.c  USB CDC serial (receives commands)     │
│          ├── storage.c       LittleFS config/PIN/log on flash       │
│          ├── crypto.c        AES-256 PIN encryption (mbedtls)       │
│          ├── wifi.c          CYW43 auto-detect (W models only)      │
│          ├── scheduler.c     NTP + scheduled wake (W models only)   │
│          └── bootloader.c    OTA serial firmware updates             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
          │ USB (HID + CDC serial)
          ▼
┌─ PC Software (Python) ─────────────────────────────────────────────┐
│                                                                     │
│  serial/                                                            │
│  ├── protocol.py      Command/response encoding                      │
│  ├── device.py        Pico auto-detection, handshake, reconnect     │
│  └── flasher.py       OTA firmware push over serial                 │
│                                                                     │
│  monitor/                                                           │
│  ├── service.py       Main orchestrator (arm on plug, disarm on     │
│  │                    unplug, clean shutdown)                        │
│  ├── usb_watcher.py   WMI USB plug/unplug events (callback-based)   │
│  ├── lock_detector.py Lock screen detection + UNLOCK command         │
│  ├── hello_detector.py WinEvent hook + per-app whitelist + HELLO     │
│  ├── scheduler_sync.py Task Scheduler create/delete (wake timers)    │
│  └── updater.py       GitHub Releases auto-updater (software + fw)   │
│                                                                     │
│  gui/                                                               │
│  ├── app.py           CustomTkinter root (routes to wizard/settings) │
│  ├── wizard/          First-run setup (device → test → PIN →         │
│  │                    schedule)                                      │
│  ├── settings/        Settings panel (basic, apps, advanced, log,    │
│  │                    version)                                       │
│  ├── tests/           Notepad typing test, lock/unlock live test     │
│  └── i18n/            ja.json, en.json                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Why this architecture?

### Pico = sole data owner

The Pico stores everything — PIN (encrypted), schedule, timing config, app whitelist, event log. The PC stores **nothing**. This means:

- Unplug the Pico and the PC has zero knowledge of your PIN
- Settings app reads/writes Pico over serial, not local files
- No registry keys, no config files, no `.env` with plaintext secrets

### USB HID bypasses UIPI

Windows trusts physical keyboard input unconditionally. Software methods (`SendInput`, pyautogui) are blocked by UIPI on the Credential Dialog. A USB HID device is indistinguishable from a real keyboard.

### Plug/unplug = arm/disarm

No daemon management, no "start service" buttons. Users understand plugging in a USB device. The monitor watches for USB events and arms/disarms all subsystems automatically.

### Single firmware binary

The firmware auto-detects whether it's running on a W (WiFi) or non-W Pico by probing the CYW43 chip. WiFi features gracefully degrade on non-W models. Users never choose a firmware variant.

## How to build

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
uv run pytest tests/ --import-mode=importlib -v
uv run ruff check src/ tests/
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
# Build executables
cd pc
pip install pyinstaller
pyinstaller --onefile --noconsole --name pywinhello-monitor src/pywinhello/monitor/service.py
pyinstaller --onefile --noconsole --name pywinhello src/pywinhello/gui/app.py

# Build installer
iscc installer/pywinhello.iss
# Output: installer/Output/pywinhello_setup.exe
```

## Serial Protocol

Text-based, one command per line over USB CDC serial at 115200 baud.

### Why text-based?

Debuggable with any serial terminal. No binary framing overhead for the command set (payloads are small). Binary mode only activates during firmware flash.

### Commands (PC → Pico)

| Command | Response | What it does |
|---------|----------|--------------|
| `PING` | `PONG:<device>:<version>` | Handshake — returns device type and firmware version |
| `STATUS` | `OK:pin=yes\|no,schedule=HH:MM,wifi=ok\|off` | Quick device status |
| `GET_CONFIG` | `OK:<json>` | Read full config from Pico flash |
| `SET_CONFIG:<json>` | `OK` | Write config to Pico flash |
| `SETUP_PIN:<pin>` | `OK` | Encrypt and store PIN (cleartext over local USB — acceptable) |
| `CLEAR` | `OK` | Factory reset — wipe PIN, config, and log |
| `UNLOCK` | `OK` | Type stored PIN + Enter (for lock screen) |
| `HELLO` | `OK` | Type stored PIN only (for Windows Hello dialog — no Enter) |
| `GET_LOG` | `OK:<json array>` | Read last 20 events from circular log |
| `FLASH:<size>` | `READY` → binary stream | OTA firmware update |
| `TYPE:<text>` | `OK` | Type arbitrary text |
| `PRESS:<key>` | `OK` | Press named key |

### Config JSON

```json
{
  "version": 2,
  "firmware": "1.0.0",
  "device": "pico_w",
  "locale": "ja",
  "schedule": { "time": "07:45", "days": [1, 2, 3, 4, 5] },
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

### Why four layers?

Different failure modes require different test environments. Unit tests catch logic bugs fast. Hardware tests catch timing and USB issues. OS tests catch Windows state machine edge cases.

| Layer | What | Where | When |
|-------|------|-------|------|
| Unit | Protocol encoding, config parsing, version comparison, whitelist logic | `pc/tests/` | Every commit (CI) |
| Hardware integration | Serial handshake, HID typing, flash cycle | `pc/tests/integration/` | With Pico connected |
| OS state | Lock/unlock transitions, sleep/wake, Task Scheduler | `pc/tests/manual/` | Manual on Windows |
| Firmware | On-device flash read/write, crypto, USB enumeration | `firmware/tests/` | Via SWD probe |

### Running unit tests

```bash
cd pc
uv run pytest tests/ --import-mode=importlib -v
```

**222 tests** covering serial protocol, device detection, USB watcher, lock detector, hello detector, scheduler sync, auto-updater, GUI i18n, and setup provisioning.

## Release Process

1. Update version in `pc/pyproject.toml` and firmware `include/pywinhello.h`
2. Commit: `git commit -m "Release vX.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin main --tags`
5. GitHub Actions builds firmware, PyInstaller exe, and Inno Setup installer
6. Release with `manifest.json` for auto-updater
