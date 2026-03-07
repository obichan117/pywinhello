"""Pico W boot configuration — runs once at power-on.

Enables the USB CDC data channel alongside the default console channel.
The data channel is used for host <-> Pico serial communication.

Setup:
    1. Flash CircuitPython UF2 to Pico W
    2. Copy this file to CIRCUITPY/boot.py
    3. Copy code.py to CIRCUITPY/code.py
    4. Copy adafruit_hid library to CIRCUITPY/lib/adafruit_hid/
    5. Reset the Pico W
"""

import usb_cdc

# console=True  -> REPL serial (for debugging)
# data=True     -> second CDC serial (for host commands)
usb_cdc.enable(console=True, data=True)
