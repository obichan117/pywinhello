"""Tests for pin_service — validation rules and Pico registration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pywinhello.core.pin_service import register_pin, validate_pin
from pywinhello.serial.protocol import SerialProtocol


class TestValidatePin:
    def test_valid_pin_does_not_raise(self):
        validate_pin("1234")

    def test_empty_pin_raises(self):
        with pytest.raises(ValueError):
            validate_pin("")

    def test_too_short_pin_raises(self):
        with pytest.raises(ValueError):
            validate_pin("123")

    def test_error_message_is_plain_text_not_i18n_key(self):
        with pytest.raises(ValueError) as exc_info:
            validate_pin("")
        message = str(exc_info.value)
        assert "wizard" not in message
        assert " " in message


class TestRegisterPin:
    def test_valid_pin_calls_setup_pin(self):
        protocol = MagicMock(spec=SerialProtocol)

        register_pin(protocol, "1234")

        protocol.setup_pin.assert_called_once_with("1234")

    def test_invalid_pin_raises_without_calling_setup_pin(self):
        protocol = MagicMock(spec=SerialProtocol)

        with pytest.raises(ValueError):
            register_pin(protocol, "12")

        protocol.setup_pin.assert_not_called()
