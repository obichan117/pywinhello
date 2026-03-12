# pywinhello

Automate Windows Hello PIN entry using a Raspberry Pi Pico as a USB HID keyboard.

## What

pywinhello turns a $6 Raspberry Pi Pico into a physical authentication key for Windows. Plug it in and it handles lock screen logins, Windows Hello dialogs, and scheduled wake-from-sleep — all automatically.

## Why

Windows Hello's Credential Dialog is protected by **UIPI** (User Interface Privilege Isolation). Every software input method — `SendInput`, pyautogui, pywinauto, accessibility APIs — is blocked. The OS trusts physical keyboard input unconditionally, so a USB HID device bypasses this restriction entirely.

## How

The system has two halves:

1. **Firmware** (C / Pico SDK) — runs on the Pico. Stores PIN encrypted (AES-256), presents as USB keyboard, types PIN on command.
2. **PC monitor** (Python) — background process. Detects lock screens and Hello dialogs, sends serial commands to the Pico.

```
User plugs in Pico
  → Monitor detects USB connect
  → Handshake (PING → device info)
  → Read config from Pico (GET_CONFIG)
  → Arm: lock detector, hello detector, scheduler sync, auto-updater

Lock screen detected
  → Monitor sends UNLOCK
  → Pico types stored PIN + Enter
  → Lock screen dismissed

Windows Hello dialog detected
  → Monitor checks per-app whitelist
  → Monitor sends HELLO
  → Pico types stored PIN (no Enter)
  → Dialog dismissed

User unplugs Pico
  → Monitor detects USB disconnect
  → Disarm: stop all detectors, delete scheduled tasks
  → Idle scan mode
```

## Quick Links

- [Quick Start](quickstart.md) — End-user setup in 3 steps
- [Hardware](hardware.md) — Supported devices and firmware details
- [API Reference](api.md) — Python module documentation
- [CONTRIBUTING.md](https://github.com/obichan117/pywinhello/blob/main/CONTRIBUTING.md) — Architecture, building, protocol reference
