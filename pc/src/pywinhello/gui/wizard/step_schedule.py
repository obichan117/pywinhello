"""Step 4/4: Schedule configuration (time picker + day checkboxes)."""

from __future__ import annotations

import logging

import customtkinter as ctk

from pywinhello.core import save_schedule
from pywinhello.gui.constants import DAY_KEYS, DEFAULT_DAYS
from pywinhello.gui.i18n import t
from pywinhello.gui.wizard.base import WizardStep

logger = logging.getLogger(__name__)


class ScheduleStep(WizardStep):
    """Step 4: Time picker + day checkboxes, sends SET_CONFIG to Pico."""

    @property
    def title(self) -> str:
        return t("wizard.step4.title")

    def build(self) -> None:
        # Description
        self._desc = ctk.CTkLabel(
            self.frame,
            text=t("wizard.step4.desc"),
            font=ctk.CTkFont(size=13),
            text_color="gray50",
        )
        self._desc.pack(pady=(0, 15))

        # Time picker section
        time_frame = ctk.CTkFrame(self.frame)
        time_frame.pack(fill="x", padx=40, pady=10)

        time_label = ctk.CTkLabel(
            time_frame,
            text=t("wizard.step4.time_label"),
            font=ctk.CTkFont(size=14),
            anchor="w",
        )
        time_label.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        # Hour
        self._hour_var = ctk.StringVar(value="07")
        hour_menu = ctk.CTkOptionMenu(
            time_frame,
            values=[f"{h:02d}" for h in range(24)],
            variable=self._hour_var,
            width=70,
        )
        hour_menu.grid(row=0, column=1, padx=(5, 2), pady=10)

        colon = ctk.CTkLabel(time_frame, text=":", font=ctk.CTkFont(size=16, weight="bold"))
        colon.grid(row=0, column=2, padx=2, pady=10)

        # Minute
        self._minute_var = ctk.StringVar(value="45")
        minute_menu = ctk.CTkOptionMenu(
            time_frame,
            values=[f"{m:02d}" for m in range(0, 60, 5)],
            variable=self._minute_var,
            width=70,
        )
        minute_menu.grid(row=0, column=3, padx=(2, 15), pady=10)

        # Day checkboxes
        days_frame = ctk.CTkFrame(self.frame)
        days_frame.pack(fill="x", padx=40, pady=10)

        days_label = ctk.CTkLabel(
            days_frame,
            text=t("wizard.step4.days_label"),
            font=ctk.CTkFont(size=14),
            anchor="w",
        )
        days_label.pack(anchor="w", padx=15, pady=(10, 5))

        checkbox_row = ctk.CTkFrame(days_frame, fg_color="transparent")
        checkbox_row.pack(padx=15, pady=(0, 10))

        self._day_vars: dict[str, ctk.BooleanVar] = {}
        for i, day_key in enumerate(DAY_KEYS):
            var = ctk.BooleanVar(value=day_key in DEFAULT_DAYS)
            self._day_vars[day_key] = var
            cb = ctk.CTkCheckBox(
                checkbox_row,
                text=t(f"wizard.step4.day_{day_key}"),
                variable=var,
                width=50,
                font=ctk.CTkFont(size=13),
            )
            cb.grid(row=0, column=i, padx=6, pady=5)

        # Sleep recommendation
        sleep_frame = ctk.CTkFrame(self.frame, fg_color=("gray90", "gray20"))
        sleep_frame.pack(fill="x", padx=40, pady=15)

        self._sleep_notice = ctk.CTkLabel(
            sleep_frame,
            text=t("wizard.step4.sleep_notice"),
            font=ctk.CTkFont(size=13, weight="bold"),
            justify="left",
        )
        self._sleep_notice.pack(padx=15, pady=(10, 2))

        self._sleep_guide = ctk.CTkLabel(
            sleep_frame,
            text=t("wizard.step4.sleep_guide"),
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
        )
        self._sleep_guide.pack(padx=15, pady=(2, 10))

        # Status
        self._status_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._status_label.pack(pady=10)

        # State
        self._saved = False

    def on_enter(self) -> None:
        self.wizard.nav_bar.set_next_text(t("wizard.btn_finish"))
        self.wizard.nav_bar.set_next_enabled(True)

    def on_leave(self) -> None:
        self.wizard.nav_bar.set_next_text(t("wizard.btn_next"))

    def can_proceed(self) -> bool:
        # Save before proceeding
        if not self._saved:
            self._save_schedule()
        return True

    def _get_schedule_data(self) -> dict:
        """Collect schedule values from the UI."""
        hour = self._hour_var.get()
        minute = self._minute_var.get()
        days = [k for k, v in self._day_vars.items() if v.get()]
        return {
            "time": f"{hour}:{minute}",
            "days": days,
        }

    def _save_schedule(self) -> None:
        """Send schedule to Pico synchronously (called from can_proceed)."""
        hour = int(self._hour_var.get())
        minute = int(self._minute_var.get())
        days = [k for k, v in self._day_vars.items() if v.get()]
        self._status_label.configure(
            text=t("wizard.step4.saving"), text_color="gray50"
        )

        try:
            from pywinhello.serial.protocol import SerialProtocol

            port = self.wizard.collected_data.get("port")
            if port is None:
                self._status_label.configure(
                    text=t("wizard.step4.save_failed", error="No port available"),
                    text_color="red",
                )
                self._saved = True
                return

            with SerialProtocol(port=port) as proto:
                try:
                    save_schedule(proto, hour, minute, days)
                    self._saved = True
                    self._status_label.configure(
                        text=t("wizard.step4.save_success"), text_color="green"
                    )
                except RuntimeError as e:
                    self._status_label.configure(
                        text=t("wizard.step4.save_failed", error=str(e)),
                        text_color="red",
                    )
        except Exception as e:
            logger.exception("Failed to save schedule")
            self._status_label.configure(
                text=t("wizard.step4.save_failed", error=str(e)),
                text_color="red",
            )
            # Allow proceeding even on save failure
            self._saved = True

    def get_data(self) -> dict:
        return {"schedule": self._get_schedule_data()}
