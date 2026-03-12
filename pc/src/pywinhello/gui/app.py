"""CustomTkinter main app window for pywinhello settings.

Routes based on Pico state:
- No Pico detected -> connection screen
- Pico without PIN -> setup wizard
- Pico with PIN -> settings panel

Polls for Pico every 2 seconds. Language toggle (ja/en).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import customtkinter as ctk

from pywinhello.gui.i18n import detect_default_locale, get_locale, set_locale, t

logger = logging.getLogger(__name__)

_WINDOW_WIDTH = 600
_WINDOW_HEIGHT = 700
_POLL_INTERVAL_MS = 2000


class _PicoConnection:
    """Manages serial connection to Pico. Thread-safe."""

    def __init__(self) -> None:
        self._hid = None
        self._lock = threading.Lock()
        self._port: str | None = None

    @property
    def port(self) -> str | None:
        return self._port

    def detect(self) -> bool:
        """Try to find and connect to a Pico. Returns True if connected."""
        with self._lock:
            if self._hid is not None:
                try:
                    if self._hid.ping():
                        return True
                except Exception:
                    self._close_locked()

            try:
                from pywinhello.hid import HIDKeyboard, find_pico_port

                port = find_pico_port()
                if port is None:
                    return False
                self._hid = HIDKeyboard(port=port)
                if self._hid.ping():
                    self._port = port
                    return True
                else:
                    self._close_locked()
                    return False
            except Exception:
                self._close_locked()
                return False

    def send_command(self, command: str) -> str | None:
        """Send a command to the Pico. Returns response or None."""
        with self._lock:
            if self._hid is None:
                return None
            try:
                return self._hid._send(command)
            except Exception as e:
                logger.debug("Command failed: %s", e)
                return None

    def get_config(self) -> dict[str, Any]:
        """Send GET_CONFIG and parse response JSON."""
        resp = self.send_command("GET_CONFIG")
        if resp and resp.startswith("OK:"):
            try:
                return json.loads(resp[3:])
            except (json.JSONDecodeError, ValueError):
                pass
        return {}

    def get_status(self) -> dict[str, Any]:
        """Send STATUS and parse response."""
        resp = self.send_command("STATUS")
        if resp:
            info: dict[str, Any] = {}
            clean = resp.replace("OK:", "")
            for part in clean.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    info[k.strip()] = v.strip()
            return info
        return {}

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self._hid is not None:
            try:
                self._hid.close()
            except Exception:
                pass
            self._hid = None
            self._port = None


class App(ctk.CTk):
    """Main application window.

    State machine:
    - ``disconnected``: No Pico found, show connection screen
    - ``wizard``: Pico found but no PIN, show setup wizard
    - ``settings``: Pico found with PIN, show settings panel
    """

    def __init__(self) -> None:
        super().__init__()

        # Detect locale
        locale = detect_default_locale()
        set_locale(locale)

        # Window setup
        self.title(t("app.title"))
        self.geometry(f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}")
        self.minsize(_WINDOW_WIDTH, 500)
        ctk.set_appearance_mode("system")

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - _WINDOW_WIDTH) // 2
        y = (self.winfo_screenheight() - _WINDOW_HEIGHT) // 2
        self.geometry(f"+{x}+{y}")

        # Try to set icon
        try:
            from pathlib import Path

            ico = Path(__file__).parent / "assets" / "icon.ico"
            if ico.exists():
                self.iconbitmap(str(ico))
        except Exception:
            pass

        # Pico connection
        self._pico = _PicoConnection()
        self._state = "disconnected"

        # Language toggle in top-right corner
        self._top_bar = ctk.CTkFrame(self, fg_color="transparent", height=30)
        self._top_bar.pack(fill="x", padx=10, pady=(5, 0))

        self._lang_btn = ctk.CTkButton(
            self._top_bar,
            text=t("app.lang_toggle"),
            width=70,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            text_color=("gray40", "gray60"),
            border_color=("gray40", "gray60"),
            command=self._toggle_language,
        )
        self._lang_btn.pack(side="right")

        # Content container (everything below top bar)
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True)

        # Current view reference
        self._current_view: ctk.CTkFrame | None = None

        # Show disconnected screen initially
        self._show_disconnected()

        # Start polling
        self._poll_id: str | None = None
        self._start_polling()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _clear_content(self) -> None:
        """Remove the current view from the content area."""
        if self._current_view is not None:
            self._current_view.destroy()
            self._current_view = None

    # ── Views ──────────────────────────────────────────────────────────

    def _show_disconnected(self) -> None:
        """Show 'connect your Pico' screen."""
        self._state = "disconnected"
        self._clear_content()

        frame = ctk.CTkFrame(self._content, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        self._current_view = frame

        # Center content vertically
        spacer = ctk.CTkFrame(frame, fg_color="transparent")
        spacer.pack(expand=True)

        # Icon placeholder
        ctk.CTkLabel(
            frame,
            text="USB",
            font=ctk.CTkFont(size=40, weight="bold"),
            text_color="gray50",
        ).pack(pady=(0, 10))

        # Title
        self._conn_title = ctk.CTkLabel(
            frame,
            text=t("connection.title"),
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self._conn_title.pack(pady=(0, 5))

        # Message
        self._conn_msg = ctk.CTkLabel(
            frame,
            text=t("connection.message"),
            font=ctk.CTkFont(size=14),
            text_color="gray50",
        )
        self._conn_msg.pack(pady=(0, 10))

        # Hint
        self._conn_hint = ctk.CTkLabel(
            frame,
            text=t("connection.hint"),
            font=ctk.CTkFont(size=12),
            text_color="gray60",
            justify="center",
        )
        self._conn_hint.pack(pady=(0, 10))

        # Scanning indicator
        self._conn_scan = ctk.CTkLabel(
            frame,
            text=t("connection.scanning"),
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        )
        self._conn_scan.pack(pady=10)

        spacer2 = ctk.CTkFrame(frame, fg_color="transparent")
        spacer2.pack(expand=True)

    def _show_wizard(self) -> None:
        """Show the setup wizard."""
        self._state = "wizard"
        self._clear_content()

        from pywinhello.gui.wizard import SetupWizard

        wizard = SetupWizard(
            self._content,
            on_complete=self._on_wizard_complete,
            on_cancel=self._on_wizard_cancel,
        )
        # Pass port info to wizard
        wizard.collected_data["port"] = self._pico.port
        status = self._pico.get_status()
        wizard.collected_data["device_type"] = status.get("type", "Pico")
        wizard.collected_data["firmware_version"] = status.get("fw", "unknown")

        wizard.pack(fill="both", expand=True)
        self._current_view = wizard

    def _show_settings(self) -> None:
        """Show the settings panel."""
        self._state = "settings"
        self._clear_content()

        from pywinhello.gui.settings import SettingsPanel

        panel = SettingsPanel(
            self._content,
            send_command=self._pico.send_command,
            on_run_wizard=self._show_wizard,
            on_test=self._on_run_test,
        )
        panel.pack(fill="both", expand=True)
        self._current_view = panel

    # ── Callbacks ──────────────────────────────────────────────────────

    def _on_wizard_complete(self) -> None:
        """Wizard finished successfully, switch to settings."""
        self._show_settings()

    def _on_wizard_cancel(self) -> None:
        """Wizard cancelled, go back to connection/settings."""
        if self._pico.detect():
            config = self._pico.get_config()
            if config.get("pin_set", False):
                self._show_settings()
            else:
                self._show_disconnected()
        else:
            self._show_disconnected()

    def _on_run_test(self) -> None:
        """Run lock/unlock test from settings panel."""
        from pywinhello.gui.tests.lock_test import LockUnlockTest

        dialog = ctk.CTkToplevel(self)
        dialog.title(t("test.lock.title"))
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=t("test.lock.confirm_message"),
            font=ctk.CTkFont(size=13),
            justify="left",
        ).pack(padx=20, pady=20)

        status_label = ctk.CTkLabel(
            dialog, text="", font=ctk.CTkFont(size=13, weight="bold")
        )
        status_label.pack(pady=5)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)

        def _start() -> None:
            start_btn.configure(state="disabled")

            def _run() -> None:
                test = LockUnlockTest(timeout=30.0)

                def _on_status(s: str) -> None:
                    key_map = {
                        "locking": "test.lock.locking",
                        "waiting": "test.lock.waiting_unlock",
                        "unlocked": "test.lock.success",
                        "timeout": "test.lock.failed",
                    }
                    dialog.after(
                        0,
                        status_label.configure,
                        {"text": t(key_map.get(s, s))},
                    )

                result = test.run(on_status=_on_status)
                if result.passed:
                    dialog.after(
                        0,
                        status_label.configure,
                        {
                            "text": t("test.lock.success", elapsed=result.elapsed),
                            "text_color": "green",
                        },
                    )
                else:
                    dialog.after(
                        0,
                        status_label.configure,
                        {"text": t("test.lock.failed"), "text_color": "red"},
                    )

            threading.Thread(target=_run, daemon=True).start()

        start_btn = ctk.CTkButton(
            btn_frame, text=t("test.lock.btn_start"), command=_start
        )
        start_btn.pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text=t("test.lock.btn_cancel"),
            fg_color="transparent",
            border_width=1,
            text_color=("gray30", "gray70"),
            border_color=("gray30", "gray70"),
            command=dialog.destroy,
        ).pack(side="right")

    # ── Language ───────────────────────────────────────────────────────

    def _toggle_language(self) -> None:
        """Switch between ja and en."""
        current = get_locale()
        new_locale = "en" if current == "ja" else "ja"
        set_locale(new_locale)

        # Save locale to Pico
        try:
            self._pico.send_command(f'SET_CONFIG:{{"locale":"{new_locale}"}}')
        except Exception:
            pass

        # Refresh UI
        self._lang_btn.configure(text=t("app.lang_toggle"))
        self.title(t("app.title"))

        # Rebuild current view
        if self._state == "disconnected":
            self._show_disconnected()
        elif self._state == "wizard":
            # Refresh wizard i18n if possible
            if self._current_view and hasattr(self._current_view, "refresh_i18n"):
                self._current_view.refresh_i18n()
        elif self._state == "settings":
            self._show_settings()

    # ── Polling ────────────────────────────────────────────────────────

    def _start_polling(self) -> None:
        """Poll for Pico connection every 2 seconds."""
        self._do_poll()

    def _do_poll(self) -> None:
        """Single poll iteration, scheduled on the main thread."""

        def _check() -> None:
            connected = self._pico.detect()
            if connected:
                config = self._pico.get_config()
                has_pin = config.get("pin_set", False)
                self.after(0, self._on_poll_result, True, has_pin)
            else:
                self.after(0, self._on_poll_result, False, False)

        threading.Thread(target=_check, daemon=True).start()
        self._poll_id = self.after(_POLL_INTERVAL_MS, self._do_poll)

    def _on_poll_result(self, connected: bool, has_pin: bool) -> None:
        """Handle poll result on the main thread."""
        if not connected:
            if self._state != "disconnected":
                self._show_disconnected()
        elif not has_pin:
            if self._state == "disconnected":
                self._show_wizard()
        else:
            if self._state == "disconnected":
                self._show_settings()
            elif self._state == "settings" and self._current_view:
                # Update connection status
                if hasattr(self._current_view, "update_connection_status"):
                    self._current_view.update_connection_status(True)

    # ── Cleanup ────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        """Clean up on window close."""
        if self._poll_id:
            self.after_cancel(self._poll_id)
        self._pico.close()
        self.destroy()


def main() -> None:
    """Entry point for pywinhello-settings GUI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s %(levelname)s %(message)s",
    )
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
