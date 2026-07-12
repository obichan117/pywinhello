"""Tests for schedule_service — HH:MM/day formatting and Pico patch writes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pywinhello.core.schedule_service import (
    DAY_KEYS,
    DEFAULT_DAYS,
    format_time,
    parse_days,
    parse_time,
    save_schedule,
)
from pywinhello.serial.protocol import SerialProtocol


class TestFormatTime:
    def test_pads_single_digits(self):
        assert format_time(7, 5) == "07:05"

    def test_double_digits(self):
        assert format_time(23, 59) == "23:59"

    def test_hour_out_of_range_raises(self):
        with pytest.raises(ValueError):
            format_time(24, 0)

    def test_minute_out_of_range_raises(self):
        with pytest.raises(ValueError):
            format_time(0, 60)


class TestParseTime:
    def test_parses_hh_mm(self):
        assert parse_time("07:45") == (7, 45)

    def test_missing_colon_raises(self):
        with pytest.raises(ValueError):
            parse_time("0745")


class TestParseDays:
    def test_valid_days_lowercased(self):
        assert parse_days(["MON", "Tue"]) == ["mon", "tue"]

    def test_default_days_are_valid(self):
        assert parse_days(DEFAULT_DAYS) == DEFAULT_DAYS

    def test_unknown_day_raises(self):
        with pytest.raises(ValueError):
            parse_days(["mon", "notaday"])

    def test_all_day_keys_valid(self):
        assert parse_days(DAY_KEYS) == DAY_KEYS


class TestSaveSchedule:
    def test_builds_expected_patch(self):
        protocol = MagicMock(spec=SerialProtocol)

        save_schedule(protocol, hour=7, minute=45, days=["mon", "wed", "fri"])

        protocol.set_config.assert_called_once_with(
            {"schedule": {"time": "07:45", "days": ["mon", "wed", "fri"]}}
        )

    def test_invalid_day_raises_without_calling_set_config(self):
        protocol = MagicMock(spec=SerialProtocol)

        with pytest.raises(ValueError):
            save_schedule(protocol, hour=7, minute=45, days=["notaday"])

        protocol.set_config.assert_not_called()

    def test_invalid_time_raises_without_calling_set_config(self):
        protocol = MagicMock(spec=SerialProtocol)

        with pytest.raises(ValueError):
            save_schedule(protocol, hour=25, minute=0, days=["mon"])

        protocol.set_config.assert_not_called()
