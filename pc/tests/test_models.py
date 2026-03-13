"""Tests for data models."""

from pywinhello.models import AuthEvent


class TestAuthEvent:
    def test_defaults(self):
        e = AuthEvent()
        assert e.owner_exe is None
        assert e.pin_sent is False
        assert e.dialog_dismissed is False
        assert e.elapsed == 0.0
        assert e.error is None

    def test_with_values(self):
        e = AuthEvent(
            owner_exe="test.exe",
            pin_sent=True,
            dialog_dismissed=True,
            elapsed=1.5,
        )
        assert e.owner_exe == "test.exe"
        assert e.pin_sent is True
        assert e.dialog_dismissed is True
        assert e.elapsed == 1.5
        assert e.error is None

    def test_with_error(self):
        e = AuthEvent(error="timeout")
        assert e.error == "timeout"
        assert e.pin_sent is False
