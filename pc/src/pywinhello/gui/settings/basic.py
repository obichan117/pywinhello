"""Basic settings: PIN status + change, schedule time/day picker."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from pywinhello.gui.constants import DAY_KEYS, validate_pin
from pywinhello.gui.i18n import t

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BasicSettings(ctk.CTkFrame):
    """PIN status + change button, schedule time/day picker with save.

    Reads current values from ``config`` dict and writes back to Pico
    via the ``send_command`` callback.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        config: dict[str, Any],
        send_command: Callable[[str], str | None],
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._config = config
        self._send = send_command

        # --- Section: PIN ---
        self._build_pin_section()

        # --- Section: Schedule ---
        self._build_schedule_section()

    def _build_pin_section(self) -> None:
        pin_frame = ctk.CTkFrame(self)
        pin_frame.pack(fill="x", pady=(0, 10))

        pin_row = ctk.CTkFrame(pin_frame, fg_color="transparent")
        pin_row.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            pin_row,
            text=t("settings.basic.pin_status"),
            font=ctk.CTkFont(size=14),
        ).pack(side="left")

        has_pin = self._config.get("pin_set", False)
        status_text = (
            t("settings.basic.pin_registered")
            if has_pin
            else t("settings.basic.pin_not_set")
        )
        status_color = "green" if has_pin else "orange"

        self._pin_status = ctk.CTkLabel(
            pin_row,
            text=status_text,
            font=ctk.CTkFont(size=14),
            text_color=status_color,
        )
        self._pin_status.pack(side="left", padx=10)

        self._change_pin_btn = ctk.CTkButton(
            pin_row,
            text=t("settings.basic.btn_change_pin"),
            width=120,
            command=self._on_change_pin,
        )
        self._change_pin_btn.pack(side="right")

    def _build_schedule_section(self) -> None:
        sched_frame = ctk.CTkFrame(self)
        sched_frame.pack(fill="x", pady=5)

        title = ctk.CTkLabel(
            sched_frame,
            text=t("settings.basic.schedule_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        title.pack(anchor="w", padx=15, pady=(10, 5))

        # Time picker row
        time_row = ctk.CTkFrame(sched_frame, fg_color="transparent")
        time_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(
            time_row,
            text=t("settings.basic.time_label"),
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        schedule = self._config.get("schedule", {})
        sched_time = schedule.get("time", "07:45")
        parts = sched_time.split(":")
        hour_val = parts[0] if len(parts) >= 2 else "07"
        minute_val = parts[1] if len(parts) >= 2 else "45"

        self._hour_var = ctk.StringVar(value=hour_val)
        ctk.CTkOptionMenu(
            time_row,
            values=[f"{h:02d}" for h in range(24)],
            variable=self._hour_var,
            width=70,
        ).pack(side="left", padx=(10, 2))

        ctk.CTkLabel(
            time_row, text=":", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=2)

        self._minute_var = ctk.StringVar(value=minute_val)
        ctk.CTkOptionMenu(
            time_row,
            values=[f"{m:02d}" for m in range(0, 60, 5)],
            variable=self._minute_var,
            width=70,
        ).pack(side="left", padx=(2, 10))

        # Day checkboxes
        days_row = ctk.CTkFrame(sched_frame, fg_color="transparent")
        days_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(
            days_row,
            text=t("settings.basic.days_label"),
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        active_days = schedule.get("days", ["mon", "tue", "wed", "thu", "fri"])
        self._day_vars: dict[str, ctk.BooleanVar] = {}

        cb_frame = ctk.CTkFrame(days_row, fg_color="transparent")
        cb_frame.pack(side="left", padx=10)

        for day_key in DAY_KEYS:
            var = ctk.BooleanVar(value=day_key in active_days)
            self._day_vars[day_key] = var
            ctk.CTkCheckBox(
                cb_frame,
                text=t(f"settings.basic.day_{day_key}"),
                variable=var,
                width=50,
                font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=4)

        # Save button
        btn_row = ctk.CTkFrame(sched_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(5, 10))

        self._save_btn = ctk.CTkButton(
            btn_row,
            text=t("settings.btn_save"),
            width=100,
            command=self._on_save_schedule,
        )
        self._save_btn.pack(side="right")

        self._save_status = ctk.CTkLabel(
            btn_row,
            text="",
            font=ctk.CTkFont(size=12),
        )
        self._save_status.pack(side="right", padx=10)

    def _on_change_pin(self) -> None:
        """Open a PIN change dialog."""
        dialog = _PinChangeDialog(self, self._send)
        dialog.grab_set()
        self.wait_window(dialog)

        if dialog.success:
            self._pin_status.configure(
                text=t("settings.basic.pin_registered"), text_color="green"
            )

    def _on_save_schedule(self) -> None:
        """Save schedule to Pico."""
        self._save_btn.configure(state="disabled")
        self._save_status.configure(text=t("settings.btn_saving"), text_color="gray50")

        schedule = {
            "time": f"{self._hour_var.get()}:{self._minute_var.get()}",
            "days": [k for k, v in self._day_vars.items() if v.get()],
        }

        def _save() -> None:
            try:
                payload = json.dumps({"schedule": schedule})
                resp = self._send(f"SET_CONFIG:{payload}")
                if resp and resp.startswith("OK"):
                    self.after(
                        0,
                        self._save_status.configure,
                        {"text": t("settings.btn_saved"), "text_color": "green"},
                    )
                else:
                    self.after(
                        0,
                        self._save_status.configure,
                        {
                            "text": t("settings.save_failed", error=resp or "no response"),
                            "text_color": "red",
                        },
                    )
            except Exception as e:
                self.after(
                    0,
                    self._save_status.configure,
                    {"text": t("settings.save_failed", error=str(e)), "text_color": "red"},
                )
            finally:
                self.after(0, self._save_btn.configure, {"state": "normal"})

        threading.Thread(target=_save, daemon=True).start()

    def get_schedule(self) -> dict:
        """Return current schedule values from the UI."""
        return {
            "time": f"{self._hour_var.get()}:{self._minute_var.get()}",
            "days": [k for k, v in self._day_vars.items() if v.get()],
        }


class _PinChangeDialog(ctk.CTkToplevel):
    """Modal dialog for changing the PIN."""

    def __init__(self, parent: ctk.CTkFrame, send_command: Callable[[str], str | None]) -> None:
        super().__init__(parent)
        self.title(t("settings.basic.change_pin_title"))
        self.geometry("350x280")
        self.resizable(False, False)
        self._send = send_command
        self.success = False

        # New PIN
        ctk.CTkLabel(
            self, text=t("settings.basic.new_pin_label"), font=ctk.CTkFont(size=13)
        ).pack(padx=20, pady=(20, 5), anchor="w")

        self._pin_entry = ctk.CTkEntry(self, show="*", width=250)
        self._pin_entry.pack(padx=20, pady=(0, 10))

        # Confirm
        ctk.CTkLabel(
            self, text=t("settings.basic.new_pin_confirm_label"), font=ctk.CTkFont(size=13)
        ).pack(padx=20, pady=(0, 5), anchor="w")

        self._confirm_entry = ctk.CTkEntry(self, show="*", width=250)
        self._confirm_entry.pack(padx=20, pady=(0, 10))

        # Error
        self._error_label = ctk.CTkLabel(self, text="", text_color="red", font=ctk.CTkFont(size=12))
        self._error_label.pack(padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(
            btn_frame, text=t("common.cancel"), width=80,
            fg_color="transparent", border_width=1,
            text_color=("gray30", "gray70"), border_color=("gray30", "gray70"),
            command=self.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text=t("common.ok"), width=80, command=self._on_ok
        ).pack(side="right")

        self._pin_entry.focus_set()

    def _on_ok(self) -> None:
        pin = self._pin_entry.get()
        confirm = self._confirm_entry.get()

        error_key = validate_pin(pin, confirm)
        if error_key:
            self._error_label.configure(text=t(error_key))
            return

        try:
            resp = self._send(f"SETUP_PIN:{pin}")
            if resp and resp.startswith("OK"):
                self.success = True
                self.destroy()
            else:
                self._error_label.configure(
                    text=t("settings.basic.pin_change_failed", error=resp or "no response")
                )
        except Exception as e:
            self._error_label.configure(
                text=t("settings.basic.pin_change_failed", error=str(e))
            )
