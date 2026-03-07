"""Tests for data models."""

from pywinhello.models import AppConfig, AuthEvent, MonitorConfig


class TestAuthEvent:
    def test_defaults(self):
        e = AuthEvent()
        assert e.owner_exe is None
        assert e.pin_sent is False
        assert e.dialog_dismissed is False
        assert e.elapsed == 0.0
        assert e.error is None


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig(exe="test.exe", pin="1234")
        assert cfg.pin_select_keys == ["ESCAPE"]

    def test_custom_keys(self):
        cfg = AppConfig(exe="test.exe", pin="1234", pin_select_keys=["TAB", "ENTER"])
        assert cfg.pin_select_keys == ["TAB", "ENTER"]


class TestMonitorConfig:
    def test_defaults(self):
        cfg = MonitorConfig()
        assert cfg.apps == []
        assert cfg.hid_port is None
        assert cfg.inter_key_delay_ms == 50

    def test_with_apps(self):
        cfg = MonitorConfig(
            apps=[AppConfig(exe="a.exe", pin="1111")],
            hid_port="COM3",
        )
        assert len(cfg.apps) == 1
        assert cfg.hid_port == "COM3"
