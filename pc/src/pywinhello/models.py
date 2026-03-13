"""Pure data models — no I/O, no win32 dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BoardVariant(Enum):
    """Pico board variants — determines which firmware binary to flash."""

    PICO = "pico"
    PICO_W = "pico_w"
    PICO_2 = "pico_2"
    PICO_2_W = "pico_2_w"


# Adafruit VID used by all Raspberry Pi Pico boards
PICO_VID = 0x239A

# USB PID → board variant mapping
BOARD_BY_PID: dict[int, BoardVariant] = {
    0x80F4: BoardVariant.PICO,
    0x8058: BoardVariant.PICO_W,
    0x8120: BoardVariant.PICO_W,
    0x8150: BoardVariant.PICO_2,
    0x8160: BoardVariant.PICO_2_W,
}


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
