"""Recent events display from Pico log (last 20 entries)."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

import customtkinter as ctk

from pywinhello.gui.i18n import t

logger = logging.getLogger(__name__)

# Event type to i18n key mapping
_EVENT_TYPES = {
    "boot_unlock": "settings.log.event_boot_unlock",
    "wake_unlock": "settings.log.event_wake_unlock",
    "hello": "settings.log.event_hello",
}


def _format_event(event: dict[str, Any]) -> str:
    """Format a single log event for display.

    Expected event format::

        {
            "type": "wake_unlock",
            "success": True,
            "elapsed": 2.3,
            "timestamp": "03/12 07:45"
        }
    """
    event_type = event.get("type", "unknown")
    success = event.get("success", False)
    elapsed = event.get("elapsed", 0.0)
    timestamp = event.get("timestamp", "")

    result_key = "settings.log.result_success" if success else "settings.log.result_failed"
    result_str = t(result_key)

    i18n_key = _EVENT_TYPES.get(event_type, "settings.log.event_unknown")
    if event_type in _EVENT_TYPES:
        message = t(i18n_key, result=result_str)
    else:
        message = t(i18n_key, type=event_type)

    elapsed_str = t("settings.log.elapsed", seconds=elapsed) if elapsed else ""

    parts = []
    if timestamp:
        parts.append(timestamp)
    parts.append(message)
    if elapsed_str:
        parts.append(elapsed_str)

    return " ".join(parts)


class LogView(ctk.CTkFrame):
    """Display the last 20 events from the Pico log."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        send_command: Callable[[str], str | None],
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._send = send_command

        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", pady=5)

        # Header row
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(
            header,
            text=t("settings.log.title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(side="left")

        self._refresh_btn = ctk.CTkButton(
            header,
            text=t("settings.log.btn_refresh"),
            width=80,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._on_refresh,
        )
        self._refresh_btn.pack(side="right")

        # Log text area
        self._log_text = ctk.CTkTextbox(
            frame,
            height=180,
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled",
            activate_scrollbars=True,
        )
        self._log_text.pack(fill="x", padx=15, pady=(0, 10))

        # Initial load
        self._on_refresh()

    def _on_refresh(self) -> None:
        """Fetch and display log entries from Pico."""
        self._refresh_btn.configure(state="disabled")

        def _fetch() -> None:
            entries: list[str] = []
            try:
                resp = self._send("GET_LOG")
                if resp and resp.startswith("OK:"):
                    data = json.loads(resp[3:])
                    if isinstance(data, list):
                        for event in data[-20:]:
                            entries.append(_format_event(event))
            except Exception as e:
                logger.debug("Failed to fetch log: %s", e)

            self.after(0, self._display_entries, entries)

        threading.Thread(target=_fetch, daemon=True).start()

    def _display_entries(self, entries: list[str]) -> None:
        """Update the log textbox with entries."""
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")

        if entries:
            # Show newest first
            for entry in reversed(entries):
                self._log_text.insert("end", entry + "\n")
        else:
            self._log_text.insert("end", t("settings.log.no_events"))

        self._log_text.configure(state="disabled")
        self._refresh_btn.configure(state="normal")
