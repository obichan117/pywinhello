"""Tests for the Typer CLI — status/doctor/config/setup command wiring."""

from __future__ import annotations

import importlib
import json
from unittest.mock import MagicMock

from typer.testing import CliRunner

from pywinhello.core import StatusReport
from pywinhello.models import BoardVariant
from pywinhello.serial.protocol import SerialProtocol
from pywinhello.setup import BUNDLED_FW_VERSION, ProvisionResult
from pywinhello.setup.detect import DetectedDevice, DeviceState

# "pywinhello.cli.app" is shadowed by cli/__init__.py's own `app` re-export,
# so fetch the actual app.py module (not the Typer instance) directly.
cli_app = importlib.import_module("pywinhello.cli.app")
app = cli_app.app
runner = CliRunner()


class TestStatus:
    def test_json_matches_status_report_shape(self, monkeypatch):
        report = StatusReport(
            device_connected=True,
            port="COM8",
            firmware_version="1.0.0",
            pin_set=True,
            schedule_armed=False,
            monitor_running=True,
        )
        monkeypatch.setattr(cli_app, "gather_status", lambda: report)

        result = runner.invoke(app, ["status", "--json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout) == {
            "device_connected": True,
            "port": "COM8",
            "firmware_version": "1.0.0",
            "pin_set": True,
            "schedule_armed": False,
            "monitor_running": True,
        }

    def test_human_readable_does_not_error(self, monkeypatch):
        report = StatusReport(
            device_connected=False,
            port=None,
            firmware_version=None,
            pin_set=False,
            schedule_armed=False,
            monitor_running=False,
        )
        monkeypatch.setattr(cli_app, "gather_status", lambda: report)

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0


class TestConfig:
    def _patch_device(self, monkeypatch):
        mock_device = MagicMock()
        monkeypatch.setattr(cli_app, "find_pico_port", lambda: "COM8")
        monkeypatch.setattr(cli_app, "PicoDevice", lambda port=None: mock_device)
        return mock_device

    def test_get_with_no_key_prints_full_config_as_json(self, monkeypatch):
        self._patch_device(monkeypatch)
        config = {"schedule": {"time": "07:45"}}
        monkeypatch.setattr(cli_app, "read_config", lambda protocol: config)

        result = runner.invoke(app, ["config", "get"])

        assert result.exit_code == 0
        assert json.loads(result.stdout) == {"schedule": {"time": "07:45"}}

    def test_get_with_dotted_key_prints_field_value(self, monkeypatch):
        self._patch_device(monkeypatch)
        config = {"schedule": {"time": "07:45"}}
        monkeypatch.setattr(cli_app, "read_config", lambda protocol: config)

        result = runner.invoke(app, ["config", "get", "schedule.time"])

        assert result.exit_code == 0
        assert result.stdout.strip() == "07:45"

    def test_get_with_unknown_key_exits_nonzero(self, monkeypatch):
        self._patch_device(monkeypatch)
        monkeypatch.setattr(cli_app, "read_config", lambda protocol: {})

        result = runner.invoke(app, ["config", "get", "missing.field"])

        assert result.exit_code != 0

    def test_set_writes_parsed_patch_to_device_protocol(self, monkeypatch):
        mock_device = self._patch_device(monkeypatch)
        calls: dict[str, object] = {}

        def fake_write_config(protocol, patch):
            calls["protocol"] = protocol
            calls["patch"] = patch

        monkeypatch.setattr(cli_app, "write_config", fake_write_config)

        result = runner.invoke(app, ["config", "set", "schedule.time=08:00"])

        assert result.exit_code == 0
        assert calls["patch"] == {"schedule": {"time": "08:00"}}
        assert calls["protocol"] is mock_device.protocol

    def test_set_with_invalid_assignment_exits_nonzero_without_connecting(self, monkeypatch):
        find_port = MagicMock(return_value="COM8")
        monkeypatch.setattr(cli_app, "find_pico_port", find_port)

        result = runner.invoke(app, ["config", "set", "no-equals-sign"])

        assert result.exit_code != 0
        find_port.assert_not_called()


class TestSetup:
    def test_prompts_for_pin_with_hidden_confirmed_input(self, monkeypatch):
        monkeypatch.setattr(
            cli_app,
            "provision",
            lambda on_progress=None: ProvisionResult(
                success=True, state=DeviceState.RUNNING_PYWINHELLO, message="Setup complete!"
            ),
        )
        mock_device = MagicMock()
        mock_device.protocol = MagicMock(spec=SerialProtocol)
        mock_device.info = MagicMock(port="COM8")
        monkeypatch.setattr(cli_app, "find_pico_port", lambda: "COM8")
        monkeypatch.setattr(cli_app, "PicoDevice", lambda port=None: mock_device)

        result = runner.invoke(app, ["setup"], input="1234\n1234\n07:45\nmon,tue\nn\n")

        assert result.exit_code == 0
        mock_device.protocol.setup_pin.assert_called_once_with("1234")
        mock_device.protocol.set_config.assert_called_once_with(
            {"schedule": {"time": "07:45", "days": ["mon", "tue"]}}
        )

    def test_aborts_before_pin_prompt_when_provision_fails(self, monkeypatch):
        monkeypatch.setattr(
            cli_app,
            "provision",
            lambda on_progress=None: ProvisionResult(
                success=False, state=DeviceState.NOT_FOUND, message="No Pico detected."
            ),
        )
        register_pin = MagicMock()
        monkeypatch.setattr(cli_app, "register_pin", register_pin)

        result = runner.invoke(app, ["setup"], input="")

        assert result.exit_code != 0
        register_pin.assert_not_called()

    def test_never_accepts_pin_as_a_command_line_argument(self):
        result = runner.invoke(app, ["setup", "--pin", "1234"])

        assert result.exit_code != 0
        assert "1234" not in (result.stdout or "")


class TestDoctor:
    def test_exits_nonzero_when_device_not_usable(self, monkeypatch):
        monkeypatch.setattr(
            cli_app,
            "gather_status",
            lambda: StatusReport(
                device_connected=False,
                port=None,
                firmware_version=None,
                pin_set=False,
                schedule_armed=False,
                monitor_running=False,
            ),
        )
        monkeypatch.setattr(cli_app, "detect", lambda: DetectedDevice(state=DeviceState.NOT_FOUND))

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code != 0

    def test_exits_zero_when_device_connected_and_pin_set(self, monkeypatch):
        monkeypatch.setattr(
            cli_app,
            "gather_status",
            lambda: StatusReport(
                device_connected=True,
                port="COM8",
                firmware_version=BUNDLED_FW_VERSION,
                pin_set=True,
                schedule_armed=True,
                monitor_running=True,
            ),
        )
        monkeypatch.setattr(
            cli_app,
            "detect",
            lambda: DetectedDevice(
                state=DeviceState.RUNNING_PYWINHELLO,
                board=BoardVariant.PICO_W,
                port="COM8",
                firmware_version=BUNDLED_FW_VERSION,
            ),
        )

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0


class TestNoDevice:
    def test_config_get_fails_fast_with_clear_message_when_no_pico(self, monkeypatch):
        monkeypatch.setattr(cli_app, "find_pico_port", lambda: None)

        result = runner.invoke(app, ["config", "get"])

        assert result.exit_code != 0
        assert "No Pico found" in result.stdout
