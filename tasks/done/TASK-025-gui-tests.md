# TASK-025: GUI — Integration Tests (Notepad + Lock/Unlock)

**Status**: todo
**Priority**: high
**Phase**: 4 — GUI

## Description
Visible, tangible tests that prove the Pico works. Users see actual typing happen on screen. Includes auto-calibration of keystroke timing.

## Acceptance Criteria

### Notepad Typing Test (Step 2 of wizard)
- [ ] ① メモ帳を開く — launch `notepad.exe`, wait for window + focus
- [ ] ② テスト文字列を入力:
  - Send `TYPE:pywinhello test <date>` to Pico
  - Read Notepad content (Ctrl+A → Ctrl+C → clipboard, or UIA)
  - Compare sent vs received → ✓ 一致 / ✗ 不一致
- [ ] ③ 入力速度テスト:
  - Type longer string at configured interval
  - If characters dropped → auto-increase interval (50 → 80 → 100 → 120 → 150)
  - Retry at each interval until pass
  - Save optimal interval to Pico config
  - Display: "50ミリ秒間隔: ✓ 正常"
- [ ] ④ 特殊キーテスト:
  - Send Enter → verify new line in Notepad
  - Send Tab → verify tab character
  - Display: ✓ 成功
- [ ] ⑤ メモ帳を閉じる:
  - Ctrl+A → Delete → Alt+F4 → handle "保存しますか" dialog
  - Display: ✓ 成功

### Failure Handling
- [ ] Character mismatch → auto-adjust interval, show "再テスト" button
- [ ] All intervals fail → show troubleshooting tips:
  - "USBハブを使っている → 直接接続してください"
  - "別のポートを試す"
- [ ] "※ テスト中はキーボードやマウスに触れないでください" warning

### Lock/Unlock Live Test (end of wizard, optional)
- [ ] Confirmation dialog: "パソコンをロックし、自動解除をテストします"
- [ ] Safety note: "ロック解除できない場合は手動でPINを入力してください"
- [ ] Call `LockWorkStation()` → desktop locks
- [ ] Monitor detects lock → sends UNLOCK → Pico types PIN
- [ ] Verify desktop unlocked → show "✓ ロック解除テスト成功 (N.N秒)"
- [ ] Failure → "手動でPINを入力してロック解除してください" + "PINを変更" / "再テスト"

### Settings Panel Test Button
- [ ] Same lock/unlock test available from settings panel via "テスト" button
- [ ] For re-verification after changing PIN or timing settings

## Notes
- Notepad read: simplest is clipboard (Ctrl+A, Ctrl+C, read clipboard via ctypes/win32clipboard)
- Alternative: UI Automation to read Notepad text control — more reliable but heavier
- Lock test: `ctypes.windll.user32.LockWorkStation()` — standard API
- The test code is shared between wizard and settings panel "テスト" button
