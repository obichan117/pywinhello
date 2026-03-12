# Quick Start

## Install

```bash
pip install pywinhello
```

## Prerequisites

1. A Raspberry Pi Pico (W, 2, or 2W) connected via USB
2. Firmware installed (see [Hardware Setup](hardware.md) or use `pywinhello setup-pico`)

## One-shot PIN entry

```python
from pywinhello import enter_pin

# When Windows Hello dialog appears, enter PIN
event = enter_pin("1234")

if event.dialog_dismissed:
    print(f"PIN accepted! (took {event.elapsed:.1f}s)")
elif event.error:
    print(f"Failed: {event.error}")
```

### Options

```python
event = enter_pin(
    pin="1234",
    port="COM8",              # explicit port (default: auto-detect)
    inter_key_delay_ms=50,    # delay between keystrokes
    pin_select_keys=["ESCAPE"],  # keys to navigate from fingerprint to PIN
    dialog_timeout=10.0,      # seconds to wait for dialog
    dismiss_timeout=5.0,      # seconds to wait for dismissal
)
```

## Process-aware daemon

Create `config.yaml`:

```yaml
apps:
  - exe: MarketSpeed2.exe
    pin: "1234"
  - exe: chrome.exe
    pin: "5678"
    pin_select_keys: ["ESCAPE"]

hid_port: auto           # or "COM8"
inter_key_delay_ms: 50
dialog_wait_timeout: 5.0
```

Run the monitor:

```python
from pywinhello import HelloMonitor, load_config

config = load_config("config.yaml")
monitor = HelloMonitor(config)

# Handle next dialog (one-shot)
event = monitor.handle_next(timeout=60.0)
print(f"Handled {event.owner_exe}: dismissed={event.dialog_dismissed}")

# Or run as daemon
monitor.serve(on_event=lambda e: print(e))
```

## CLI

```bash
# Set up a Pico (flash CircuitPython + firmware)
pywinhello setup-pico

# Ping the Pico HID bridge
pywinhello ping

# Run monitor daemon
pywinhello serve -c config.yaml
```

## How it works

1. **Dialog detection** — WinEvent hook (`EVENT_OBJECT_CREATE`) detects the `Credential Dialog Xaml Host` window instantly
2. **Process identification** — `GetWindow(GW_OWNER)` traces the dialog back to the requesting process
3. **PIN lookup** — Maps the process exe name to a PIN from your config
4. **Focus** — `AttachThreadInput` + `SetForegroundWindow` brings the dialog to focus (required for HID keystrokes)
5. **Two-pass entry** — Types PIN directly (assumes PIN mode); if dialog persists, navigates from fingerprint mode via configurable keys and retries
6. **HID bypass** — Physical keyboard input from the Pico bypasses UIPI restrictions
