"""Setup wizard for first-time Pico configuration.

Four steps:
1. Device detection and firmware flashing
2. Notepad integration test with auto-calibration
3. PIN registration
4. Schedule configuration
"""

from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from pywinhello.gui.i18n import t
from pywinhello.gui.wizard.base import NavigationBar, ProgressBar, WizardStep
from pywinhello.gui.wizard.step_device import DeviceStep
from pywinhello.gui.wizard.step_pin import PinStep
from pywinhello.gui.wizard.step_schedule import ScheduleStep
from pywinhello.gui.wizard.step_test import TestStep


class SetupWizard(ctk.CTkFrame):
    """Four-step setup wizard shown on first run (no PIN on Pico).

    Collects device info, runs integration test, registers PIN,
    and configures the schedule. Calls ``on_complete`` when finished.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_complete: Callable[[], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._on_complete = on_complete
        self._on_cancel = on_cancel
        self.collected_data: dict[str, Any] = {}
        self._current_index = 0

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 5))

        self._title_label = ctk.CTkLabel(
            header,
            text=t("wizard.title"),
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self._title_label.pack(side="left")

        self._step_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="gray50",
        )
        self._step_label.pack(side="right")

        # Progress bar
        self._progress = ProgressBar(self, total_steps=4)
        self._progress.pack(fill="x", padx=40, pady=10)

        # Step title
        self._step_title = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._step_title.pack(pady=(5, 5))

        # Content area for step frames
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        # Navigation bar
        self.nav_bar = NavigationBar(
            self,
            on_back=self._go_back,
            on_next=self._go_next,
            on_cancel=self._cancel,
        )
        self.nav_bar.pack(fill="x", padx=20, pady=(5, 15))

        # Create steps
        self._steps: list[WizardStep] = [
            DeviceStep(self),
            TestStep(self),
            PinStep(self),
            ScheduleStep(self),
        ]

        # Show first step
        self._show_step(0)

    def _show_step(self, index: int) -> None:
        """Display the step at the given index."""
        # Hide current
        if 0 <= self._current_index < len(self._steps):
            self._steps[self._current_index].hide()

        self._current_index = index
        step = self._steps[index]

        # Update header
        self._step_label.configure(
            text=t("wizard.step_label", current=index + 1, total=len(self._steps))
        )
        self._step_title.configure(text=step.title)
        self._progress.set_step(index)

        # Update navigation
        self.nav_bar.set_back_enabled(index > 0)
        if index == len(self._steps) - 1:
            self.nav_bar.set_next_text(t("wizard.btn_finish"))
        else:
            self.nav_bar.set_next_text(t("wizard.btn_next"))

        # Show step
        step.show()

    def _go_next(self) -> None:
        """Advance to the next step (or finish)."""
        step = self._steps[self._current_index]
        if not step.can_proceed():
            return

        # Collect data from this step
        self.collected_data.update(step.get_data())

        if self._current_index < len(self._steps) - 1:
            self._show_step(self._current_index + 1)
        else:
            self._finish()

    def _go_back(self) -> None:
        """Go back to the previous step."""
        if self._current_index > 0:
            self._show_step(self._current_index - 1)

    def _cancel(self) -> None:
        """Cancel the wizard."""
        if self._on_cancel:
            self._on_cancel()

    def _finish(self) -> None:
        """Wizard complete — collect final data and notify parent."""
        step = self._steps[self._current_index]
        self.collected_data.update(step.get_data())

        if self._on_complete:
            self._on_complete()

    def refresh_i18n(self) -> None:
        """Update all text after a locale change."""
        self._title_label.configure(text=t("wizard.title"))
        self._step_label.configure(
            text=t(
                "wizard.step_label",
                current=self._current_index + 1,
                total=len(self._steps),
            )
        )
        step = self._steps[self._current_index]
        self._step_title.configure(text=step.title)
        self.nav_bar.refresh_text()


__all__ = ["SetupWizard"]
