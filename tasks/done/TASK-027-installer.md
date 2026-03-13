# TASK-027: Installer — Inno Setup + PyInstaller Bundle

**Status**: todo
**Priority**: high
**Phase**: 5 — Installer & Distribution

## Description
Create the end-user installer that non-technical users download and run. Standard Windows setup wizard (Inno Setup) wrapping PyInstaller executables and bundled firmware.

## Acceptance Criteria

### PyInstaller Bundles
- [ ] `pywinhello-monitor.exe` — background monitor (single-file, --noconsole)
- [ ] `pywinhello.exe` — settings app GUI (single-file, --noconsole, --icon)
- [ ] Both bundles include all dependencies (pyserial, customtkinter, requests, wmi)
- [ ] Total size < 50MB (ideally < 30MB)

### Inno Setup Installer
- [ ] `installer/pywinhello.iss` — Inno Setup script
- [ ] Standard wizard: Welcome → License → Install → Finish
- [ ] Japanese installer text (default) with English option
- [ ] Installs to `%LOCALAPPDATA%\pywinhello\`
- [ ] Files installed:
  - `pywinhello-monitor.exe`
  - `pywinhello.exe`
  - `firmware_rp2040.uf2` (bundled)
  - `firmware_rp2350.uf2` (bundled, if needed)
- [ ] Start Menu shortcut: "pywinhello" → `pywinhello.exe`
- [ ] Startup entry: `pywinhello-monitor.exe` in Startup folder
- [ ] "Launch pywinhello" checkbox on finish (opens settings app for first-run wizard)
- [ ] Icon for shortcuts and Add/Remove Programs
- [ ] Signed executable (nice-to-have, requires code signing cert)

### Uninstaller
- [ ] Standard Windows uninstall (Settings → Apps → pywinhello → Uninstall)
- [ ] If Pico connected: send CLEAR (wipe PIN from device)
- [ ] If Pico not connected: show warning about PIN remaining on device
- [ ] Remove Task Scheduler tasks (pywinhello-*)
- [ ] Remove Startup entry
- [ ] Remove installed files + directory
- [ ] Remove Start Menu shortcut

### First Launch
- [ ] Installer finishes → settings app opens → first-run wizard starts
- [ ] Monitor starts in background (via Startup entry or launched by settings app)

## Notes
- Inno Setup: free, open source, industry standard for Windows installers
- Japanese Inno Setup translations available (built-in)
- PyInstaller `--onefile` for simplest deployment (no DLL hell)
- Code signing: consider Let's Encrypt or cheap code signing cert to avoid SmartScreen warnings
  - Without signing: "Windows protected your PC" dialog on first run (scary for beginners)
  - Consider: `signtool` + Azure Code Signing or SSL.com
