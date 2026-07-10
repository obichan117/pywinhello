"""Tests for config_service — dotted-path helpers and Pico read/write."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pywinhello.core.config_service import (
    build_patch,
    get_field,
    parse_assignment,
    read_config,
    write_config,
)
from pywinhello.serial.protocol import SerialProtocol


class TestParseAssignment:
    def test_string_value(self):
        assert parse_assignment("wifi.ssid=MyNetwork") == ("wifi.ssid", "MyNetwork")

    def test_time_value_stays_string(self):
        assert parse_assignment("schedule.time=08:00") == ("schedule.time", "08:00")

    def test_int_value(self):
        assert parse_assignment("timing.retry_count=3") == ("timing.retry_count", 3)

    def test_float_value(self):
        assert parse_assignment("timing.dialog_wait_sec=1.5") == (
            "timing.dialog_wait_sec",
            1.5,
        )

    def test_bool_true(self):
        assert parse_assignment("apps.notepad=true") == ("apps.notepad", True)

    def test_bool_false_case_insensitive(self):
        assert parse_assignment("apps.notepad=FALSE") == ("apps.notepad", False)

    def test_list_value(self):
        dotted, value = parse_assignment("schedule.days=mon,tue,wed")
        assert dotted == "schedule.days"
        assert value == ["mon", "tue", "wed"]

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError):
            parse_assignment("schedule.time")

    def test_missing_key_raises(self):
        with pytest.raises(ValueError):
            parse_assignment("=08:00")


class TestBuildPatch:
    def test_single_level(self):
        assert build_patch("locale", "en") == {"locale": "en"}

    def test_nested(self):
        assert build_patch("schedule.time", "08:00") == {"schedule": {"time": "08:00"}}

    def test_deeply_nested(self):
        assert build_patch("timing.retry_count", 3) == {"timing": {"retry_count": 3}}


class TestGetField:
    def test_top_level(self):
        assert get_field({"locale": "en"}, "locale") == "en"

    def test_nested(self):
        config = {"schedule": {"time": "08:00", "days": ["mon"]}}
        assert get_field(config, "schedule.time") == "08:00"

    def test_missing_top_level_raises(self):
        with pytest.raises(KeyError):
            get_field({}, "locale")

    def test_missing_nested_raises(self):
        with pytest.raises(KeyError):
            get_field({"schedule": {}}, "schedule.time")

    def test_non_dict_intermediate_raises(self):
        with pytest.raises(KeyError):
            get_field({"schedule": "not a dict"}, "schedule.time")


class TestReadWriteConfig:
    def test_read_config_calls_get_config(self):
        protocol = MagicMock(spec=SerialProtocol)
        protocol.get_config.return_value = {"locale": "en"}

        result = read_config(protocol)

        assert result == {"locale": "en"}
        protocol.get_config.assert_called_once_with()

    def test_write_config_calls_set_config(self):
        protocol = MagicMock(spec=SerialProtocol)
        patch = {"schedule": {"time": "08:00"}}

        write_config(protocol, patch)

        protocol.set_config.assert_called_once_with(patch)
