"""Pure data models — no I/O, no win32 dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass
class AppConfig:
    """Per-application PIN configuration."""

    exe: str
    """Process executable name (e.g. 'MarketSpeed2.exe')."""

    pin: str
    """Windows Hello PIN for this application."""



@dataclass
class MonitorConfig:
    """Configuration for the HelloMonitor daemon."""

    apps: list[AppConfig] = field(default_factory=list)
    """List of per-application configurations."""

    hid_port: str | None = None
    """COM port for Pico HID bridge. None = auto-detect."""

    inter_key_delay_ms: int = 50
    """Delay between keystrokes in milliseconds."""

    dialog_wait_timeout: float = 5.0
    """Seconds to wait for dialog to be ready after detection."""
