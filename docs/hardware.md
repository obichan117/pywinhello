# Hardware Setup

## Supported boards

Any Raspberry Pi Pico variant running CircuitPython:

| Board | USB PID |
|-------|---------|
| Pico W | 0x8058, 0x8120 |
| Pico (non-W) | 0x80F4 |
| Pico 2 | 0x8150 |
| Pico 2 W | 0x8160 |

All use Adafruit VID `0x239A`.

## Flash CircuitPython

1. Hold the **BOOTSEL** button while plugging in the Pico via USB
2. A drive named `RPI-RP2` appears
3. Download the CircuitPython `.uf2` for your board from [circuitpython.org](https://circuitpython.org/downloads)
4. Copy the `.uf2` file to the `RPI-RP2` drive
5. The Pico reboots and a `CIRCUITPY` drive appears

## Install firmware

Copy the firmware files from `firmware/pico_hid/` to the Pico:

```
CIRCUITPY/
├── boot.py          <- firmware/pico_hid/boot.py
├── code.py          <- firmware/pico_hid/code.py
└── lib/
    └── adafruit_hid/ <- download from circuitpython.org/libraries
```

!!! important
    You must also download the `adafruit_hid` library bundle from
    [circuitpython.org/libraries](https://circuitpython.org/libraries)
    and copy the `adafruit_hid/` folder to `CIRCUITPY/lib/`.

## Verify

After resetting the Pico:

```bash
pywinhello ping
# PONG from COM8
```

## Serial protocol

The Pico communicates via CDC serial (text, newline-delimited):

| Command | Response | Description |
|---------|----------|-------------|
| `PING` | `PONG` | Health check |
| `TYPE:1234` | `OK` | Type characters |
| `PRESS:ENTER` | `OK` | Press named key |
| `COMBO:CTRL+C` | `OK` | Key combination |
| `DELAY:100` | `OK` | Set inter-key delay (ms) |

## Two CDC ports

`boot.py` enables two CDC channels: console (REPL) and data. The host library auto-detects the data port by picking the highest-numbered COM port among VID:PID matches.
