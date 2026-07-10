"""Settings panel shown after initial setup is complete.

Reads all configuration from Pico via GET_CONFIG, provides UI for
modifying and saving back via SET_CONFIG.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from pywinhello.core import read_config
from pywinhello.gui.i18n import t
from pywinhello.gui.settings.advanced import AdvancedSettings
from pywinhello.gui.settings.apps import AppsSettings
from pywinhello.gui.settings.basic import BasicSettings
from pywinhello.gui.settings.log_view import LogView
from pywinhello.gui.settings.version_info import VersionInfo

if TYPE_CHECKING:
    from pywinhello.gui.app import _PicoConnection

logger = logging.getLogger(__name__)


class SettingsPanel(ctk.CTkFrame):
    """Full settings panel with all sections in a scrollable frame.

    Reads Pico config on init, builds sections, writes changes back.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        pico: _PicoConnection,
        on_run_wizard: Callable[[], None] | None = None,
        on_test: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._pico = pico
        self._on_run_wizard = on_run_wizard
        self._on_test = on_test
        self._config: dict[str, Any] = {}
        self._sections_built = False

        # Connection status bar
        self._status_frame = ctk.CTkFrame(self)
        self._status_frame.pack(fill="x", padx=15, pady=(10, 5))

        self._status_label = ctk.CTkLabel(
            self._status_frame,
            text=t("common.loading"),
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        self._status_label.pack(padx=15, pady=8)

        # Scrollable content
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # Bottom actions bar
        self._actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._actions_frame.pack(fill="x", padx=15, pady=(5, 10))

        # Load config and build
        self._load_config()

    def _load_config(self) -> None:
        """Fetch config from Pico in background."""

        def _fetch() -> None:
            try:
                config = read_config(self._pico.protocol)
            except Exception as e:
                logger.debug("Failed to load config: %s", e)
                config = {}

            self.after(0, self._build_sections, config)

        threading.Thread(target=_fetch, daemon=True).start()

    def _build_sections(self, config: dict[str, Any]) -> None:
        """Build all settings sections with loaded config."""
        self._config = config

        if self._sections_built:
            # Rebuild: clear existing
            for child in self._scroll.winfo_children():
                child.destroy()
            for child in self._actions_frame.winfo_children():
                child.destroy()

        # Connection status
        device = config.get("device_type", "Pico")
        if config:
            self._status_label.configure(
                text=t("settings.status_connected", device=device),
                text_color="green",
            )
        else:
            self._status_label.configure(
                text=t("settings.status_disconnected"),
                text_color="orange",
            )

        # Basic settings (PIN + schedule)
        self._basic = BasicSettings(self._scroll, config, self._pico)
        self._basic.pack(fill="x", pady=5)

        # Automation targets (apps)
        self._apps = AppsSettings(self._scroll, config, self._pico)
        self._apps.pack(fill="x", pady=5)

        # Advanced settings (timing)
        self._advanced = AdvancedSettings(self._scroll, config, self._pico)
        self._advanced.pack(fill="x", pady=5)

        # Recent events log
        self._log = LogView(self._scroll, self._pico)
        self._log.pack(fill="x", pady=5)

        # Version info
        self._version = VersionInfo(self._scroll, config, self._pico)
        self._version.pack(fill="x", pady=5)

        # Bottom action buttons
        self._build_actions()
        self._sections_built = True

    def _build_actions(self) -> None:
        """Build the bottom action button bar."""
        # Test button
        test_btn = ctk.CTkButton(
            self._actions_frame,
            text=t("settings.actions.btn_test"),
            width=100,
            command=self._on_test_click,
        )
        test_btn.pack(side="left", padx=5)

        # Wizard button
        wizard_btn = ctk.CTkButton(
            self._actions_frame,
            text=t("settings.actions.btn_wizard"),
            width=160,
            fg_color="transparent",
            border_width=1,
            text_color=("gray30", "gray70"),
            border_color=("gray30", "gray70"),
            command=self._on_wizard_click,
        )
        wizard_btn.pack(side="left", padx=5)

        # Clear/reset button (right side, destructive)
        clear_btn = ctk.CTkButton(
            self._actions_frame,
            text=t("settings.actions.btn_clear"),
            width=120,
            fg_color="red",
            hover_color="darkred",
            command=self._on_clear,
        )
        clear_btn.pack(side="right", padx=5)

        # Status label for actions
        self._action_status = ctk.CTkLabel(
            self._actions_frame, text="", font=ctk.CTkFont(size=12)
        )
        self._action_status.pack(side="right", padx=10)

    def _on_test_click(self) -> None:
        if self._on_test:
            self._on_test()

    def _on_wizard_click(self) -> None:
        if self._on_run_wizard:
            self._on_run_wizard()

    def _on_clear(self) -> None:
        """Confirm and clear all Pico data."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(t("common.warning"))
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=t("settings.actions.clear_confirm"),
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
            self._do_clear()

        ctk.CTkButton(
            btn_frame,
            text=t("common.yes"),
            width=80,
            fg_color="red",
            hover_color="darkred",
            command=_confirm,
        ).pack(side="right")

    def _do_clear(self) -> None:
        """Send CLEAR command to Pico."""

        def _clear() -> None:
            try:
                self._pico.protocol.clear()
                self.after(
                    0,
                    self._action_status.configure,
                    {"text": t("settings.actions.clear_success"), "text_color": "green"},
                )
                # Trigger wizard mode
                if self._on_run_wizard:
                    self.after(1000, self._on_run_wizard)
            except Exception as e:
                self.after(
                    0,
                    self._action_status.configure,
                    {"text": t("settings.actions.clear_failed", error=str(e)), "text_color": "red"},
                )

        threading.Thread(target=_clear, daemon=True).start()

    def update_connection_status(self, connected: bool, device: str = "Pico") -> None:
        """Update the connection status bar."""
        if connected:
            self._status_label.configure(
                text=t("settings.status_connected", device=device),
                text_color="green",
            )
        else:
            self._status_label.configure(
                text=t("settings.status_disconnected"),
                text_color="orange",
            )

    def refresh_config(self) -> None:
        """Reload config from Pico and rebuild sections."""
        self._load_config()


__all__ = ["SettingsPanel"]
