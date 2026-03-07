"""Pico HID keyboard bridge — main loop.

Reads newline-delimited commands from the USB CDC data channel
and sends corresponding HID keystrokes.

Protocol (text, newline-delimited):
    Host -> Pico: "PING\\n"              -> Pico: "PONG\\n"
    Host -> Pico: "TYPE:hello\\n"        -> types "hello" -> "OK\\n"
    Host -> Pico: "PRESS:ENTER\\n"       -> sends Enter   -> "OK\\n"
    Host -> Pico: "COMBO:CTRL+C\\n"      -> sends Ctrl+C  -> "OK\\n"
    Host -> Pico: "DELAY:100\\n"         -> sets delay ms  -> "OK\\n"
    Error:                               -> "ERR:message\\n"
"""

import time

import usb_cdc
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode

KEY_MAP = {
    "CTRL": Keycode.CONTROL,
    "SHIFT": Keycode.SHIFT,
    "ALT": Keycode.ALT,
    "GUI": Keycode.GUI,
    "ENTER": Keycode.ENTER,
    "ESCAPE": Keycode.ESCAPE,
    "TAB": Keycode.TAB,
    "BACKSPACE": Keycode.BACKSPACE,
    "DELETE": Keycode.DELETE,
    "HOME": Keycode.HOME,
    "END": Keycode.END,
    "PAGE_UP": Keycode.PAGE_UP,
    "PAGE_DOWN": Keycode.PAGE_DOWN,
    "UP": Keycode.UP_ARROW,
    "DOWN": Keycode.DOWN_ARROW,
    "LEFT": Keycode.LEFT_ARROW,
    "RIGHT": Keycode.RIGHT_ARROW,
    "F1": Keycode.F1,
    "F2": Keycode.F2,
    "F3": Keycode.F3,
    "F4": Keycode.F4,
    "F5": Keycode.F5,
    "F6": Keycode.F6,
    "F7": Keycode.F7,
    "F8": Keycode.F8,
    "F9": Keycode.F9,
    "F10": Keycode.F10,
    "F11": Keycode.F11,
    "F12": Keycode.F12,
    "SPACE": Keycode.SPACE,
    "CAPS_LOCK": Keycode.CAPS_LOCK,
    "INSERT": Keycode.INSERT,
    "PRINT_SCREEN": Keycode.PRINT_SCREEN,
}

inter_key_delay_ms = 50

keyboard = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(keyboard)
serial = usb_cdc.data


def respond(msg):
    serial.write((msg + "\n").encode("utf-8"))


def handle_type(text):
    global inter_key_delay_ms
    for char in text:
        layout.write(char)
        if inter_key_delay_ms > 0:
            time.sleep(inter_key_delay_ms / 1000.0)
    respond("OK")


def handle_press(key_name):
    keycode = KEY_MAP.get(key_name)
    if keycode is None:
        respond(f"ERR:Unknown key: {key_name}")
        return
    keyboard.press(keycode)
    keyboard.release(keycode)
    respond("OK")


def handle_combo(combo_str):
    parts = combo_str.split("+")
    keycodes = []
    for part in parts:
        keycode = KEY_MAP.get(part)
        if keycode is None:
            respond(f"ERR:Unknown key in combo: {part}")
            return
        keycodes.append(keycode)
    for kc in keycodes:
        keyboard.press(kc)
    time.sleep(0.01)
    keyboard.release_all()
    respond("OK")


def handle_delay(value_str):
    global inter_key_delay_ms
    try:
        inter_key_delay_ms = int(value_str)
        respond("OK")
    except ValueError:
        respond(f"ERR:Invalid delay value: {value_str}")


HANDLERS = {
    "PING": lambda _: respond("PONG"),
    "TYPE": handle_type,
    "PRESS": handle_press,
    "COMBO": handle_combo,
    "DELAY": handle_delay,
}

print("HID Bridge ready")

while True:
    if serial.in_waiting:
        try:
            line = serial.readline().decode("utf-8").strip()
            if not line:
                continue
            if ":" in line:
                cmd, arg = line.split(":", 1)
            else:
                cmd, arg = line, ""
            handler = HANDLERS.get(cmd)
            if handler:
                handler(arg)
            else:
                respond(f"ERR:Unknown command: {cmd}")
        except Exception as e:
            try:
                respond(f"ERR:{e}")
            except Exception:
                pass
    time.sleep(0.001)
