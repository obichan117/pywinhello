from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from pywinhello.core import status_service
from pywinhello.setup.detect import DeviceState


@contextmanager
def _proto_returning(status_dict):
    proto = MagicMock()
    proto.status.return_value = status_dict
    proto.__enter__ = MagicMock(return_value=proto)
    proto.__exit__ = MagicMock(return_value=False)
    with patch.object(status_service, "SerialProtocol", return_value=proto):
        yield


class TestReadPinSet:
    def test_reads_firmware_pin_stored_key(self):
        # Firmware STATUS emits "pin_stored", not "pin_set" — regression guard.
        with _proto_returning({"pin_stored": True, "firmware": "1.2.3"}):
            assert status_service._read_pin_set("COM7") is True

    def test_pin_stored_false(self):
        with _proto_returning({"pin_stored": False}):
            assert status_service._read_pin_set("COM7") is False

    def test_missing_key_defaults_false(self):
        with _proto_returning({"firmware": "1.2.3"}):
            assert status_service._read_pin_set("COM7") is False

    def test_serial_error_is_swallowed_to_false(self):
        with patch.object(status_service, "SerialProtocol", side_effect=OSError("no port")):
            assert status_service._read_pin_set("COM7") is False


class TestGatherStatus:
    def test_disconnected_device_never_raises(self):
        dev = MagicMock(state=DeviceState.NOT_FOUND, port=None, firmware_version=None)
        with (
            patch.object(status_service, "detect", return_value=dev),
            patch.object(status_service, "_is_schedule_armed", return_value=False),
            patch.object(status_service, "_is_monitor_running", return_value=False),
        ):
            report = status_service.gather_status()
        assert report.device_connected is False
        assert report.pin_set is False

    def test_monitor_check_targets_monitor_exe_not_cli(self):
        # pywinhello.exe is the CLI now; the monitor is pywinhello-monitor.exe.
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return MagicMock(stdout="")

        with (
            patch.object(status_service.sys, "platform", "win32"),
            patch.object(status_service.subprocess, "run", side_effect=fake_run),
        ):
            status_service._is_monitor_running()
        assert any("pywinhello-monitor.exe" in part for part in captured["cmd"])
