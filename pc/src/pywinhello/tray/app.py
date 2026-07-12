from __future__ import annotations

import logging
import subprocess
import sys
import threading

import pystray
from PIL import Image, ImageDraw

from pywinhello.core.diagnostics import LockUnlockTest
from pywinhello.core.status_service import StatusReport, gather_status

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 10.0
_ICON_SIZE = 64
_ARMED_COLOR = (34, 139, 34, 255)
_DISARMED_COLOR = (128, 128, 128, 255)


def is_armed(status: StatusReport) -> bool:
    return status.device_connected and status.pin_set and status.schedule_armed


def build_icon_image(armed: bool) -> Image.Image:
    color = _ARMED_COLOR if armed else _DISARMED_COLOR
    image = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, _ICON_SIZE - 4, _ICON_SIZE - 4), fill=color)
    return image


def _build_tooltip(status: StatusReport) -> str:
    return "pywinhello — armed" if is_armed(status) else "pywinhello — disarmed"


def _build_status_message(status: StatusReport) -> str:
    return "\n".join(
        [
            f"Device: {'connected' if status.device_connected else 'disconnected'}",
            f"PIN set: {'yes' if status.pin_set else 'no'}",
            f"Schedule armed: {'yes' if status.schedule_armed else 'no'}",
            f"Monitor running: {'yes' if status.monitor_running else 'no'}",
        ]
    )


class TrayApp:
    def __init__(self) -> None:
        self._status = gather_status()
        self._stop_event = threading.Event()
        self._icon = pystray.Icon(
            "pywinhello",
            build_icon_image(is_armed(self._status)),
            _build_tooltip(self._status),
            menu=self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Status", self._on_status),
            pystray.MenuItem("Test unlock", self._on_test_unlock),
            pystray.MenuItem("Open settings", self._on_open_settings),
            pystray.MenuItem("Quit", self._on_quit),
        )

    def _on_status(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        icon.notify(_build_status_message(self._status), "pywinhello status")

    def _on_test_unlock(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        threading.Thread(target=self._run_test_unlock, daemon=True).start()

    def _run_test_unlock(self) -> None:
        result = LockUnlockTest().run()
        if result.passed:
            message = f"Unlock test passed in {result.elapsed:.1f}s"
        else:
            message = f"Unlock test failed: {result.error}"
        self._icon.notify(message, "pywinhello test unlock")

    def _on_open_settings(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        subprocess.Popen([sys.executable, "-m", "pywinhello.gui.app"])

    def _on_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._stop_event.set()
        icon.stop()

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(_POLL_INTERVAL_SECONDS):
            self._refresh_status()

    def _refresh_status(self) -> None:
        self._status = gather_status()
        self._icon.icon = build_icon_image(is_armed(self._status))
        self._icon.title = _build_tooltip(self._status)

    def run(self) -> None:
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self._icon.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    if sys.platform != "win32":
        logger.error("pywinhello tray is Windows-only")
        return
    TrayApp().run()


if __name__ == "__main__":
    main()
