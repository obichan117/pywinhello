"""Base wizard step class with back/next navigation and progress indicator."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from pywinhello.gui.i18n import t

if TYPE_CHECKING:
    from pywinhello.gui.wizard import SetupWizard


class WizardStep(abc.ABC):
    """Abstract base class for a single wizard step.

    Each step owns a CTkFrame that is packed/unpacked by the wizard
    controller. Subclasses implement ``build()`` and ``on_enter()``.
    """

    def __init__(self, wizard: SetupWizard) -> None:
        self.wizard = wizard
        self.frame = ctk.CTkFrame(wizard.content_frame, fg_color="transparent")
        self._built = False

    @property
    @abc.abstractmethod
    def title(self) -> str:
        """Step title shown in the header."""

    @abc.abstractmethod
    def build(self) -> None:
        """Create all widgets inside ``self.frame``. Called once."""

    def on_enter(self) -> None:
        """Called every time this step becomes visible. Override for refresh logic."""

    def on_leave(self) -> None:
        """Called when navigating away from this step. Override for cleanup."""

    def can_proceed(self) -> bool:
        """Return True if the user is allowed to click Next. Override for validation."""
        return True

    def get_data(self) -> dict[str, Any]:
        """Return any data collected by this step. Override to provide step output."""
        return {}

    def show(self) -> None:
        """Display this step's frame."""
        if not self._built:
            self.build()
            self._built = True
        self.on_enter()
        self.frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    def hide(self) -> None:
        """Hide this step's frame."""
        self.on_leave()
        self.frame.pack_forget()


class ProgressBar(ctk.CTkFrame):
    """Horizontal step progress indicator: (1)---(2)---(3)---(4)."""

    def __init__(self, parent: ctk.CTkFrame, total_steps: int) -> None:
        super().__init__(parent, fg_color="transparent")
        self._total = total_steps
        self._circles: list[ctk.CTkLabel] = []
        self._lines: list[ctk.CTkFrame] = []

        for i in range(total_steps):
            circle = ctk.CTkLabel(
                self,
                text=str(i + 1),
                width=32,
                height=32,
                corner_radius=16,
                fg_color="gray60",
                text_color="white",
                font=ctk.CTkFont(size=14, weight="bold"),
            )
            circle.grid(row=0, column=i * 2, padx=2)
            self._circles.append(circle)

            if i < total_steps - 1:
                line = ctk.CTkFrame(self, height=3, fg_color="gray60")
                line.grid(row=0, column=i * 2 + 1, sticky="ew", padx=2)
                self.columnconfigure(i * 2 + 1, weight=1)
                self._lines.append(line)

    def set_step(self, step_index: int) -> None:
        """Highlight steps up to and including ``step_index`` (0-based)."""
        accent = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        if isinstance(accent, (list, tuple)):
            accent = accent[1]  # dark mode variant

        for i, circle in enumerate(self._circles):
            if i <= step_index:
                circle.configure(fg_color=accent)
            else:
                circle.configure(fg_color="gray60")

        for i, line in enumerate(self._lines):
            if i < step_index:
                line.configure(fg_color=accent)
            else:
                line.configure(fg_color="gray60")


class NavigationBar(ctk.CTkFrame):
    """Bottom bar with Back / Next / Cancel buttons."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_back: Any = None,
        on_next: Any = None,
        on_cancel: Any = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")

        self.btn_cancel = ctk.CTkButton(
            self,
            text=t("wizard.btn_cancel"),
            width=80,
            fg_color="transparent",
            border_width=1,
            text_color=("gray30", "gray70"),
            border_color=("gray30", "gray70"),
            command=on_cancel,
        )
        self.btn_cancel.pack(side="left", padx=(0, 10))

        self.btn_next = ctk.CTkButton(
            self,
            text=t("wizard.btn_next"),
            width=100,
            command=on_next,
        )
        self.btn_next.pack(side="right", padx=(10, 0))

        self.btn_back = ctk.CTkButton(
            self,
            text=t("wizard.btn_back"),
            width=80,
            fg_color="transparent",
            border_width=1,
            text_color=("gray30", "gray70"),
            border_color=("gray30", "gray70"),
            command=on_back,
        )
        self.btn_back.pack(side="right")

    def set_back_enabled(self, enabled: bool) -> None:
        self.btn_back.configure(state="normal" if enabled else "disabled")

    def set_next_enabled(self, enabled: bool) -> None:
        self.btn_next.configure(state="normal" if enabled else "disabled")

    def set_next_text(self, text: str) -> None:
        self.btn_next.configure(text=text)

    def refresh_text(self) -> None:
        """Re-apply i18n strings (after locale change)."""
        self.btn_cancel.configure(text=t("wizard.btn_cancel"))
        self.btn_back.configure(text=t("wizard.btn_back"))
        self.btn_next.configure(text=t("wizard.btn_next"))
