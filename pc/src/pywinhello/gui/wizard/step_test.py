"""Step 2/4: Notepad integration test with auto-calibration."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from typing import TYPE_CHECKING

import customtkinter as ctk

from pywinhello.gui.i18n import t
from pywinhello.gui.wizard.base import WizardStep

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_TEST_STRING = "pywinhello test"
_SPEED_INTERVALS = [50, 80, 100, 120, 150]
_SPEED_TEST_STRING = "The quick brown fox jumps over the lazy dog 1234567890"


def _get_clipboard_text() -> str:
    """Read text from Windows clipboard via ctypes."""
    try:
        import ctypes as _ct

        CF_UNICODETEXT = 13
        user32 = _ct.windll.user32
        kernel32 = _ct.windll.kernel32

        user32.OpenClipboard(0)
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                kernel32.GlobalLock.restype = _ct.c_wchar_p
                text = kernel32.GlobalLock(handle)
                kernel32.GlobalUnlock(handle)
                return text or ""
        finally:
            user32.CloseClipboard()
    except Exception:
        pass
    return ""


def _set_clipboard_text(text: str) -> None:
    """Write text to Windows clipboard via ctypes."""
    try:
        import ctypes as _ct

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        user32 = _ct.windll.user32
        kernel32 = _ct.windll.kernel32

        data = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        kernel32.GlobalLock.restype = _ct.c_void_p
        ptr = kernel32.GlobalLock(h_mem)
        _ct.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h_mem)

        user32.OpenClipboard(0)
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        user32.CloseClipboard()
    except Exception:
        pass


class TestStep(WizardStep):
    """Step 2: Notepad typing test with auto-calibration of keystroke timing."""

    @property
    def title(self) -> str:
        return t("wizard.step2.title")

    def build(self) -> None:
        # Description
        self._desc = ctk.CTkLabel(
            self.frame,
            text=t("wizard.step2.desc"),
            font=ctk.CTkFont(size=13),
            text_color="gray50",
        )
        self._desc.pack(pady=(0, 5))

        # Warning
        self._warning = ctk.CTkLabel(
            self.frame,
            text=t("wizard.step2.warning"),
            font=ctk.CTkFont(size=12),
            text_color="orange",
        )
        self._warning.pack(pady=(0, 10))

        # Test results frame
        self._results_frame = ctk.CTkFrame(self.frame)
        self._results_frame.pack(fill="x", pady=10, padx=10)

        self._step_labels: dict[str, ctk.CTkLabel] = {}
        self._status_labels: dict[str, ctk.CTkLabel] = {}

        steps = [
            ("open", t("wizard.step2.notepad_open")),
            ("type", t("wizard.step2.type_test")),
            ("speed", t("wizard.step2.speed_test")),
            ("special", t("wizard.step2.special_test")),
            ("close", t("wizard.step2.notepad_close")),
        ]
        for i, (key, label_text) in enumerate(steps):
            lbl = ctk.CTkLabel(
                self._results_frame,
                text=label_text,
                font=ctk.CTkFont(size=13),
                anchor="w",
            )
            lbl.grid(row=i, column=0, sticky="w", padx=10, pady=4)
            self._step_labels[key] = lbl

            status = ctk.CTkLabel(
                self._results_frame,
                text=t("test.notepad.status_waiting"),
                font=ctk.CTkFont(size=13),
                text_color="gray50",
                anchor="e",
            )
            status.grid(row=i, column=1, sticky="e", padx=10, pady=4)
            self._status_labels[key] = status

        self._results_frame.columnconfigure(0, weight=1)
        self._results_frame.columnconfigure(1, weight=0)

        # Calibration result
        self._calibration_label = ctk.CTkLabel(
            self.frame,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._calibration_label.pack(pady=5)

        # Troubleshooting (hidden by default)
        self._trouble_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self._trouble_title = ctk.CTkLabel(
            self._trouble_frame,
            text=t("wizard.step2.troubleshoot"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="orange",
            anchor="w",
        )
        self._trouble_title.pack(anchor="w")
        for hint_key in ("troubleshoot_hub", "troubleshoot_port", "troubleshoot_restart"):
            ctk.CTkLabel(
                self._trouble_frame,
                text=t(f"wizard.step2.{hint_key}"),
                font=ctk.CTkFont(size=12),
                text_color="gray50",
                anchor="w",
            ).pack(anchor="w", padx=10)

        # Buttons
        self._btn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self._btn_frame.pack(pady=10)

        self._start_btn = ctk.CTkButton(
            self._btn_frame,
            text=t("wizard.step2.btn_start_test"),
            command=self._on_start,
        )
        self._start_btn.pack(side="left", padx=5)

        self._retest_btn = ctk.CTkButton(
            self._btn_frame,
            text=t("wizard.step2.btn_retest"),
            command=self._on_start,
            state="disabled",
        )

        # State
        self._all_passed = False
        self._optimal_interval: int | None = None

    def on_enter(self) -> None:
        self.wizard.nav_bar.set_next_enabled(self._all_passed)

    def _set_status(self, key: str, text: str, color: str = "gray50") -> None:
        """Update a step's status label on the main thread."""
        self.frame.after(
            0, self._status_labels[key].configure, {"text": text, "text_color": color}
        )

    def _on_start(self) -> None:
        """Start the test sequence in a background thread."""
        self._start_btn.configure(state="disabled")
        self._retest_btn.pack_forget()
        self._trouble_frame.pack_forget()
        self._calibration_label.configure(text="")
        self._all_passed = False
        self.wizard.nav_bar.set_next_enabled(False)

        # Reset all statuses
        for key in self._status_labels:
            self._set_status(key, t("test.notepad.status_waiting"), "gray50")

        threading.Thread(target=self._run_tests, daemon=True).start()

    def _get_hid(self):
        """Get an HIDKeyboard connected to the Pico."""
        from pywinhello.hid import HIDKeyboard

        port = self.wizard.collected_data.get("port")
        return HIDKeyboard(port=port)

    def _run_tests(self) -> None:
        """Execute all test steps sequentially."""
        passed = True

        # Step 1: Open Notepad
        self._set_status("open", t("test.notepad.status_running"), "white")
        try:
            subprocess.Popen(["notepad.exe"])
            time.sleep(1.5)  # Wait for window to appear and get focus
            self._set_status("open", t("test.notepad.status_pass"), "green")
        except Exception:
            self._set_status("open", t("test.notepad.status_fail"), "red")
            logger.exception("Failed to open Notepad")
            passed = False
            self._finish_tests(passed)
            return

        try:
            hid = self._get_hid()
        except Exception as e:
            self._set_status("type", f"HID error: {e}", "red")
            self._finish_tests(False)
            return

        try:
            # Step 2: Type test string
            self._set_status("type", t("test.notepad.status_running"), "white")
            _set_clipboard_text("")  # Clear clipboard
            hid.type_text(_TEST_STRING)
            time.sleep(0.5)

            # Read back via Ctrl+A, Ctrl+C
            hid.key_combo("CTRL", "A")
            time.sleep(0.2)
            hid.key_combo("CTRL", "C")
            time.sleep(0.3)
            actual = _get_clipboard_text().strip()

            if actual == _TEST_STRING:
                self._set_status("type", t("wizard.step2.type_match"), "green")
            else:
                self._set_status("type", t("wizard.step2.type_mismatch"), "red")
                passed = False

            # Clear notepad for speed test
            hid.key_combo("CTRL", "A")
            time.sleep(0.1)
            hid.press_key("DELETE")
            time.sleep(0.2)

            # Step 3: Speed calibration
            self._set_status("speed", t("test.notepad.status_running"), "white")
            optimal = None
            for interval in _SPEED_INTERVALS:
                self.frame.after(
                    0,
                    self._calibration_label.configure,
                    {"text": t("wizard.step2.speed_testing", interval=interval)},
                )

                # Set delay and type
                hid.set_delay(interval)
                time.sleep(0.2)
                _set_clipboard_text("")
                hid.type_text(_SPEED_TEST_STRING)
                time.sleep(0.8)

                # Read back
                hid.key_combo("CTRL", "A")
                time.sleep(0.2)
                hid.key_combo("CTRL", "C")
                time.sleep(0.3)
                result = _get_clipboard_text().strip()

                if result == _SPEED_TEST_STRING:
                    optimal = interval
                    break

                # Clear for next attempt
                hid.press_key("DELETE")
                time.sleep(0.2)

            if optimal is not None:
                self._optimal_interval = optimal
                self._set_status(
                    "speed", t("wizard.step2.speed_pass", interval=optimal), "green"
                )
                self.frame.after(
                    0,
                    self._calibration_label.configure,
                    {"text": t("wizard.step2.speed_calibrated", interval=optimal)},
                )
                # Save calibrated interval to Pico
                hid.set_delay(optimal)
            else:
                self._set_status("speed", t("wizard.step2.speed_all_failed"), "red")
                passed = False

            # Clear for special key test
            hid.key_combo("CTRL", "A")
            time.sleep(0.1)
            hid.press_key("DELETE")
            time.sleep(0.2)

            # Step 4: Special keys
            self._set_status("special", t("test.notepad.status_running"), "white")
            hid.type_text("line1")
            hid.press_key("ENTER")
            hid.type_text("line2")
            time.sleep(0.5)

            hid.key_combo("CTRL", "A")
            time.sleep(0.2)
            hid.key_combo("CTRL", "C")
            time.sleep(0.3)
            result = _get_clipboard_text().strip()

            if "line1" in result and "line2" in result and result.index("line2") > result.index("line1"):
                self._set_status("special", t("wizard.step2.special_pass"), "green")
            else:
                self._set_status("special", t("wizard.step2.special_fail"), "red")
                passed = False

            # Step 5: Close Notepad
            self._set_status("close", t("test.notepad.status_running"), "white")
            hid.key_combo("CTRL", "A")
            time.sleep(0.1)
            hid.press_key("DELETE")
            time.sleep(0.2)
            hid.key_combo("ALT", "F4")
            time.sleep(1.0)

            # Handle save dialog if it appears - press "Don't Save" (N key or Tab+Enter)
            try:
                hid.press_key("TAB")
                time.sleep(0.1)
                hid.press_key("ENTER")
            except Exception:
                pass

            time.sleep(0.5)
            self._set_status("close", t("wizard.step2.notepad_closed"), "green")

            hid.close()

        except Exception:
            logger.exception("Test failed")
            passed = False
            try:
                hid.close()
            except Exception:
                pass

        self._finish_tests(passed)

    def _finish_tests(self, passed: bool) -> None:
        """Update UI after all tests complete."""
        self._all_passed = passed

        def _update() -> None:
            if passed:
                self._calibration_label.configure(
                    text=t("wizard.step2.all_pass"), text_color="green"
                )
            else:
                self._calibration_label.configure(
                    text=t("wizard.step2.some_fail"), text_color="orange"
                )
                self._trouble_frame.pack(fill="x", padx=20, pady=5)

            self._start_btn.configure(state="normal")
            self._retest_btn.pack(side="left", padx=5)
            self._retest_btn.configure(state="normal")
            self.wizard.nav_bar.set_next_enabled(passed)

        self.frame.after(0, _update)

    def can_proceed(self) -> bool:
        return self._all_passed

    def get_data(self) -> dict:
        return {"optimal_interval": self._optimal_interval}
