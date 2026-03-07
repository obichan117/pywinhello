"""Tests for YAML config loader."""

from pathlib import Path

import pytest

from pywinhello.config import load_config


@pytest.fixture
def tmp_yaml(tmp_path):
    """Helper to create a temp YAML file."""

    def _write(content: str) -> Path:
        p = tmp_path / "config.yaml"
        p.write_text(content)
        return p

    return _write


class TestLoadConfig:
    def test_valid_config(self, tmp_yaml):
        cfg = load_config(
            tmp_yaml(
                """
apps:
  - exe: test.exe
    pin: "1234"
  - exe: other.exe
    pin: "5678"
    pin_select_keys: [TAB, ENTER]
hid_port: COM3
inter_key_delay_ms: 100
"""
            )
        )
        assert len(cfg.apps) == 2
        assert cfg.apps[0].exe == "test.exe"
        assert cfg.apps[0].pin == "1234"
        assert cfg.apps[0].pin_select_keys == ["ESCAPE"]
        assert cfg.apps[1].pin_select_keys == ["TAB", "ENTER"]
        assert cfg.hid_port == "COM3"
        assert cfg.inter_key_delay_ms == 100

    def test_minimal_config(self, tmp_yaml):
        cfg = load_config(tmp_yaml("apps: []"))
        assert cfg.apps == []
        assert cfg.hid_port is None

    def test_pin_coerced_to_string(self, tmp_yaml):
        cfg = load_config(
            tmp_yaml(
                """
apps:
  - exe: test.exe
    pin: 1234
"""
            )
        )
        assert cfg.apps[0].pin == "1234"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_invalid_root_type(self, tmp_yaml):
        with pytest.raises(ValueError, match="YAML mapping"):
            load_config(tmp_yaml("just a string"))

    def test_apps_not_list(self, tmp_yaml):
        with pytest.raises(ValueError, match="must be a list"):
            load_config(tmp_yaml("apps: not_a_list"))

    def test_app_missing_exe(self, tmp_yaml):
        with pytest.raises(ValueError, match="missing required field 'exe'"):
            load_config(tmp_yaml("apps:\n  - pin: '1234'"))

    def test_app_missing_pin(self, tmp_yaml):
        with pytest.raises(ValueError, match="missing required field 'pin'"):
            load_config(tmp_yaml("apps:\n  - exe: test.exe"))

    def test_app_not_mapping(self, tmp_yaml):
        with pytest.raises(ValueError, match="must be a mapping"):
            load_config(tmp_yaml("apps:\n  - just_a_string"))

    def test_defaults_without_optional_fields(self, tmp_yaml):
        cfg = load_config(
            tmp_yaml(
                """
apps:
  - exe: test.exe
    pin: "0000"
"""
            )
        )
        assert cfg.hid_port is None
        assert cfg.inter_key_delay_ms == 50
        assert cfg.dialog_wait_timeout == 5.0
