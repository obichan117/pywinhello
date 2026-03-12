# TASK-026: GUI — Settings Panel

**Status**: todo
**Priority**: high
**Phase**: 4 — GUI

## Description
Full settings panel shown after initial setup. All data read from / written to Pico. Users manage everything from this single window.

## Acceptance Criteria

### Connection Status (top)
- [ ] "✓ 接続中 (Pico W)" or "Picoデバイスが接続されていません"
- [ ] Auto-updates on plug/unplug

### 基本設定 (Basic Settings)
- [ ] PIN: "登録済み ✓" + [PINを変更] button
  - Change flow: enter new PIN twice → SETUP_PIN → confirm
- [ ] スケジュール:
  - Time picker (HH:MM)
  - Day-of-week checkboxes
  - [保存] button → SET_CONFIG to Pico

### 自動入力の対象 (Automation Targets)
- [ ] ロック画面: toggle (auto-unlock on/off)
- [ ] Windows Helloダイアログ: per-app toggles
  - List of detected apps with checkboxes
  - "※ 新しいアプリが検出されると自動で追加されます (初期状態: 有効)"
- [ ] Save → SET_CONFIG to Pico

### 詳細設定 (Advanced Settings)
- [ ] 起動後の待機時間: number input (30-90秒, default 45)
- [ ] スリープ復帰後の待機時間: number input (3-10秒, default 5)
- [ ] キー入力の速度: number input (30-150ミリ秒, default 50)
- [ ] リトライ回数: number input (1-5回, default 3)
- [ ] リトライ間隔: number input (5-30秒, default 10)
- [ ] ダイアログ検出後の待機時間: number input (0.5-3秒, default 1)
- [ ] Each field has description text + recommended range
- [ ] Save → SET_CONFIG to Pico

### 最近の記録 (Recent Log)
- [ ] Last 20 events from Pico log (GET_LOG)
- [ ] Format: "03/12 07:45 スリープ復帰 → ログイン成功 2.3秒"
- [ ] Show event type, result, duration
- [ ] Auto-suggest timing improvements based on failures (nice-to-have)

### バージョン情報 (Version Info)
- [ ] ソフトウェア: vX.Y.Z + "✓ 最新" or "アップデートあり"
- [ ] ファームウェア: vX.Y.Z + "✓ 最新" or "アップデートあり"
- [ ] 最終確認: date/time
- [ ] [今すぐ確認] button → trigger update check
- [ ] Force update notification if applicable

### Bottom Actions
- [ ] [テスト] — lock/unlock test (same as TASK-025)
- [ ] [初期値に戻す] — reset timing values to defaults (not PIN/schedule)
- [ ] [Picoを初期化] — confirmation dialog → CLEAR → wipes everything
- [ ] [English] / [日本語] toggle

## Notes
- All settings read from Pico via GET_CONFIG on panel open
- All saves write to Pico via SET_CONFIG
- PC stores nothing — close and reopen, same data (from Pico)
- Consider scrollable frame for all sections if window gets too tall
- CustomTkinter widgets: CTkEntry, CTkCheckBox, CTkSwitch, CTkSlider
