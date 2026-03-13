"""Step 1/4: Device detection and firmware flashing.

Uses the setup.provision() module for all detection and flashing logic.
The wizard simply displays progress and results.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from pywinhello.gui.i18n import t
from pywinhello.gui.wizard.base import WizardStep
from pywinhello.setup import ProvisionResult, provision
from pywinhello.setup.detect import DeviceState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DeviceStep(WizardStep):
    """Step 1: detect Pico (BOOTSEL or COM port), flash firmware if needed."""

    @property
    def title(self) -> str:
        return t("wizard.step1.title")

    def build(self) -> None:
        # Description
        self._desc_label = ctk.CTkLabel(
            self.frame,
            text=t("wizard.step1.desc"),
            font=ctk.CTkFont(size=13),
            text_color="gray50",
        )
        self._desc_label.pack(pady=(0, 15))

        # Status icon area
        self._icon_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(size=48),
        )
        self._icon_label.pack(pady=10)

        # Main status
        self._status_label = ctk.CTkLabel(
            self.frame,
            text=t("wizard.step1.detecting"),
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._status_label.pack(pady=(5, 5))

        # Detail info
        self._detail_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="gray50",
            justify="left",
        )
        self._detail_label.pack(pady=(0, 10))

        # Device info frame (hidden until detected)
        self._info_frame = ctk.CTkFrame(self.frame)
        self._device_type_label = ctk.CTkLabel(
            self._info_frame, text="", font=ctk.CTkFont(size=13)
        )
        self._device_type_label.pack(pady=2)
        self._fw_label = ctk.CTkLabel(
            self._info_frame, text="", font=ctk.CTkFont(size=13)
        )
        self._fw_label.pack(pady=2)

        # Action buttons
        self._btn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self._btn_frame.pack(pady=15)

        self._flash_btn = ctk.CTkButton(
            self._btn_frame,
            text=t("wizard.step1.btn_flash"),
            command=self._on_provision,
        )

        self._detect_btn = ctk.CTkButton(
            self._btn_frame,
            text=t("wizard.step1.btn_detect"),
            command=self._on_detect,
        )

        # Instructions (for BOOTSEL re-flash)
        self._instructions_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray50",
            justify="left",
        )
        self._instructions_label.pack(pady=(5, 0))

        # Internal state
        self._detected = False
        self._device_type: str | None = None
        self._fw_version: str | None = None
        self._port: str | None = None

    def on_enter(self) -> None:
        self._on_detect()

    def _reset_ui(self) -> None:
        """Reset all UI elements to detecting state."""
        self._status_label.configure(text=t("wizard.step1.detecting"))
        self._detail_label.configure(text="")
        self._info_frame.pack_forget()
        self._flash_btn.pack_forget()
        self._detect_btn.pack_forget()
        self._instructions_label.configure(text="")
        self._icon_label.configure(text="")
        self.wizard.nav_bar.set_next_enabled(False)

    def _on_detect(self) -> None:
        """Run provision() in a background thread."""
        self._reset_ui()
        threading.Thread(target=self._provision_thread, daemon=True).start()

    def _on_provision(self) -> None:
        """Same as detect — provision handles everything."""
        self._on_detect()

    def _update_progress(self, message: str, progress: float) -> None:
        """Progress callback from provision() — runs on background thread."""
        self.frame.after(0, self._status_label.configure, {"text": message})

    def _provision_thread(self) -> None:
        """Run provision() and dispatch result to GUI."""
        try:
            result = provision(on_progress=self._update_progress)
            self.frame.after(0, self._show_result, result)
        except Exception as e:
            logger.exception("Provision failed")
            self.frame.after(
                0,
                self._show_error,
                str(e),
            )

    def _show_result(self, result: ProvisionResult) -> None:
        """Display provision result in the wizard."""
        if result.success:
            self._show_success(result)
        elif result.state == DeviceState.NOT_FOUND:
            self._show_not_found()
        elif result.state in (
            DeviceState.UNKNOWN_FIRMWARE,
            DeviceState.RUNNING_PYWINHELLO,
        ):
            self._show_needs_bootsel(result)
        else:
            self._show_error(result.message)

    def _show_success(self, result: ProvisionResult) -> None:
        """Pico is set up and ready."""
        self._detected = True
        self._device_type = result.board.value if result.board else "Pico"
        self._fw_version = result.firmware_version or "unknown"
        self._port = None  # Will be re-detected by later steps

        self._icon_label.configure(text="OK")
        self._status_label.configure(text=t("wizard.step1.com_found"))
        self._detail_label.configure(text=t("wizard.step1.already_flashed"))

        self._device_type_label.configure(
            text=t("wizard.step1.device_type", type=self._device_type)
        )
        self._fw_label.configure(
            text=t("wizard.step1.firmware_version", version=self._fw_version)
        )
        self._info_frame.pack(pady=10)

        self._flash_btn.pack_forget()
        self._detect_btn.pack_forget()
        self._instructions_label.configure(text="")

        self.wizard.nav_bar.set_next_enabled(True)

    def _show_not_found(self) -> None:
        """No Pico detected at all."""
        self._detected = False
        self._icon_label.configure(text="?")
        self._status_label.configure(text=t("wizard.step1.not_found"))
        self._detail_label.configure(text=t("wizard.step1.not_found_hint"))
        self._instructions_label.configure(text="")
        self._detect_btn.pack(side="left", padx=5)
        self.wizard.nav_bar.set_next_enabled(False)

    def _show_needs_bootsel(self, result: ProvisionResult) -> None:
        """Automatic update failed — show BOOTSEL re-flash instructions."""
        self._detected = False
        self._icon_label.configure(text="!")
        self._status_label.configure(text=t("wizard.step1.needs_bootsel"))
        self._detail_label.configure(text=result.message)
        self._instructions_label.configure(
            text=t("wizard.step1.needs_bootsel_steps")
        )
        self._detect_btn.pack(side="left", padx=5)
        self.wizard.nav_bar.set_next_enabled(False)

    def _show_error(self, message: str) -> None:
        """Generic error display."""
        self._detected = False
        self._icon_label.configure(text="!")
        self._status_label.configure(text=t("wizard.step1.flash_failed"))
        self._detail_label.configure(text=message)
        self._detect_btn.pack(side="left", padx=5)
        self.wizard.nav_bar.set_next_enabled(False)

    def can_proceed(self) -> bool:
        return self._detected

    def get_data(self) -> dict:
        return {
            "port": self._port,
            "device_type": self._device_type,
            "firmware_version": self._fw_version,
        }
