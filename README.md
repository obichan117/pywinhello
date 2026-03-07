# pywinhello

Automate Windows Hello PIN entry via USB HID keyboard (Raspberry Pi Pico).

Windows Hello's Credential Dialog is protected by UIPI — no software input method
(SendInput, pyautogui, pywinauto) can type into it. `pywinhello` uses a Raspberry Pi
Pico as a USB HID keyboard to bypass this restriction and enter PINs automatically.

## Features

- **Process-aware**: identifies which app triggered Windows Hello, enters the correct PIN
- **Two-pass detection**: handles both PIN mode and fingerprint mode automatically
- **Progressive API**: from raw HID keyboard to full daemon monitor
- **Zero polling**: uses WinEvent hooks for instant dialog detection

## Install

```bash
pip install pywinhello
```

## Quick Start

```python
from pywinhello import enter_pin

# One-shot: enter PIN when dialog appears
event = enter_pin("1234")
print(event.dialog_dismissed)  # True if PIN was accepted

# Daemon: monitor all apps
from pywinhello import HelloMonitor
from pywinhello.models import AppConfig, MonitorConfig

config = MonitorConfig(apps=[
    AppConfig(exe="MarketSpeed2.exe", pin="1234"),
])
monitor = HelloMonitor(config)
monitor.serve()
```

## Hardware Setup

Requires a Raspberry Pi Pico (W/2/2W) running CircuitPython with `adafruit_hid`.
See `firmware/pico_hid/` for the firmware files.

## License

MIT
