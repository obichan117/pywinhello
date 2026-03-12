# TASK-023: GUI — Settings App Skeleton (CustomTkinter)

**Status**: todo
**Priority**: high
**Phase**: 4 — GUI

## Description
Create the settings app GUI shell using CustomTkinter. This is the only thing users intentionally interact with — it reads/writes Pico config over serial. First launch shows wizard, subsequent launches show settings panel.

## Acceptance Criteria
- [ ] `gui/app.py` — CustomTkinter root window
  - Window title: "pywinhello"
  - Fixed size, centered on screen
  - Appearance: system theme (light/dark follows Windows)
- [ ] Route based on Pico state:
  - No Pico detected → "Picoデバイスを接続してください" screen
  - Pico connected, no PIN → First-run wizard (TASK-024)
  - Pico connected, PIN set → Settings panel (TASK-026)
- [ ] Real-time Pico detection:
  - Poll COM ports every 2s (or WMI event from monitor)
  - UI updates instantly when Pico plugged/unplugged
- [ ] `gui/i18n/` — internationalization
  - `ja.json` — Japanese strings (default)
  - `en.json` — English strings
  - Language toggle button in corner
  - Language preference stored on Pico (`locale` in config.json)
- [ ] Icon and branding:
  - App icon (.ico) for window and taskbar
  - Simple, recognizable (key or lock icon)
- [ ] PyInstaller-compatible (no external file dependencies at runtime)
- [ ] Entry point: `pywinhello-settings.exe` (separate from monitor)

## Notes
- CustomTkinter: `pip install customtkinter` — MIT license, 10k+ stars
- Settings app and monitor are separate processes
  - Settings app reads/writes Pico directly over serial
  - Monitor also uses serial — need to handle port sharing or communicate via IPC
- Serial port sharing: settings app sends commands, monitor yields serial access
  - Or: settings app talks to monitor via named pipe / localhost socket
  - Simplest: settings app asks monitor to pause, takes serial, returns when done
