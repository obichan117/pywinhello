# Hardware

## What devices are supported?

Any Raspberry Pi Pico variant. All use Adafruit VID `0x239A`.

| Board | USB PID(s) | Chip | WiFi | Recommended |
|-------|-----------|------|------|-------------|
| Pico | 0x80F4 | RP2040 | No | |
| Pico H | 0x80F4 | RP2040 | No | |
| Pico W | 0x8058, 0x8120 | RP2040 | Yes | ★ |
| Pico 2 | 0x8150 | RP2350 | No | |
| Pico 2 W | 0x8160 | RP2350 | Yes | ★ |

## Why Pico W?

WiFi models add two features that non-W models can't do:

1. **NTP time sync** — the Pico knows the actual time, enabling independent scheduled actions
2. **USB remote wakeup** — the Pico can wake the PC from S3 sleep at the scheduled time without needing Windows Task Scheduler

Non-W models still support scheduled wake via Windows Task Scheduler (the PC monitor creates the task). The Pico W version is more reliable because it doesn't depend on the PC's clock.

## Firmware

The firmware is written in C using the Pico SDK. This gives:

- **Dual USB interface** — HID keyboard + CDC serial on one connection
- **AES-256 encrypted PIN** — key derived from Pico's unique hardware ID
- **LittleFS persistent storage** — config, PIN, and event log survive power cycles
- **Single binary** — auto-detects W vs non-W by probing the CYW43 WiFi chip
- **OTA updates** — firmware can be updated over serial without BOOTSEL

### USB interfaces

The Pico presents two USB interfaces simultaneously:

| Interface | Purpose |
|-----------|---------|
| HID Keyboard | Types PIN characters, Enter, Escape, Tab, Shift |
| CDC Serial | Receives commands from PC (PING, UNLOCK, HELLO, etc.) |

### Storage layout

```
Pico flash (2MB)
├── Firmware (partition A)     — active firmware
├── Firmware (partition B)     — staging for OTA updates
└── LittleFS (last 256KB)
    ├── config.json            — schedule, timing, apps, locale
    ├── pin.enc                — AES-256 encrypted PIN
    └── log.bin                — circular event log (20 entries)
```

### PIN security

- Encrypted with AES-256 using a key derived from the RP2040's unique board ID + salt via HKDF
- PIN is decrypted only into RAM when typing, then wiped
- No `GET_PIN` serial command exists — the PIN never leaves the Pico
- `SETUP_PIN` sends cleartext over local USB serial (acceptable: physical access required)

## First-time setup

The setup wizard in the settings app handles this automatically, but here's what happens:

1. User holds BOOTSEL button and plugs in Pico → `RPI-RP2` drive appears
2. Installer copies `.uf2` firmware to the drive → Pico reboots
3. Pico re-enumerates as HID keyboard + CDC serial
4. Settings app sends `PING` → receives device type and firmware version
5. User enters PIN → `SETUP_PIN` encrypts and stores on Pico flash

Subsequent firmware updates happen over serial (OTA) — no BOOTSEL needed.

## Troubleshooting

**RPI-RP2 drive doesn't appear**
: Try a different USB cable. Charge-only cables don't expose the drive. Hold BOOTSEL *before* plugging in.

**Pico not detected after flashing**
: Wait 5-10 seconds for USB re-enumeration. Check Device Manager → Ports (COM & LPT) for a new COM port.

**PIN entry types wrong characters**
: The firmware uses US keyboard layout for HID reports. PIN digits (0-9) are unaffected by keyboard layout, but special characters may differ.

**Two COM ports in Device Manager**
: The firmware uses a single COM port for CDC serial alongside the HID interface. If you see two, it may be from prior firmware.
