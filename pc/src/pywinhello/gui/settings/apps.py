"""Automation targets: lock screen toggle + per-app Windows Hello whitelist."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

import customtkinter as ctk

from pywinhello.gui.i18n import t

logger = logging.getLogger(__name__)


class AppsSettings(ctk.CTkFrame):
    """Lock screen toggle and per-app Windows Hello whitelist toggles.

    The ``config`` dict is expected to contain::

        {
            "lock_screen_enabled": True,
            "apps": {
                "MarketSpeed2.exe": True,
                "Chrome.exe": False,
            }
        }
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

        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", pady=5)

        # Section title
        ctk.CTkLabel(
            frame,
            text=t("settings.apps.title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Lock screen toggle
        lock_row = ctk.CTkFrame(frame, fg_color="transparent")
        lock_row.pack(fill="x", padx=15, pady=5)

        lock_label_frame = ctk.CTkFrame(lock_row, fg_color="transparent")
        lock_label_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            lock_label_frame,
            text=t("settings.apps.lock_screen"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            lock_label_frame,
            text=t("settings.apps.lock_screen_desc"),
            font=ctk.CTkFont(size=11),
            text_color="gray50",
            anchor="w",
        ).pack(anchor="w")

        self._lock_var = ctk.BooleanVar(
            value=self._config.get("lock_screen_enabled", True)
        )
        self._lock_switch = ctk.CTkSwitch(
            lock_row,
            text="",
            variable=self._lock_var,
            command=self._on_toggle_changed,
            width=48,
        )
        self._lock_switch.pack(side="right", padx=5)

        # Separator
        ctk.CTkFrame(frame, height=1, fg_color="gray60").pack(
            fill="x", padx=15, pady=8
        )

        # Windows Hello dialog section
        hello_label_frame = ctk.CTkFrame(frame, fg_color="transparent")
        hello_label_frame.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkLabel(
            hello_label_frame,
            text=t("settings.apps.hello_dialog"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            hello_label_frame,
            text=t("settings.apps.hello_dialog_desc"),
            font=ctk.CTkFont(size=11),
            text_color="gray50",
            anchor="w",
        ).pack(anchor="w")

        # Per-app toggles
        self._apps_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._apps_frame.pack(fill="x", padx=15, pady=5)

        self._app_vars: dict[str, ctk.BooleanVar] = {}
        apps = self._config.get("apps", {})

        if not apps:
            ctk.CTkLabel(
                self._apps_frame,
                text=t("settings.apps.no_apps"),
                font=ctk.CTkFont(size=12),
                text_color="gray50",
            ).pack(anchor="w", padx=10, pady=5)
        else:
            for app_name, enabled in apps.items():
                self._add_app_row(app_name, enabled)

        # Note
        ctk.CTkLabel(
            frame,
            text=t("settings.apps.app_auto_note"),
            font=ctk.CTkFont(size=11),
            text_color="gray50",
            anchor="w",
        ).pack(anchor="w", padx=15, pady=(5, 10))

        # Save status
        self._save_status = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=11)
        )
        self._save_status.pack(anchor="e", padx=15, pady=(0, 10))

    def _add_app_row(self, app_name: str, enabled: bool) -> None:
        """Add a single app toggle row."""
        row = ctk.CTkFrame(self._apps_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(
            row,
            text=app_name,
            font=ctk.CTkFont(size=12),
            anchor="w",
        ).pack(side="left", padx=10)

        var = ctk.BooleanVar(value=enabled)
        self._app_vars[app_name] = var

        ctk.CTkSwitch(
            row,
            text="",
            variable=var,
            command=self._on_toggle_changed,
            width=48,
        ).pack(side="right", padx=5)

    def _on_toggle_changed(self) -> None:
        """Save all toggle states to Pico."""
        data = {
            "lock_screen_enabled": self._lock_var.get(),
            "apps": {name: var.get() for name, var in self._app_vars.items()},
        }

        def _save() -> None:
            try:
                payload = json.dumps(data)
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
                        {"text": t("settings.save_failed", error=""), "text_color": "red"},
                    )
            except Exception:
                pass

            # Clear status after 2s
            self.after(2000, self._save_status.configure, {"text": ""})

        threading.Thread(target=_save, daemon=True).start()

    def get_app_settings(self) -> dict:
        """Return current toggle values."""
        return {
            "lock_screen_enabled": self._lock_var.get(),
            "apps": {name: var.get() for name, var in self._app_vars.items()},
        }
