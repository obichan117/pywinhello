"""GUI-independent diagnostics: Notepad typing test, lock/unlock test.

Notepad sequence is extracted from gui/wizard/step_test.py, replacing the ctk
per-step status labels with a single (message, progress) callback so a CLI
`test` command can drive it without importing gui. LockUnlockTest is already
ctk-independent (gui/tests/lock_test.py) and is re-exported as-is.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from pywinhello.gui.tests.lock_test import LockUnlockResult, LockUnlockTest
from pywinhello.serial.protocol import Command, SerialProtocol

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float], None]

_TEST_STRING = "pywinhello test"
_SPEED_TEST_STRING = "The quick brown fox jumps over the lazy dog 1234567890"
_SPEED_INTERVALS = [50, 80, 100, 120, 150]


@dataclass
class TypeTestResult:
    notepad_opened: bool = False
    type_match: bool = False
    optimal_interval: int | None = None
    special_keys_ok: bool = False
    notepad_closed: bool = False
    error: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.notepad_opened
            and self.type_match
            and self.optimal_interval is not None
            and self.special_keys_ok
            and self.notepad_closed
        )


def _get_clipboard_text() -> str:
    """Read text from the Windows clipboard via ctypes."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes as _ct

        CF_UNICODETEXT = 13
        user32 = _ct.windll.user32
        kernel32 = _ct.windll.kernel32

        user32.OpenClipboard(0)
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                kernel32.GlobalLock.restype = _ct.c_wchar_p
                text = kernel32.GlobalLock(handle)
                kernel32.GlobalUnlock(handle)
                return text or ""
        finally:
            user32.CloseClipboard()
    except Exception:
        pass
    return ""


def _clear_clipboard() -> None:
    """Empty the Windows clipboard via ctypes."""
    if sys.platform != "win32":
        return
    try:
        import ctypes as _ct

        _ct.windll.user32.OpenClipboard(0)
        _ct.windll.user32.EmptyClipboard()
        _ct.windll.user32.CloseClipboard()
    except Exception:
        pass


def run_notepad_type_test(
    port: str,
    on_progress: ProgressCallback | None = None,
) -> TypeTestResult:
    """Open Notepad, type/verify text, calibrate keystroke speed, close Notepad.

    Args:
        port: COM port of the connected Pico.
        on_progress: Optional callback (message, progress 0..1).

    Returns:
        TypeTestResult with per-stage outcomes.
    """
    progress = on_progress or (lambda message, fraction: None)
    result = TypeTestResult()

    progress("Opening Notepad...", 0.0)
    try:
        subprocess.Popen(["notepad.exe"])
        time.sleep(1.5)
        result.notepad_opened = True
    except Exception as e:
        result.error = f"Failed to open Notepad: {e}"
        return result

    try:
        proto = SerialProtocol(port=port)
    except Exception as e:
        result.error = f"Serial connection failed: {e}"
        return result

    try:
        # Type + verify
        progress("Typing test string...", 0.2)
        _clear_clipboard()
        proto.send_checked(Command.TYPE, _TEST_STRING)
        time.sleep(0.5)
        proto.send_checked(Command.COMBO, "CTRL+A")
        time.sleep(0.2)
        proto.send_checked(Command.COMBO, "CTRL+C")
        time.sleep(0.3)
        result.type_match = _get_clipboard_text().strip() == _TEST_STRING

        proto.send_checked(Command.COMBO, "CTRL+A")
        time.sleep(0.1)
        proto.send_checked(Command.PRESS, "DELETE")
        time.sleep(0.2)

        # Speed calibration
        progress("Calibrating keystroke speed...", 0.4)
        for interval in _SPEED_INTERVALS:
            proto.send_checked(Command.DELAY, str(interval))
            time.sleep(0.2)
            _clear_clipboard()
            proto.send_checked(Command.TYPE, _SPEED_TEST_STRING)
            time.sleep(0.8)
            proto.send_checked(Command.COMBO, "CTRL+A")
            time.sleep(0.2)
            proto.send_checked(Command.COMBO, "CTRL+C")
            time.sleep(0.3)
            if _get_clipboard_text().strip() == _SPEED_TEST_STRING:
                result.optimal_interval = interval
                proto.send_checked(Command.DELAY, str(interval))
                break
            proto.send_checked(Command.PRESS, "DELETE")
            time.sleep(0.2)

        proto.send_checked(Command.COMBO, "CTRL+A")
        time.sleep(0.1)
        proto.send_checked(Command.PRESS, "DELETE")
        time.sleep(0.2)

        # Special keys
        progress("Testing special keys...", 0.6)
        proto.send_checked(Command.TYPE, "line1")
        proto.send_checked(Command.PRESS, "ENTER")
        proto.send_checked(Command.TYPE, "line2")
        time.sleep(0.5)
        proto.send_checked(Command.COMBO, "CTRL+A")
        time.sleep(0.2)
        proto.send_checked(Command.COMBO, "CTRL+C")
        time.sleep(0.3)
        text = _get_clipboard_text().strip()
        result.special_keys_ok = (
            "line1" in text and "line2" in text and text.index("line2") > text.index("line1")
        )

        # Close Notepad
        progress("Closing Notepad...", 0.8)
        proto.send_checked(Command.COMBO, "CTRL+A")
        time.sleep(0.1)
        proto.send_checked(Command.PRESS, "DELETE")
        time.sleep(0.2)
        proto.send_checked(Command.COMBO, "ALT+F4")
        time.sleep(1.0)
        try:
            proto.send_checked(Command.PRESS, "TAB")
            time.sleep(0.1)
            proto.send_checked(Command.PRESS, "ENTER")
        except Exception:
            pass
        time.sleep(0.5)
        result.notepad_closed = True
        progress("Test complete.", 1.0)

    except Exception as e:
        logger.exception("Notepad type test failed")
        result.error = str(e)
    finally:
        proto.close()

    return result


__all__ = ["LockUnlockResult", "LockUnlockTest", "TypeTestResult", "run_notepad_type_test"]
