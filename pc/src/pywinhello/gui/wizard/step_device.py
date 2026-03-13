"""Step 1/4: Device detection and firmware flashing."""

from __future__ import annotations

import logging
import shutil
import string
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from pywinhello.gui.i18n import t
from pywinhello.gui.wizard.base import WizardStep

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# BOOTSEL mode volume label
_BOOTSEL_LABEL = "RPI-RP2"


def _find_bootsel_drive() -> Path | None:
    """Find a mounted drive with the RPI-RP2 volume label (BOOTSEL mode)."""
    try:
        import ctypes as _ctypes

        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if Path(drive).exists():
                vol_buf = _ctypes.create_unicode_buffer(256)
                result = _ctypes.windll.kernel32.GetVolumeInformationW(
                    drive, vol_buf, 256, None, None, None, None, 0
                )
                if result and vol_buf.value == _BOOTSEL_LABEL:
                    return Path(drive)
    except Exception:
        pass
    return None


def _find_pico_com() -> tuple[str | None, str | None, str | None]:
    """Detect Pico on a COM port. Returns (port, device_type, firmware_version)."""
    try:
        from pywinhello.hid import find_pico_port, HIDKeyboard

        port = find_pico_port()
        if port is None:
            return None, None, None

        # Try to get device info via protocol
        try:
            with HIDKeyboard(port=port) as kb:
                if kb.ping():
                    # v2 firmware supports STATUS command
                    try:
                        resp = kb._send("STATUS")
                        # Expected: "OK:type=pico_w,fw=1.0.0" or similar
                        info: dict[str, str] = {}
                        for part in resp.replace("OK:", "").split(","):
                            if "=" in part:
                                k, v = part.split("=", 1)
                                info[k.strip()] = v.strip()
                        device_type = info.get("type", "Pico")
                        fw_version = info.get("fw", "unknown")
                        return port, device_type, fw_version
                    except Exception:
                        # v1 firmware: only PING works
                        return port, "Pico", "1.x"
        except Exception:
            return port, None, None

    except ImportError:
        pass

    return None, None, None


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
            command=self._on_flash,
        )

        self._detect_btn = ctk.CTkButton(
            self._btn_frame,
            text=t("wizard.step1.btn_detect"),
            command=self._on_detect,
        )

        # Instructions for BOOTSEL
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

    def _on_detect(self) -> None:
        """Run device detection in a background thread."""
        self._status_label.configure(text=t("wizard.step1.detecting"))
        self._detail_label.configure(text="")
        self._info_frame.pack_forget()
        self._flash_btn.pack_forget()
        self._detect_btn.pack_forget()
        self._instructions_label.configure(text="")
        self._icon_label.configure(text="")

        threading.Thread(target=self._detect_thread, daemon=True).start()

    def _detect_thread(self) -> None:
        """Background detection."""
        # Check for BOOTSEL drive
        bootsel = _find_bootsel_drive()
        if bootsel is not None:
            self.frame.after(0, self._show_bootsel, str(bootsel))
            return

        # Check for COM port
        port, dev_type, fw_ver = _find_pico_com()
        if port is not None:
            self.frame.after(0, self._show_com_found, port, dev_type, fw_ver)
            return

        # Not found
        self.frame.after(0, self._show_not_found)

    def _show_bootsel(self, drive: str) -> None:
        self._detected = False
        self._icon_label.configure(text="USB")
        self._status_label.configure(text=t("wizard.step1.bootsel_found"))
        self._detail_label.configure(text=f"Drive: {drive}")
        self._instructions_label.configure(text="")
        self._flash_btn.pack(side="left", padx=5)
        self._detect_btn.pack(side="left", padx=5)

    def _show_com_found(
        self, port: str, device_type: str | None, fw_version: str | None
    ) -> None:
        self._detected = True
        self._port = port
        self._device_type = device_type or "Pico"
        self._fw_version = fw_version or "unknown"

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

        # Enable next
        self.wizard.nav_bar.set_next_enabled(True)

    def _show_not_found(self) -> None:
        self._detected = False
        self._icon_label.configure(text="?")
        self._status_label.configure(text=t("wizard.step1.not_found"))
        self._detail_label.configure(text=t("wizard.step1.not_found_hint"))
        self._instructions_label.configure(text=t("wizard.step1.bootsel_instructions"))
        self._detect_btn.pack(side="left", padx=5)
        self.wizard.nav_bar.set_next_enabled(False)

    def _on_flash(self) -> None:
        """Flash firmware to BOOTSEL drive in background."""
        self._flash_btn.configure(state="disabled")
        self._status_label.configure(text=t("wizard.step1.flashing"))
        threading.Thread(target=self._flash_thread, daemon=True).start()

    def _flash_thread(self) -> None:
        """Copy .uf2 firmware to the BOOTSEL drive."""
        try:
            bootsel = _find_bootsel_drive()
            if bootsel is None:
                self.frame.after(
                    0, self._status_label.configure, {"text": t("wizard.step1.flash_failed")}
                )
                return

            # Look for bundled .uf2 firmware
            fw_dir = Path(__file__).parent.parent.parent / "firmware"
            uf2_files = list(fw_dir.glob("*.uf2")) if fw_dir.exists() else []

            if not uf2_files:
                # Also check package data
                import importlib.resources as resources

                try:
                    pkg_path = resources.files("pywinhello") / "firmware"
                    if pkg_path.is_dir():  # type: ignore[union-attr]
                        uf2_files = [p for p in pkg_path.iterdir() if str(p).endswith(".uf2")]  # type: ignore[union-attr]
                except Exception:
                    pass

            if not uf2_files:
                self.frame.after(
                    0,
                    self._status_label.configure,
                    {"text": t("wizard.step1.flash_failed")},
                )
                self.frame.after(
                    0,
                    self._detail_label.configure,
                    {"text": "No .uf2 firmware file found"},
                )
                return

            uf2_path = uf2_files[0]
            dest = bootsel / uf2_path.name
            shutil.copy2(str(uf2_path), str(dest))

            self.frame.after(
                0, self._status_label.configure, {"text": t("wizard.step1.waiting_reboot")}
            )

            # Wait for Pico to reboot and appear as COM port
            for _ in range(30):
                time.sleep(1)
                port, dev_type, fw_ver = _find_pico_com()
                if port is not None:
                    self.frame.after(
                        0, self._show_com_found, port, dev_type, fw_ver
                    )
                    return

            self.frame.after(
                0, self._status_label.configure, {"text": t("wizard.step1.flash_failed")}
            )

        except Exception as e:
            logger.exception("Flash failed")
            self.frame.after(
                0, self._status_label.configure, {"text": t("wizard.step1.flash_failed")}
            )
            self.frame.after(
                0, self._detail_label.configure, {"text": str(e)}
            )

    def can_proceed(self) -> bool:
        return self._detected

    def get_data(self) -> dict:
        return {
            "port": self._port,
            "device_type": self._device_type,
            "firmware_version": self._fw_version,
        }
