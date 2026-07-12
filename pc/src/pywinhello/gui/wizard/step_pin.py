"""Step 3/4: PIN registration with confirmation and security notice."""

from __future__ import annotations

import logging
import threading

import customtkinter as ctk

from pywinhello.core import register_pin
from pywinhello.gui.constants import validate_pin
from pywinhello.gui.i18n import t
from pywinhello.gui.wizard.base import WizardStep

logger = logging.getLogger(__name__)


class PinStep(WizardStep):
    """Step 3: Enter and confirm Windows Hello PIN, send SETUP_PIN to Pico."""

    @property
    def title(self) -> str:
        return t("wizard.step3.title")

    def build(self) -> None:
        # Description
        self._desc = ctk.CTkLabel(
            self.frame,
            text=t("wizard.step3.desc"),
            font=ctk.CTkFont(size=13),
            text_color="gray50",
        )
        self._desc.pack(pady=(0, 15))

        # PIN entry form
        form = ctk.CTkFrame(self.frame)
        form.pack(fill="x", padx=40, pady=10)

        # PIN field
        pin_label = ctk.CTkLabel(
            form,
            text=t("wizard.step3.pin_label"),
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        pin_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self._pin_entry = ctk.CTkEntry(
            form,
            placeholder_text=t("wizard.step3.pin_placeholder"),
            show="*",
            width=250,
            font=ctk.CTkFont(size=14),
        )
        self._pin_entry.grid(row=0, column=1, padx=10, pady=(10, 5))

        # Confirm field
        confirm_label = ctk.CTkLabel(
            form,
            text=t("wizard.step3.pin_confirm_label"),
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        confirm_label.grid(row=1, column=0, sticky="w", padx=10, pady=5)

        self._confirm_entry = ctk.CTkEntry(
            form,
            placeholder_text=t("wizard.step3.pin_confirm_placeholder"),
            show="*",
            width=250,
            font=ctk.CTkFont(size=14),
        )
        self._confirm_entry.grid(row=1, column=1, padx=10, pady=5)

        form.columnconfigure(1, weight=1)

        # Error label
        self._error_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="red",
        )
        self._error_label.pack(pady=(5, 0))

        # Security notice
        notice_frame = ctk.CTkFrame(self.frame, fg_color=("gray90", "gray20"))
        notice_frame.pack(fill="x", padx=40, pady=15)

        self._security_label = ctk.CTkLabel(
            notice_frame,
            text=t("wizard.step3.security_notice"),
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60"),
            justify="left",
        )
        self._security_label.pack(padx=15, pady=10)

        # Register button
        self._register_btn = ctk.CTkButton(
            self.frame,
            text=t("wizard.step3.btn_register"),
            command=self._on_register,
            width=150,
        )
        self._register_btn.pack(pady=10)

        # Status
        self._status_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._status_label.pack(pady=5)

        # State
        self._registered = False

    def on_enter(self) -> None:
        self._pin_entry.focus_set()
        self.wizard.nav_bar.set_next_enabled(self._registered)

    def _validate(self) -> str | None:
        """Validate PIN fields. Returns error message or None."""
        pin = self._pin_entry.get()
        confirm = self._confirm_entry.get()
        error_key = validate_pin(pin, confirm)
        return t(error_key) if error_key else None

    def _on_register(self) -> None:
        """Validate and send PIN to Pico."""
        error = self._validate()
        if error:
            self._error_label.configure(text=error)
            return

        self._error_label.configure(text="")
        self._register_btn.configure(state="disabled")
        self._status_label.configure(
            text=t("wizard.step3.pin_sending"), text_color="gray50"
        )

        pin = self._pin_entry.get()
        threading.Thread(target=self._send_pin, args=(pin,), daemon=True).start()

    def _send_pin(self, pin: str) -> None:
        """Send SETUP_PIN command to Pico in background thread."""
        try:
            from pywinhello.serial.protocol import SerialProtocol

            port = self.wizard.collected_data.get("port")
            if port is None:
                self.frame.after(0, self._on_pin_failed, "No port available")
                return

            with SerialProtocol(port=port) as proto:
                try:
                    register_pin(proto, pin)
                    self.frame.after(0, self._on_pin_success)
                except RuntimeError as e:
                    self.frame.after(
                        0,
                        self._on_pin_failed,
                        str(e),
                    )

        except Exception as e:
            logger.exception("PIN registration failed")
            self.frame.after(0, self._on_pin_failed, str(e))

    def _on_pin_success(self) -> None:
        self._registered = True
        self._status_label.configure(
            text=t("wizard.step3.pin_success"), text_color="green"
        )
        self._register_btn.configure(state="normal")
        self.wizard.nav_bar.set_next_enabled(True)

    def _on_pin_failed(self, error: str) -> None:
        self._registered = False
        self._status_label.configure(
            text=t("wizard.step3.pin_failed", error=error), text_color="red"
        )
        self._register_btn.configure(state="normal")
        self.wizard.nav_bar.set_next_enabled(False)

    def can_proceed(self) -> bool:
        return self._registered

    def get_data(self) -> dict:
        return {"pin_registered": self._registered}
