# Quick Start

## What you'll get

A Raspberry Pi Pico that automatically types your Windows PIN whenever needed — lock screen, Windows Hello dialogs, and morning wake-from-sleep.

## Why a Pico?

Windows blocks all software-based input on the credential dialog (UIPI). A USB HID keyboard is the only way to type into it programmatically. The Pico costs ~$6 and acts as a dedicated authentication device.

## End-User Setup (3 steps)

### 1. Buy a Pico

[Raspberry Pi Pico W](https://www.raspberrypi.com/products/raspberry-pi-pico/) (~$6 / ~1,000円). Any Pico variant works, but W models add scheduled wake-from-sleep.

### 2. Download and install

[Latest release](https://github.com/obichan117/pywinhello/releases/latest) → run `pywinhello_setup.exe`

The installer places:
- `pywinhello-monitor.exe` — invisible background process (starts on login)
- `pywinhello.exe` — settings app (Start Menu shortcut)
- Firmware `.uf2` files for Pico flashing

### 3. Follow the setup wizard

The settings app opens automatically after install:

1. **Device detection** — just plug in the Pico. The wizard handles everything:
    - Brand new Pico? Firmware is flashed automatically (no button presses needed)
    - Already has pywinhello? Checks for updates and applies them over serial
2. **Typing test** — Notepad opens, Pico types test string, speed auto-calibrated
3. **PIN registration** — enter Windows PIN twice, stored encrypted on Pico only
4. **Schedule** — set wake time and days (default: weekdays 07:45)

Done. The monitor runs silently in the background. Plug in = armed, unplug = disarmed.

!!! note "Upgrading from old firmware?"
    If your Pico is already running old pywinhello firmware or other software
    (MicroPython, CircuitPython, Arduino), the wizard will try to update
    automatically. If it can't, you'll be asked to do a one-time manual
    re-flash — see [Manual re-flash](#manual-re-flash-one-time-if-needed) below.

### Manual re-flash (one-time, if needed)

The setup wizard will tell you if this step is needed. It only happens once —
after this, all future updates are automatic.

1. **Unplug** the Pico from your computer
2. **Find the small white button** on the Pico board
3. **Press and hold** that button — don't let go yet
4. **While still holding the button**, plug the USB cable back in
5. **Let go** of the button
6. A **new USB drive** should appear on your computer
7. **Click "Detect Again"** in the setup wizard — it will flash automatically

After this, you'll never need to do this again.

## Developer Setup

For building from source or contributing:

```bash
git clone https://github.com/obichan117/pywinhello.git
cd pywinhello/pc
uv sync --extra dev
uv run pytest tests/ --import-mode=importlib -v
```

## How the detection works

1. **WinEvent hook** (`EVENT_OBJECT_CREATE`) — zero-polling detection of the `Credential Dialog Xaml Host` window
2. **Process identification** — `GetWindow(GW_OWNER)` → PID → exe name identifies which app triggered the dialog
3. **Focus guards** — 3-layer verification (`AttachThreadInput` + `SetForegroundWindow` + re-check) ensures PIN only types into the correct window
4. **Two-pass entry** — tries PIN directly; if dialog persists (fingerprint mode), sends ESCAPE and retries
5. **HID bypass** — Pico types as a physical USB keyboard, bypassing UIPI
