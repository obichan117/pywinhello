"""Notepad typing test: launch, type, verify, calibrate, close.

Shared between wizard step 2 and the settings panel test button.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_TEST_STRING = "pywinhello test"
_SPEED_TEST_STRING = "The quick brown fox jumps over the lazy dog 1234567890"
_SPEED_INTERVALS = [50, 80, 100, 120, 150]


@dataclass
class NotepadTestResult:
    """Aggregate result of the full Notepad test suite."""

    notepad_opened: bool = False
    type_match: bool = False
    actual_text: str = ""
    optimal_interval: int | None = None
    speed_results: dict[int, bool] = field(default_factory=dict)
    special_keys_ok: bool = False
    notepad_closed: bool = False
    error: str | None = None

    @property
    def all_passed(self) -> bool:
        return (
            self.notepad_opened
            and self.type_match
            and self.optimal_interval is not None
            and self.special_keys_ok
            and self.notepad_closed
        )


def _get_clipboard() -> str:
    """Read Windows clipboard text."""
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
    """Empty the Windows clipboard."""
    try:
        import ctypes as _ct

        _ct.windll.user32.OpenClipboard(0)
        _ct.windll.user32.EmptyClipboard()
        _ct.windll.user32.CloseClipboard()
    except Exception:
        pass


class NotepadTest:
    """Full Notepad typing test with auto-calibration.

    Usage::

        test = NotepadTest(port="COM8")
        result = test.run()
        if result.all_passed:
            print(f"Optimal interval: {result.optimal_interval}ms")
    """

    def __init__(self, port: str | None = None) -> None:
        self._port = port
        self._proc: subprocess.Popen | None = None
        self._hid = None

    def _get_hid(self):
        from pywinhello.hid import HIDKeyboard

        if self._hid is None:
            self._hid = HIDKeyboard(port=self._port)
        return self._hid

    def _close_hid(self) -> None:
        if self._hid is not None:
            try:
                self._hid.close()
            except Exception:
                pass
            self._hid = None

    def _read_notepad(self) -> str:
        """Read Notepad content via Ctrl+A, Ctrl+C."""
        hid = self._get_hid()
        _clear_clipboard()
        hid.key_combo("CTRL", "A")
        time.sleep(0.2)
        hid.key_combo("CTRL", "C")
        time.sleep(0.3)
        return _get_clipboard().strip()

    def _clear_notepad(self) -> None:
        """Select all and delete in Notepad."""
        hid = self._get_hid()
        hid.key_combo("CTRL", "A")
        time.sleep(0.1)
        hid.press_key("DELETE")
        time.sleep(0.2)

    def run(
        self,
        on_step: None | (callable) = None,
    ) -> NotepadTestResult:
        """Execute the full test sequence.

        Args:
            on_step: Optional callback ``(step_name: str, status: str)``
                     called as each sub-test starts/completes.

        Returns:
            NotepadTestResult with all outcomes.
        """
        result = NotepadTestResult()

        def _notify(step: str, status: str) -> None:
            if on_step:
                on_step(step, status)

        # 1. Open Notepad
        _notify("open", "running")
        try:
            self._proc = subprocess.Popen(["notepad.exe"])
            time.sleep(1.5)
            result.notepad_opened = True
            _notify("open", "pass")
        except Exception as e:
            result.error = str(e)
            _notify("open", "fail")
            return result

        try:
            hid = self._get_hid()
        except Exception as e:
            result.error = f"HID connection failed: {e}"
            _notify("type", "fail")
            return result

        try:
            # 2. Type test string
            _notify("type", "running")
            _clear_clipboard()
            hid.type_text(_TEST_STRING)
            time.sleep(0.5)
            actual = self._read_notepad()
            result.actual_text = actual
            result.type_match = actual == _TEST_STRING
            _notify("type", "pass" if result.type_match else "fail")

            self._clear_notepad()

            # 3. Speed calibration
            _notify("speed", "running")
            for interval in _SPEED_INTERVALS:
                hid.set_delay(interval)
                time.sleep(0.2)
                _clear_clipboard()
                hid.type_text(_SPEED_TEST_STRING)
                time.sleep(0.8)
                text = self._read_notepad()
                ok = text == _SPEED_TEST_STRING
                result.speed_results[interval] = ok

                if ok and result.optimal_interval is None:
                    result.optimal_interval = interval
                    hid.set_delay(interval)
                    break

                self._clear_notepad()

            _notify("speed", "pass" if result.optimal_interval else "fail")

            self._clear_notepad()

            # 4. Special keys
            _notify("special", "running")
            hid.type_text("line1")
            hid.press_key("ENTER")
            hid.type_text("line2")
            time.sleep(0.5)
            text = self._read_notepad()
            result.special_keys_ok = (
                "line1" in text and "line2" in text and text.index("line2") > text.index("line1")
            )
            _notify("special", "pass" if result.special_keys_ok else "fail")

            # 5. Close Notepad
            _notify("close", "running")
            self._clear_notepad()
            hid.key_combo("ALT", "F4")
            time.sleep(1.0)
            # Dismiss save dialog
            try:
                hid.press_key("TAB")
                time.sleep(0.1)
                hid.press_key("ENTER")
            except Exception:
                pass
            time.sleep(0.5)
            result.notepad_closed = True
            _notify("close", "pass")

        except Exception as e:
            logger.exception("Notepad test error")
            result.error = str(e)
        finally:
            self._close_hid()

        return result


__all__ = ["NotepadTest", "NotepadTestResult"]
