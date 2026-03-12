"""PIN entry — type PIN into Windows Hello dialog via USB HID.

Handles two dialog modes:
1. **PIN mode**: type PIN + ENTER → dialog dismisses → success.
2. **Fingerprint mode**: keystrokes ignored → close dialog with ESCAPE →
   caller retries (dialog randomly picks mode on each open).
"""

from __future__ import annotations

import logging
import os
import time

from pywinhello import dialog
from pywinhello.hid import HIDKeyboard
from pywinhello.models import AuthEvent

logger = logging.getLogger(__name__)

_PIN_ENV_VAR = "PYWINHELLO_PIN"


def _resolve_pin() -> str | None:
    """Read PIN from process env, falling back to user-level registry.

    On Windows, user-level env vars set after the current process started
    are not visible via ``os.environ``.  We fall back to reading directly
    from the Windows registry (HKCU\\Environment).
    """
    pin = os.environ.get(_PIN_ENV_VAR)
    if pin:
        return pin

    # Windows: read user-level env var from registry
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, _PIN_ENV_VAR)
            return str(value) if value else None
    except (ImportError, OSError):
        return None


def enter_pin(
    pin: str | None = None,
    *,
    port: str | None = None,
    inter_key_delay_ms: int = 50,
    dialog_timeout: float = 10.0,
    dismiss_timeout: float = 5.0,
    _keyboard: HIDKeyboard | None = None,
) -> AuthEvent:
    """Send Windows Hello PIN via USB HID keyboard.

    Waits for the Windows Security dialog, focuses it, types the PIN,
    and reports the result. If the dialog is in fingerprint mode (PIN
    keystrokes ignored), closes it with ESCAPE so the caller can retry.

    Args:
        pin: The Windows Hello PIN. If None, reads from ``PYWINHELLO_PIN``
            env var or Windows user-level registry.
        port: COM port for Pico. None = auto-detect.
        inter_key_delay_ms: Delay between keystrokes in ms.
        dialog_timeout: Seconds to wait for the dialog to appear.
        dismiss_timeout: Seconds to wait for dialog dismissal after PIN entry.
        _keyboard: Inject a HIDKeyboard instance (for testing).

    Returns:
        AuthEvent with the outcome. Check ``event.error == "fingerprint_mode"``
        to know if the caller should retry.

    Raises:
        ValueError: If no PIN is provided and ``PYWINHELLO_PIN`` is not set.
    """
    if pin is None:
        pin = _resolve_pin()
    if not pin:
        raise ValueError(
            f"No PIN provided and {_PIN_ENV_VAR} environment variable is not set"
        )

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
    time.sleep(0.3)

    # Verify the credential dialog actually has focus before sending keystrokes.
    # HID input goes to whichever window is foreground — if the user clicked
    # elsewhere during the settle delay, we must NOT type the PIN.
    if not dialog.is_foreground():
        # Try once more to reclaim focus
        dialog.focus()
        time.sleep(0.3)
        if not dialog.is_foreground():
            event.error = "credential dialog lost focus — aborting to avoid PIN leak"
            event.elapsed = time.time() - start
            logger.warning(event.error)
            return event

    try:
        kb = _keyboard or HIDKeyboard(port=port)
        owns_kb = _keyboard is None
        try:
            if inter_key_delay_ms:
                kb.set_delay(inter_key_delay_ms)

            # Final focus gate right before first keystroke
            if not dialog.is_foreground():
                event.error = "credential dialog lost focus — aborting to avoid PIN leak"
                event.elapsed = time.time() - start
                logger.warning(event.error)
                return event

            # Type PIN + ENTER.
            # PIN mode: text goes into the PIN field → dialog dismisses.
            # Fingerprint mode: no text field has focus → keystrokes ignored.
            kb.type_text(pin)
            kb.press_key("ENTER")
            event.pin_sent = True

            if dialog.wait_for_dismiss(timeout=dismiss_timeout):
                event.dialog_dismissed = True
                logger.info("PIN accepted")
            else:
                # Dialog still open → likely fingerprint mode.
                # Close it so the calling app can retry and hopefully
                # get PIN mode next time.
                logger.info("Dialog still open (fingerprint mode?) — closing with ESCAPE")
                kb.press_key("ESCAPE")
                dialog.wait_for_dismiss(timeout=3.0)
                event.error = "fingerprint_mode"

        finally:
            if owns_kb:
                kb.close()

    except Exception as e:
        event.error = str(e)
        logger.error("PIN entry failed: %s", e)

    event.elapsed = time.time() - start
    return event
