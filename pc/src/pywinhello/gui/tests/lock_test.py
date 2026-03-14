"""Lock/unlock test: lock workstation, wait for Pico to unlock, verify.

Used at the end of the wizard (optional) and from the settings panel
test button.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LockUnlockResult:
    """Result of the lock/unlock integration test."""

    locked: bool = False
    unlocked: bool = False
    elapsed: float = 0.0
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.locked and self.unlocked and self.error is None


def _lock_workstation() -> bool:
    """Lock the Windows desktop via user32.LockWorkStation()."""
    try:
        import ctypes

        return bool(ctypes.windll.user32.LockWorkStation())
    except Exception:
        return False


def _is_desktop_locked() -> bool:
    """Check if the desktop is currently locked.

    Uses OpenInputDesktop — if it fails, the desktop is locked.
    """
    try:
        import ctypes

        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
        if hdesk:
            ctypes.windll.user32.CloseDesktop(hdesk)
            return False
        return True
    except Exception:
        return True


class LockUnlockTest:
    """Lock/unlock integration test.

    Locks the workstation and waits for the Pico/monitor to unlock it.
    The monitor daemon (running separately) detects the lock and triggers
    the Pico to type the PIN.

    Usage::

        test = LockUnlockTest(timeout=30.0)
        result = test.run()
        if result.passed:
            print(f"Unlock took {result.elapsed:.1f}s")
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def run(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> LockUnlockResult:
        """Execute the lock/unlock test.

        Args:
            on_status: Optional callback ``(status: str)`` for progress updates.

        Returns:
            LockUnlockResult with timing and outcome.
        """
        result = LockUnlockResult()

        def _notify(msg: str) -> None:
            if on_status:
                on_status(msg)

        # Lock
        _notify("locking")
        if not _lock_workstation():
            result.error = "LockWorkStation failed"
            return result

        result.locked = True
        time.sleep(1.0)  # Brief wait for lock to take effect

        # Wait for unlock
        _notify("waiting")
        start = time.time()

        while time.time() - start < self._timeout:
            if not _is_desktop_locked():
                result.unlocked = True
                result.elapsed = time.time() - start
                _notify("unlocked")
                return result
            time.sleep(0.5)

        # Timeout
        result.elapsed = time.time() - start
        result.error = f"Unlock timed out after {self._timeout:.0f}s"
        _notify("timeout")
        return result


__all__ = ["LockUnlockTest", "LockUnlockResult"]
