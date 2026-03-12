# pywinhello

Automate Windows Hello PIN entry via USB HID keyboard (Raspberry Pi Pico).

## Why?

Windows Hello's Credential Dialog is protected by **UIPI** (User Interface Privilege Isolation). No software input method — SendInput, pyautogui, pywinauto — can type into it. `pywinhello` uses a Raspberry Pi Pico as a USB HID keyboard to bypass this restriction.

## Features

- **Process-aware** — identifies which app triggered Windows Hello and enters the correct PIN
- **Two-pass detection** — handles both PIN mode and fingerprint mode automatically
- **Progressive API** — from raw HID keyboard to full daemon monitor
- **Zero polling** — uses WinEvent hooks for instant dialog detection
- **Automated Pico setup** — flashes CircuitPython, downloads libraries, installs firmware in one command

## Progressive API

```
serve()           Daemon — handles all dialogs automatically
  └── handle_next()  One-shot — wait for next dialog
       └── enter_pin()   Immediate — type PIN into current dialog
            └── HIDKeyboard  Raw — serial HID bridge
```

## Quick Links

- [Quick Start](quickstart.md) — Install and get running in 5 minutes
- [Hardware Setup](hardware.md) — Flash your Pico with the firmware
- [API Reference](api.md) — Full API documentation
