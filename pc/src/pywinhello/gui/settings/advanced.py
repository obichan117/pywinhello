"""Advanced settings: timing parameters with descriptions and ranges."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from pywinhello.core import write_config
from pywinhello.gui.i18n import t

if TYPE_CHECKING:
    from pywinhello.gui.app import _PicoConnection

logger = logging.getLogger(__name__)

# (config_key, i18n_key, default, min, max, step, type)
_TIMING_PARAMS = [
    ("boot_wait", "boot_wait", 45, 30, 90, 1, int),
    ("wake_wait", "wake_wait", 5, 3, 10, 1, int),
    ("keystroke_ms", "keystroke_ms", 50, 30, 150, 10, int),
    ("retry_count", "retry_count", 3, 1, 5, 1, int),
    ("retry_interval", "retry_interval", 10, 5, 30, 1, int),
    ("dialog_wait", "dialog_wait", 1.0, 0.5, 3.0, 0.5, float),
]

_DEFAULTS = {p[0]: p[2] for p in _TIMING_PARAMS}


class AdvancedSettings(ctk.CTkFrame):
    """All timing parameters with descriptions and recommended ranges."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        config: dict[str, Any],
        pico: _PicoConnection,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._config = config
        self._pico = pico
        self._entries: dict[str, ctk.CTkEntry] = {}

        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", pady=5)

        # Section title
        ctk.CTkLabel(
            frame,
            text=t("settings.advanced.title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Parameter rows
        for cfg_key, i18n_key, default, min_val, max_val, step, typ in _TIMING_PARAMS:
            self._build_param_row(
                frame, cfg_key, i18n_key, default, min_val, max_val, typ
            )

        # Buttons row
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=10)

        self._reset_btn = ctk.CTkButton(
            btn_row,
            text=t("settings.advanced.btn_reset_defaults"),
            width=140,
            fg_color="transparent",
            border_width=1,
            text_color=("gray30", "gray70"),
            border_color=("gray30", "gray70"),
            command=self._on_reset,
        )
        self._reset_btn.pack(side="left")

        self._save_btn = ctk.CTkButton(
            btn_row,
            text=t("settings.btn_save"),
            width=100,
            command=self._on_save,
        )
        self._save_btn.pack(side="right")

        self._status_label = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=12)
        )
        self._status_label.pack(side="right", padx=10)

    def _build_param_row(
        self,
        parent: ctk.CTkFrame,
        cfg_key: str,
        i18n_key: str,
        default: int | float,
        min_val: int | float,
        max_val: int | float,
        typ: type,
    ) -> None:
        """Build a single parameter row with label, description, entry, unit."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=4)

        # Left side: name + description
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            left,
            text=t(f"settings.advanced.{i18n_key}"),
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,
            text=t(f"settings.advanced.{i18n_key}_desc"),
            font=ctk.CTkFont(size=11),
            text_color="gray50",
            anchor="w",
        ).pack(anchor="w")

        # Right side: entry + unit + range
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right")

        current = self._config.get(cfg_key, default)
        entry = ctk.CTkEntry(right, width=70, font=ctk.CTkFont(size=13))
        entry.insert(0, str(current))
        entry.pack(side="left", padx=(5, 3))
        self._entries[cfg_key] = entry

        ctk.CTkLabel(
            right,
            text=t(f"settings.advanced.{i18n_key}_unit"),
            font=ctk.CTkFont(size=12),
            text_color="gray50",
        ).pack(side="left", padx=(0, 10))

        # Range hint below entry
        range_label = ctk.CTkLabel(
            left,
            text=t(f"settings.advanced.{i18n_key}_range"),
            font=ctk.CTkFont(size=10),
            text_color="gray60",
            anchor="w",
        )
        range_label.pack(anchor="w")

    def _get_values(self) -> dict[str, int | float]:
        """Read and validate all entry values."""
        values: dict[str, int | float] = {}
        for cfg_key, i18n_key, default, min_val, max_val, step, typ in _TIMING_PARAMS:
            text = self._entries[cfg_key].get().strip()
            try:
                val = typ(text)
                val = max(min_val, min(max_val, val))
            except (ValueError, TypeError):
                val = default
            values[cfg_key] = val
        return values

    def _on_save(self) -> None:
        """Save advanced settings to Pico."""
        values = self._get_values()
        self._save_btn.configure(state="disabled")
        self._status_label.configure(text=t("settings.btn_saving"), text_color="gray50")

        def _save() -> None:
            try:
                write_config(self._pico.protocol, values)
                self.after(
                    0,
                    self._status_label.configure,
                    {"text": t("settings.btn_saved"), "text_color": "green"},
                )
            except Exception as e:
                self.after(
                    0,
                    self._status_label.configure,
                    {"text": t("settings.save_failed", error=str(e)), "text_color": "red"},
                )
            finally:
                self.after(0, self._save_btn.configure, {"state": "normal"})

        threading.Thread(target=_save, daemon=True).start()

    def _on_reset(self) -> None:
        """Reset all values to defaults with confirmation dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(t("common.warning"))
        dialog.geometry("350x150")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=t("settings.advanced.reset_confirm"),
            font=ctk.CTkFont(size=13),
            justify="left",
        ).pack(padx=20, pady=20)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkButton(
            btn_frame,
            text=t("common.cancel"),
            width=80,
            fg_color="transparent",
            border_width=1,
            text_color=("gray30", "gray70"),
            border_color=("gray30", "gray70"),
            command=dialog.destroy,
        ).pack(side="left")

        def _confirm() -> None:
            dialog.destroy()
            for cfg_key, entry in self._entries.items():
                entry.delete(0, "end")
                entry.insert(0, str(_DEFAULTS[cfg_key]))
            self._status_label.configure(
                text=t("settings.advanced.reset_success"), text_color="green"
            )
            self.after(2000, self._status_label.configure, {"text": ""})

        ctk.CTkButton(
            btn_frame,
            text=t("common.yes"),
            width=80,
            fg_color="red",
            hover_color="darkred",
            command=_confirm,
        ).pack(side="right")

    def get_values(self) -> dict[str, int | float]:
        """Return current timing values from the UI."""
        return self._get_values()
