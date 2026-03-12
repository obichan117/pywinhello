"""Live integration test for pywinhello.

Requires:
- Pico W connected via USB with firmware installed
- A way to trigger Windows Hello (e.g., MS2 passkey login)

Run manually:
    uv run python tests/integration/test_live_pin_entry.py

NOT included in default pytest collection.
"""

import logging
import os
import sys

from pywinhello import HIDKeyboard, enter_pin
from pywinhello.dialog import get_owner_exe, is_visible

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)


def test_ping():
    """Test Pico HID bridge connectivity."""
    print("\n=== Test: Ping ===")
    with HIDKeyboard() as kb:
        assert kb.ping(), "Pico did not respond to PING"
        print(f"PONG from {kb._port_name}")


def test_dialog_detection():
    """Test dialog detection (requires dialog to be visible)."""
    print("\n=== Test: Dialog Detection ===")
    if is_visible():
        exe = get_owner_exe()
        print(f"Dialog visible, owner: {exe}")
    else:
        print("No dialog visible (trigger Windows Hello to test)")


def test_enter_pin():
    """Test full PIN entry flow."""
    pin = os.environ.get("PYWINHELLO_PIN")
    if not pin:
        print("\n=== Test: Enter PIN (SKIPPED - set PYWINHELLO_PIN env var) ===")
        return

    print("\n=== Test: Enter PIN ===")
    print("Waiting for Windows Hello dialog...")
    event = enter_pin(pin, dialog_timeout=30.0)
    print(f"  owner_exe: {event.owner_exe}")
    print(f"  pin_sent: {event.pin_sent}")
    print(f"  dialog_dismissed: {event.dialog_dismissed}")
    print(f"  elapsed: {event.elapsed:.1f}s")
    print(f"  error: {event.error}")

    if event.dialog_dismissed:
        print("\n>> SUCCESS")
    else:
        print("\n>> FAILED")
        sys.exit(1)


if __name__ == "__main__":
    test_ping()
    test_dialog_detection()
    test_enter_pin()
    print("\n=== All tests complete ===")
