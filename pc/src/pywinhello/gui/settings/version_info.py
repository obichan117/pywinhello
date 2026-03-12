"""Version info: software/firmware versions, update check and apply."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import customtkinter as ctk

from pywinhello.gui.i18n import t

logger = logging.getLogger(__name__)

# Current software version (read from package metadata)
try:
    from importlib.metadata import version as _pkg_version

    _SOFTWARE_VERSION = _pkg_version("pywinhello")
except Exception:
    _SOFTWARE_VERSION = "2.0.0-dev"


class VersionInfo(ctk.CTkFrame):
    """Software/firmware version display with update check button."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        config: dict[str, Any],
        send_command: Callable[[str], str | None],
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._config = config
        self._send = send_command
        self._fw_version = config.get("firmware_version", "unknown")

        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", pady=5)

        # Section title
        ctk.CTkLabel(
            frame,
            text=t("settings.version.title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Software version
        sw_row = ctk.CTkFrame(frame, fg_color="transparent")
        sw_row.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(
            sw_row,
            text=t("settings.version.software_label"),
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        ctk.CTkLabel(
            sw_row,
            text=f"v{_SOFTWARE_VERSION}",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=5)

        self._sw_status = ctk.CTkLabel(
            sw_row,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="green",
        )
        self._sw_status.pack(side="left", padx=5)

        # Firmware version
        fw_row = ctk.CTkFrame(frame, fg_color="transparent")
        fw_row.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(
            fw_row,
            text=t("settings.version.firmware_label"),
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        self._fw_label = ctk.CTkLabel(
            fw_row,
            text=f"v{self._fw_version}",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._fw_label.pack(side="left", padx=5)

        self._fw_status = ctk.CTkLabel(
            fw_row,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="green",
        )
        self._fw_status.pack(side="left", padx=5)

        # Last checked
        checked_row = ctk.CTkFrame(frame, fg_color="transparent")
        checked_row.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(
            checked_row,
            text=t("settings.version.last_checked"),
            font=ctk.CTkFont(size=12),
            text_color="gray50",
        ).pack(side="left")

        self._last_checked = ctk.CTkLabel(
            checked_row,
            text=t("settings.version.never_checked"),
            font=ctk.CTkFont(size=12),
            text_color="gray50",
        )
        self._last_checked.pack(side="left", padx=5)

        # Buttons row
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(5, 10))

        self._check_btn = ctk.CTkButton(
            btn_row,
            text=t("settings.version.btn_check_update"),
            width=120,
            command=self._on_check,
        )
        self._check_btn.pack(side="left")

        self._update_btn = ctk.CTkButton(
            btn_row,
            text=t("settings.version.btn_update_firmware"),
            width=150,
            state="disabled",
            command=self._on_update_firmware,
        )
        self._update_btn.pack(side="left", padx=10)

        self._update_status = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=12)
        )
        self._update_status.pack(side="left", padx=10)

    def _on_check(self) -> None:
        """Check for updates from GitHub releases."""
        self._check_btn.configure(state="disabled")
        self._update_status.configure(
            text=t("settings.version.checking"), text_color="gray50"
        )

        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self) -> None:
        """Fetch latest version info from GitHub."""
        try:
            import requests
            from datetime import datetime

            resp = requests.get(
                "https://api.github.com/repos/obichan117/pywinhello/releases/latest",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                latest_tag = data.get("tag_name", "").lstrip("v")
                now = datetime.now().strftime("%Y-%m-%d %H:%M")

                def _update_ui() -> None:
                    self._last_checked.configure(text=now)

                    # Compare software version
                    if latest_tag and latest_tag != _SOFTWARE_VERSION.replace("-dev", ""):
                        self._sw_status.configure(
                            text=t("settings.version.update_available"),
                            text_color="orange",
                        )
                    else:
                        self._sw_status.configure(
                            text=t("settings.version.latest"),
                            text_color="green",
                        )

                    # Check firmware assets
                    assets = data.get("assets", [])
                    has_uf2 = any(a["name"].endswith(".uf2") for a in assets)
                    if has_uf2:
                        self._fw_status.configure(
                            text=t("settings.version.update_available"),
                            text_color="orange",
                        )
                        self._update_btn.configure(state="normal")
                    else:
                        self._fw_status.configure(
                            text=t("settings.version.latest"),
                            text_color="green",
                        )

                    self._update_status.configure(
                        text=t("settings.version.up_to_date"), text_color="green"
                    )
                    self._check_btn.configure(state="normal")

                self.after(0, _update_ui)
            else:
                self.after(
                    0,
                    self._update_status.configure,
                    {"text": t("settings.version.check_failed"), "text_color": "red"},
                )
                self.after(0, self._check_btn.configure, {"state": "normal"})

        except Exception as e:
            logger.debug("Update check failed: %s", e)
            self.after(
                0,
                self._update_status.configure,
                {"text": t("settings.version.check_failed"), "text_color": "red"},
            )
            self.after(0, self._check_btn.configure, {"state": "normal"})

    def _on_update_firmware(self) -> None:
        """Trigger firmware update via serial FLASH command."""
        self._update_btn.configure(state="disabled")
        self._update_status.configure(
            text=t("settings.version.updating"), text_color="gray50"
        )

        def _update() -> None:
            try:
                resp = self._send("FLASH")
                if resp and resp.startswith("OK"):
                    self.after(
                        0,
                        self._update_status.configure,
                        {"text": t("settings.version.update_success"), "text_color": "green"},
                    )
                else:
                    self.after(
                        0,
                        self._update_status.configure,
                        {
                            "text": t("settings.version.update_failed", error=resp or ""),
                            "text_color": "red",
                        },
                    )
            except Exception as e:
                self.after(
                    0,
                    self._update_status.configure,
                    {"text": t("settings.version.update_failed", error=str(e)), "text_color": "red"},
                )
            finally:
                self.after(0, self._update_btn.configure, {"state": "normal"})

        threading.Thread(target=_update, daemon=True).start()
