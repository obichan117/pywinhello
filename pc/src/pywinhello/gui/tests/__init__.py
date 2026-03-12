"""Integration tests for Pico HID functionality.

- NotepadTest: types into Notepad, verifies, auto-calibrates
- LockUnlockTest: locks workstation, waits for Pico to unlock
"""

from pywinhello.gui.tests.lock_test import LockUnlockResult, LockUnlockTest
from pywinhello.gui.tests.notepad_test import NotepadTest, NotepadTestResult

__all__ = [
    "LockUnlockResult",
    "LockUnlockTest",
    "NotepadTest",
    "NotepadTestResult",
]
