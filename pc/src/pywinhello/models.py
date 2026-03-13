"""Pure data models — no I/O, no win32 dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthEvent:
    """Result of a single Windows Hello PIN entry attempt.

    The library can only observe dialog appearance/dismissal — actual
    authentication success is determined by the calling application
    (WebAuthn HRESULT is only visible to the requesting process).
    """

    owner_exe: str | None = None
    """Executable name of the process that triggered the dialog."""

    pin_sent: bool = False
    """Whether PIN keystrokes were sent via HID."""

    dialog_dismissed: bool = False
    """Whether the dialog disappeared after PIN entry."""

    elapsed: float = 0.0
    """Seconds from dialog detection to dismissal (or timeout)."""

    error: str | None = None
    """Error message if something went wrong."""
