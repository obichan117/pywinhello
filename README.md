# pywinhello

Raspberry Pi Picoを「物理キー」として、Windows Helloの自動化を実現します。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

**[English](#english)** | **日本語（デフォルト）**

## pywinhelloとは？

Picoデバイスをパソコンに挿すだけで、毎朝自動でパソコンのロックを解除し、
Windows Helloの認証を自動化します。

- **挿す** → 自動化ON
- **抜く** → 自動化OFF
- **PINはデバイス本体にのみ保存** — パソコンやインターネットには一切保存されません

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

## 仕組み

```
Picoデバイス（物理キー）           パソコン
┌─────────────────────┐          ┌──────────────────────┐
│  PIN（暗号化保存）    │   USB    │  pywinhello          │
│  スケジュール         │ ◄──────► │  ├ ロック画面検出      │
│  設定                │  シリアル │  ├ Windows Hello検出   │
│                      │          │  └ 自動アップデート     │
│  USBキーボードとして   │          │                       │
│  PINを自動入力        │          │  設定アプリ            │
└─────────────────────┘          └──────────────────────┘
```

## よくある質問

**Q: PINは安全ですか？**
A: PINはPicoデバイス本体にのみ暗号化して保存されます。パソコンのディスクやインターネット上には一切保存されません。Picoを抜けば、パソコンにPINの情報は残りません。

**Q: どのPicoを買えばいいですか？**
A: どのモデルでも動作しますが、**Pico W** または **Pico 2 W**（Wi-Fi対応）がおすすめです。Wi-Fiがあると、スリープ中のパソコンを自動で起動する機能が使えます。

**Q: シャットダウンしても動きますか？**
A: シャットダウンからの自動起動はできません。**スリープ**をご利用ください。
（スタート → 電源 → スリープ）

**Q: 設定を変えたい時は？**
A: スタートメニューから「pywinhello」を開くと、スケジュールやPINの変更ができます。

**Q: アンインストールしたい時は？**
A: Windowsの設定 → アプリ → pywinhello → アンインストール

---

<a name="english"></a>

## English

### What is pywinhello?

Plug in a Raspberry Pi Pico and it automatically unlocks your Windows PC every morning and handles Windows Hello authentication.

- **Plug in** → automation ON
- **Unplug** → automation OFF
- **PIN stored on device only** — never on PC or internet

### Setup (3 steps)

1. **Buy a Pico** — [Raspberry Pi Pico W](https://www.raspberrypi.com/products/raspberry-pi-pico/) (~$6)
2. **Download** — [Latest release](https://github.com/obichan117/pywinhello/releases/latest) → run `pywinhello_setup.exe`
3. **Follow the wizard** — connect Pico, test, enter PIN, set schedule

### How it works

The Pico acts as a USB keyboard that types your PIN. Windows sees it as a physical keyboard, bypassing UIPI restrictions that block software-based input.

- **Lock screen**: Pico types PIN + Enter when PC wakes from sleep
- **Windows Hello dialogs**: Pico types PIN when apps request authentication
- **Boot unlock**: Pico detects cold boot and types PIN after Windows loads
- **Pico W bonus**: independently wakes PC from sleep at scheduled time via USB

### Developer Guide

See [CONTRIBUTING.md](CONTRIBUTING.md) for building from source, architecture, and serial protocol reference.

## License

MIT
