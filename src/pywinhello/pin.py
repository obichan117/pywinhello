"""PIN entry orchestration — two-pass detection and entry.

Handles unpredictable Windows Hello dialog state:
1. **PIN mode** (dialog has PIN field active): type PIN + ENTER -> done.
2. **Fingerprint/other mode**: first PIN attempt is ignored (no text field
   has focus), then ``pin_select_keys`` navigates to PIN entry, and PIN
   is re-entered.
"""

from __future__ import annotations

import logging
import time

from pywinhello import dialog
from pywinhello.hid import HIDKeyboard
from pywinhello.models import AuthEvent

logger = logging.getLogger(__name__)


def enter_pin(
    pin: str,
    *,
    port: str | None = None,
    inter_key_delay_ms: int = 50,
    pin_select_keys: list[str] | None = None,
    dialog_timeout: float = 10.0,
    dismiss_timeout: float = 5.0,
    _keyboard: HIDKeyboard | None = None,
) -> AuthEvent:
    """Send Windows Hello PIN via USB HID keyboard.

    This is the main entry point for one-shot PIN entry. It waits for the
    Windows Security dialog, focuses it, types the PIN, and reports the result.

    Args:
        pin: The Windows Hello PIN to enter.
        port: COM port for Pico. None = auto-detect.
        inter_key_delay_ms: Delay between keystrokes in ms.
        pin_select_keys: Keys to navigate from fingerprint to PIN mode.
            Defaults to ``['ESCAPE']``.
        dialog_timeout: Seconds to wait for the dialog to appear.
        dismiss_timeout: Seconds to wait for dialog dismissal after PIN entry.
        _keyboard: Inject a HIDKeyboard instance (for testing).

    Returns:
        AuthEvent with the outcome.
    """
    if pin_select_keys is None:
        pin_select_keys = ["ESCAPE"]

    event = AuthEvent()
    start = time.time()

    # Wait for dialog
    if not dialog.wait_for_dialog(timeout=dialog_timeout):
        event.error = "Windows Security dialog not found"
        event.elapsed = time.time() - start
        return event

    # Identify owner process
    event.owner_exe = dialog.get_owner_exe()

    # Focus dialog
    dialog.focus()
    time.sleep(1.0)

    try:
        kb = _keyboard or HIDKeyboard(port=port)
        owns_kb = _keyboard is None
        try:
            if inter_key_delay_ms:
                kb.set_delay(inter_key_delay_ms)

            # Stage 1: Try PIN directly (works if dialog is in PIN mode)
            kb.type_text(pin)
            kb.press_key("ENTER")
            event.pin_sent = True

            if dialog.wait_for_dismiss(timeout=dismiss_timeout):
                event.dialog_dismissed = True
                event.elapsed = time.time() - start
                logger.info("PIN accepted on first attempt (PIN mode)")
                return event

            # Stage 2: Fingerprint fallback — navigate to PIN mode
            logger.info("Dialog still open — trying fingerprint fallback")
            dialog.focus()
            time.sleep(0.5)

            for key in pin_select_keys:
                kb.press_key(key)
                time.sleep(0.5)
            time.sleep(1.5)

            # Stage 3: Re-enter PIN
            dialog.focus()
            time.sleep(0.5)
            kb.type_text(pin)
            kb.press_key("ENTER")

            if dialog.wait_for_dismiss(timeout=dismiss_timeout):
                event.dialog_dismissed = True
                logger.info("PIN accepted after fingerprint fallback")
            else:
                event.error = "Dialog still open after two attempts"
                logger.warning("PIN entry failed — dialog not dismissed")

        finally:
            if owns_kb:
                kb.close()

    except Exception as e:
        event.error = str(e)
        logger.error("PIN entry failed: %s", e)

    event.elapsed = time.time() - start
    return event
