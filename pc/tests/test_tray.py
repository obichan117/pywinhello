from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pywinhello.core.status_service import StatusReport
from pywinhello.tray.app import TrayApp, build_icon_image, is_armed

_ARMED_STATUS = StatusReport(
    device_connected=True,
    port="COM8",
    firmware_version="1.0.0",
    pin_set=True,
    schedule_armed=True,
    monitor_running=True,
)


def _status(**overrides) -> StatusReport:
    fields = _ARMED_STATUS.__dict__ | overrides
    return StatusReport(**fields)


class TestIsArmed:
    def test_is_armed_true_when_connected_pin_set_and_scheduled(self) -> None:
        assert is_armed(_ARMED_STATUS) is True

    def test_is_armed_false_when_device_disconnected(self) -> None:
        assert is_armed(_status(device_connected=False)) is False

    def test_is_armed_false_when_pin_not_set(self) -> None:
        assert is_armed(_status(pin_set=False)) is False

    def test_is_armed_false_when_schedule_not_armed(self) -> None:
        assert is_armed(_status(schedule_armed=False)) is False


class TestBuildIconImage:
    def test_armed_image_uses_armed_color(self) -> None:
        image = build_icon_image(armed=True)
        assert image.getpixel((32, 32)) == (34, 139, 34, 255)

    def test_disarmed_image_uses_disarmed_color(self) -> None:
        image = build_icon_image(armed=False)
        assert image.getpixel((32, 32)) == (128, 128, 128, 255)


class TestTrayAppMenu:
    def test_builds_menu_with_expected_items(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "pywinhello.tray.app.gather_status", MagicMock(return_value=_ARMED_STATUS)
        )
        mock_icon_cls = MagicMock()
        monkeypatch.setattr("pywinhello.tray.app.pystray.Icon", mock_icon_cls)

        TrayApp()

        menu = mock_icon_cls.call_args.kwargs["menu"]
        menu_texts = [item.text for item in menu]
        assert menu_texts == ["Status", "Test unlock", "Open settings", "Quit"]

    def test_icon_uses_armed_image_when_status_is_armed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "pywinhello.tray.app.gather_status", MagicMock(return_value=_ARMED_STATUS)
        )
        mock_icon_cls = MagicMock()
        monkeypatch.setattr("pywinhello.tray.app.pystray.Icon", mock_icon_cls)

        TrayApp()

        image = mock_icon_cls.call_args.args[1]
        assert image.getpixel((32, 32)) == (34, 139, 34, 255)

    def test_icon_uses_disarmed_image_when_status_is_disarmed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "pywinhello.tray.app.gather_status",
            MagicMock(return_value=_status(pin_set=False)),
        )
        mock_icon_cls = MagicMock()
        monkeypatch.setattr("pywinhello.tray.app.pystray.Icon", mock_icon_cls)

        TrayApp()

        image = mock_icon_cls.call_args.args[1]
        assert image.getpixel((32, 32)) == (128, 128, 128, 255)
