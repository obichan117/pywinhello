# pywinhello

Automate Windows Hello PIN entry via USB HID keyboard (Raspberry Pi Pico).

[![PyPI](https://img.shields.io/pypi/v/pywinhello)](https://pypi.org/project/pywinhello/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Windows Hello's Credential Dialog is protected by UIPI — no software input method
(SendInput, pyautogui, pywinauto) can type into it. `pywinhello` uses a Raspberry Pi
Pico as a USB HID keyboard to bypass this restriction and enter PINs automatically.

## Features

- **Process-aware**: identifies which app triggered Windows Hello, enters the correct PIN
- **Two-pass detection**: handles both PIN mode and fingerprint mode automatically
- **Progressive API**: from raw HID keyboard to full daemon monitor
- **Zero polling**: uses WinEvent hooks for instant dialog detection
- **Automated Pico setup**: flashes CircuitPython, downloads libraries, installs firmware

## Install

```bash
pip install pywinhello
```

## Hardware

Any Raspberry Pi Pico variant (Pico, Pico W, Pico 2, Pico 2 W) — ~$4.

### Automated Setup

```bash
# Hold BOOTSEL on Pico, plug in USB, then:
pywinhello setup-pico
```

This handles everything: flashing CircuitPython, downloading `adafruit_hid`, and installing the HID bridge firmware.

### Verify

```bash
pywinhello ping
# PONG from COM8
```

## Quick Start

```python
from pywinhello import enter_pin

# One-shot: enter PIN when dialog appears
event = enter_pin("1234")
print(event.dialog_dismissed)  # True if PIN was accepted
```

### Process-aware daemon

Create `config.yaml`:

```yaml
apps:
  - exe: MarketSpeed2.exe
    pin: "1234"
  - exe: chrome.exe
    pin: "5678"
```

```python
from pywinhello import HelloMonitor, load_config

config = load_config("config.yaml")
monitor = HelloMonitor(config)
monitor.serve(on_event=lambda e: print(e))
```

### CLI

```bash
# Run monitor daemon
pywinhello serve -c config.yaml

# Ping Pico
pywinhello ping

# Set up Pico (flash + firmware)
pywinhello setup-pico
```

## Architecture

```
Host (Python)          Pico (CircuitPython)       Windows
┌──────────┐  serial   ┌──────────┐  USB HID   ┌──────────┐
│ pywinhello│─────────→│ code.py  │───────────→│ Credential│
│           │ TYPE:1234 │ keyboard │ keystrokes  │  Dialog   │
│           │←─────────│          │             │           │
│           │    OK     │          │             │           │
└──────────┘           └──────────┘             └──────────┘
```

### Progressive API

```
serve()              Daemon — handles all dialogs automatically
  └── handle_next()    One-shot — wait for next dialog
       └── enter_pin()   Immediate — type PIN into current dialog
            └── HIDKeyboard  Raw — serial HID bridge
```

## How it works

1. **Dialog detection** — `SetWinEventHook(EVENT_OBJECT_CREATE)` detects `Credential Dialog Xaml Host` instantly
2. **Process identification** — `GetWindow(GW_OWNER)` traces the dialog to the requesting process
3. **Focus** — `AttachThreadInput` + `SetForegroundWindow` brings the dialog to focus
4. **Two-pass entry** — Types PIN directly; if dialog persists, sends ESCAPE to navigate from fingerprint to PIN mode, then retries
5. **HID bypass** — Physical keyboard input from the Pico bypasses UIPI restrictions

## License

MIT
