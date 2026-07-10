# pywinhello

Raspberry Pi Picoを「物理キー」として、Windows Helloの自動化を実現します。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/obichan117/pywinhello/actions/workflows/ci.yml/badge.svg)](https://github.com/obichan117/pywinhello/actions)

---

**[English](#english)** | **日本語（デフォルト）**

## 何をするもの？

Picoデバイスをパソコンに挿すだけで、Windows Helloの認証を全自動化します。

- **ロック画面** → 自動でPINを入力してログイン
- **Windows Helloダイアログ** → アプリごとに自動でPINを入力
- **毎朝のスリープ復帰** → スケジュールで自動起動 → 自動ログイン

## なぜ必要？

Windowsの認証画面（Credential Dialog）は **UIPI** という仕組みで保護されており、
ソフトウェアだけではPINを入力できません。
pywinhelloはRaspberry Pi PicoをUSBキーボードとして使うことで、この制限を突破します。

## どう動く？

```
挿す → 自動化ON        抜く → 自動化OFF
```

```
Picoデバイス（物理キー）           パソコン
┌─────────────────────┐          ┌──────────────────────┐
│  PIN（暗号化保存）    │   USB    │  バックグラウンド監視   │
│  スケジュール         │ ◄──────► │  ├ ロック画面 → UNLOCK │
│  アプリ設定           │  シリアル │  ├ Hello認証 → HELLO  │
│  イベントログ         │          │  └ 自動アップデート     │
│                      │          │                       │
│  キーボードとして      │          │  設定アプリ（GUI）     │
│  PINを自動入力        │          │  └ Picoの設定を読み書き │
└─────────────────────┘          └──────────────────────┘
```

**PINはデバイス本体にのみ暗号化保存** — パソコンやインターネットには一切保存されません。

## 対応デバイス

| デバイス | 対応 | Wi-Fi | おすすめ |
|---------|------|-------|---------|
| Raspberry Pi Pico | ✓ | — | |
| Raspberry Pi Pico H | ✓ | — | |
| Raspberry Pi Pico W | ✓ | ✓ | ★ おすすめ |
| Raspberry Pi Pico 2 | ✓ | — | |
| Raspberry Pi Pico 2 W | ✓ | ✓ | ★ おすすめ |

Wi-Fi対応モデルは、スリープ中のパソコンを自動で起動する機能が使えます。

## セットアップ（3ステップ）

### 1. Picoデバイスを購入
[Raspberry Pi Pico W](https://www.raspberrypi.com/products/raspberry-pi-pico/) — 約1,000円

### 2. セットアップツールをダウンロード
[最新版をダウンロード](https://github.com/obichan117/pywinhello/releases/latest)
→ `pywinhello_setup.exe` を実行

### 3. 画面の案内に従ってセットアップ
- Picoデバイスを接続
- 動作テスト（メモ帳で自動入力を確認）
- PINを登録
- スケジュールを設定

**完了！** 毎朝自動でパソコンが起動・ログインします。

## よくある質問

**Q: PINは安全ですか？**
A: PINはPicoデバイス本体にのみAES-256で暗号化して保存されます。パソコンのディスクやインターネット上には一切保存されません。Picoを抜けば、パソコンにPINの情報は残りません。

**Q: どのPicoを買えばいいですか？**
A: どのモデルでも動作しますが、**Pico W** または **Pico 2 W**（Wi-Fi対応）がおすすめです。Wi-Fiがあると、スリープ中のパソコンを自動で起動する機能が使えます。

**Q: シャットダウンしても動きますか？**
A: シャットダウンからの自動起動はできません。**スリープ**をご利用ください。
（スタート → 電源 → スリープ）

**Q: 設定を変えたい時は？**
A: スタートメニューから「pywinhello」を開くと、スケジュールやPINの変更ができます。

**Q: アンインストールしたい時は？**
A: Windowsの設定 → アプリ → pywinhello → アンインストール

## CLIを使う（上級者向け）

GUI（セットアップウィザード・設定パネル・システムトレイ）は、コマンドラインツール `pywinhello` と同じコアロジックを薄くラップしたものです。自動化やスクリプトからは直接CLIを使えます。

```
pywinhello setup                     # 初回セットアップ（ファームウェア書き込み→PIN登録→スケジュール設定）
pywinhello status [--json]           # 現在の状態を表示
pywinhello doctor                    # 問題を診断（ファームウェア/PIN/スケジュール/接続）
pywinhello config get [<key>]        # 設定を読み取る（例: schedule.time）
pywinhello config set <key>=<value>  # 設定を書き込む（例: schedule.time=08:00）
pywinhello pin set                   # PINを登録（対話的に入力、確認あり）
pywinhello test lock                 # ロック→自動アンロックのテスト
pywinhello test type                 # メモ帳への自動入力テスト
pywinhello update check              # ソフトウェア/ファームウェアの更新を確認
pywinhello serve                     # バックグラウンド監視サービスをフォアグラウンドで起動
```

**設定はPicoデバイス本体にのみ保存されます。** パソコン上には設定ファイルを一切保存しません — 読み書きはすべてシリアル経由でPicoに対して行われます。

**PINをコマンドライン引数として渡すことはできません。** `pywinhello pin set` は常に対話的にPINの入力を求めます（画面には表示されず、確認入力あり）。シェル履歴やプロセス一覧にPINが残らないようにするためです。

---

<a name="english"></a>

## English

### What

Plug in a Raspberry Pi Pico and it automatically handles all Windows Hello authentication — lock screen login, per-app PIN dialogs, and scheduled wake-from-sleep.

- **Plug in** → automation ON
- **Unplug** → automation OFF
- **PIN stored on device only** — AES-256 encrypted, never on PC or internet

### Why

Windows Hello's Credential Dialog is protected by **UIPI** (User Interface Privilege Isolation). No software input method — `SendInput`, pyautogui, pywinauto — can type into it. A USB HID keyboard bypasses this restriction because the OS trusts physical input devices unconditionally.

### How

The Pico runs C firmware that presents as a dual USB device: HID keyboard (types PIN) + CDC serial (receives commands from the PC). A background monitor on the PC detects lock screens and Hello dialogs, then tells the Pico when to type.

- **Lock screen**: PC detects lock → sends `UNLOCK` → Pico types PIN + Enter
- **Windows Hello**: PC detects dialog → checks per-app whitelist → sends `HELLO` → Pico types PIN
- **Boot unlock**: Pico detects cold boot → waits → blind-types PIN (no daemon needed)
- **Pico W bonus**: independently wakes PC from sleep at scheduled time via USB remote wakeup

### Setup (3 steps)

1. **Buy a Pico** — [Raspberry Pi Pico W](https://www.raspberrypi.com/products/raspberry-pi-pico/) (~$6)
2. **Download** — [Latest release](https://github.com/obichan117/pywinhello/releases/latest) → run `pywinhello_setup.exe`
3. **Follow the wizard** — connect Pico, test, enter PIN, set schedule

### Using the CLI

The GUI (setup wizard, settings panel, system tray icon) is a thin wrapper over the same core logic as the `pywinhello` command-line tool. Use the CLI directly for automation or scripting.

```
pywinhello setup                     # first-time setup: flash firmware, register PIN, set schedule
pywinhello status [--json]           # show current status
pywinhello doctor                    # diagnose problems (firmware/PIN/schedule/connection)
pywinhello config get [<key>]        # read config (e.g. schedule.time)
pywinhello config set <key>=<value>  # write config (e.g. schedule.time=08:00)
pywinhello pin set                   # register a PIN (interactive, hidden, confirmed)
pywinhello test lock                 # test lock screen -> auto unlock
pywinhello test type                 # test auto-typing into Notepad
pywinhello update check              # check for software/firmware updates
pywinhello serve                     # run the background monitor service in the foreground
```

**Config lives on the device** — pywinhello never writes a config file to the PC; every read/write goes over serial to the Pico.

**The PIN is never a CLI flag.** `pywinhello pin set` always prompts interactively (hidden input, confirmed) so it never appears in shell history or a process listing.

### Developer Guide

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture, building from source, and serial protocol reference.

## License

MIT
