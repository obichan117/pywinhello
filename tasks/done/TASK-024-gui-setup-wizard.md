# TASK-024: GUI — First-Run Setup Wizard

**Status**: todo
**Priority**: high
**Phase**: 4 — GUI

## Description
Step-by-step wizard for first-time setup. Guides non-technical users through device detection, firmware flashing, integration test, PIN entry, and schedule configuration.

## Acceptance Criteria
- [ ] Step 1/4 — デバイスの確認 (Device Detection):
  - Detect Pico in BOOTSEL mode (RPI-RP2 drive) or already flashed (COM port)
  - If BOOTSEL: show illustrated instructions for holding button + plugging in
  - Flash firmware (.uf2 copy to drive)
  - Wait for Pico to reboot and appear as COM port
  - Display: device type (Pico / Pico W), firmware version
  - If already flashed: skip directly to handshake
- [ ] Step 2/4 — 動作テスト (Integration Test) — see TASK-025
- [ ] Step 3/4 — PINの登録 (PIN Registration):
  - Password-masked input field
  - Confirmation field (enter twice)
  - Mismatch → error message
  - Security notice: "PINはPicoデバイス本体にのみ保存されます"
  - Send SETUP_PIN to Pico → confirm OK
- [ ] Step 4/4 — スケジュール設定 (Schedule):
  - Time picker (HH:MM, default 07:45)
  - Day-of-week checkboxes (default Mon-Fri checked)
  - Sleep recommendation: "夜はパソコンをスリープにしてください"
  - With visual guide: "スタート → 電源 → スリープ"
  - Send SET_CONFIG to Pico
- [ ] Final screen — セットアップ完了:
  - Summary checklist (all steps ✓)
  - Optional lock/unlock live test (TASK-025)
  - "Picoデバイスを抜かないでください" reminder
  - Power settings auto-configuration (wake timers, USB wake)
- [ ] Back/Next navigation between steps
- [ ] Progress indicator (step N/4)

## Notes
- BOOTSEL detection: check for removable drive with volume label "RPI-RP2"
- Firmware .uf2 bundled inside the installer (no download needed)
- Power settings configuration requires admin elevation — prompt UAC once
- If user cancels at any step → safe to re-run wizard (idempotent)
