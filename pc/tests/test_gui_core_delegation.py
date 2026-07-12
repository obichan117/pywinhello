"""Import-smoke + delegation test: settings/wizard panels call pywinhello.core
services (not raw string commands) through a mocked Pico connection/protocol.
"""

from __future__ import annotations

import importlib
import pkgutil
from unittest.mock import MagicMock, Mock

import customtkinter as ctk
import pytest

import pywinhello.gui
from pywinhello.gui.app import _PicoConnection
from pywinhello.gui.settings import SettingsPanel
from pywinhello.gui.settings.advanced import AdvancedSettings
from pywinhello.gui.settings.apps import AppsSettings
from pywinhello.gui.settings.basic import BasicSettings, _PinChangeDialog
from pywinhello.gui.settings.log_view import LogView
from pywinhello.gui.settings.version_info import VersionInfo
from pywinhello.gui.wizard.step_pin import PinStep
from pywinhello.gui.wizard.step_schedule import ScheduleStep


def _gui_module_names() -> list[str]:
    names = []
    for module_info in pkgutil.walk_packages(pywinhello.gui.__path__, prefix="pywinhello.gui."):
        names.append(module_info.name)
    return names


@pytest.mark.parametrize("module_name", _gui_module_names())
def test_gui_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)


@pytest.fixture(scope="module")
def root():
    # Module-scoped: creating/tearing down a Tcl interpreter per test is flaky
    # on Windows. Tests isolate via fresh child widgets, not a fresh root.
    window = ctk.CTk()
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def pico() -> Mock:
    fake = Mock(spec=_PicoConnection)
    fake.protocol = Mock()
    return fake


@pytest.fixture
def run_threads_sync(monkeypatch: pytest.MonkeyPatch):
    """Make threading.Thread(...).start() run the target inline, synchronously."""

    class _SyncThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self) -> None:
            self._target(*self._args, **self._kwargs)

    monkeypatch.setattr("threading.Thread", _SyncThread)


class TestPicoConnectionProtocol:
    def test_protocol_raises_when_disconnected(self) -> None:
        connection = _PicoConnection()
        with pytest.raises(ConnectionError):
            _ = connection.protocol

    def test_protocol_returns_device_protocol_when_connected(self) -> None:
        connection = _PicoConnection()
        device = Mock()
        device.is_connected = True
        device.protocol = Mock()
        connection._device = device

        assert connection.protocol is device.protocol

    def test_send_command_shim_removed(self) -> None:
        assert not hasattr(_PicoConnection, "send_command")


class TestBasicSettingsUsesCoreServices:
    def test_save_schedule_calls_core_save_schedule(self, root, pico, run_threads_sync):
        panel = BasicSettings(root, {}, pico)

        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_save_schedule = Mock()
            monkeypatch.setattr("pywinhello.gui.settings.basic.save_schedule", mock_save_schedule)
            panel._on_save_schedule()

        mock_save_schedule.assert_called_once()
        protocol_arg = mock_save_schedule.call_args.args[0]
        assert protocol_arg is pico.protocol

    def test_pin_dialog_calls_core_register_pin(self, root, pico):
        dialog = _PinChangeDialog(root, pico)
        dialog.withdraw()
        dialog._pin_entry.insert(0, "1234")
        dialog._confirm_entry.insert(0, "1234")

        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_register_pin = Mock()
            monkeypatch.setattr("pywinhello.gui.settings.basic.register_pin", mock_register_pin)
            dialog._on_ok()

        mock_register_pin.assert_called_once_with(pico.protocol, "1234")
        assert dialog.success is True


class TestAppsSettingsUsesCoreServices:
    def test_toggle_change_calls_core_write_config(self, root, pico, run_threads_sync):
        panel = AppsSettings(root, {"apps": {"Chrome.exe": True}}, pico)

        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_write_config = Mock()
            monkeypatch.setattr("pywinhello.gui.settings.apps.write_config", mock_write_config)
            panel._on_toggle_changed()

        mock_write_config.assert_called_once()
        assert mock_write_config.call_args.args[0] is pico.protocol

    def test_toggle_change_surfaces_error(self, root, pico, run_threads_sync):
        # No bare except->pass: a raised RuntimeError must reach the status-label
        # configure() call (not be silently swallowed), even though save fails.
        panel = AppsSettings(root, {}, pico)
        error = RuntimeError("SET_CONFIG failed: boom")

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "pywinhello.gui.settings.apps.write_config", Mock(side_effect=error)
            )
            mock_after = Mock(wraps=panel.after)
            monkeypatch.setattr(panel, "after", mock_after)
            panel._on_toggle_changed()

        configure_calls = [
            call
            for call in mock_after.call_args_list
            if call.args[1] == panel._save_status.configure
        ]
        assert any("boom" in call.args[2]["text"] for call in configure_calls)


class TestAdvancedSettingsUsesCoreServices:
    def test_save_calls_core_write_config(self, root, pico, run_threads_sync):
        panel = AdvancedSettings(root, {}, pico)

        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_write_config = Mock()
            monkeypatch.setattr("pywinhello.gui.settings.advanced.write_config", mock_write_config)
            panel._on_save()

        mock_write_config.assert_called_once()
        assert mock_write_config.call_args.args[0] is pico.protocol


class TestLogViewUsesTypedProtocol:
    def test_refresh_calls_protocol_get_log(self, root, pico, run_threads_sync):
        pico.protocol.get_log.return_value = []
        LogView(root, pico)

        pico.protocol.get_log.assert_called_once()


class TestVersionInfoUsesCoreServices:
    def test_check_calls_core_check_for_update(self, root, pico, run_threads_sync):
        panel = VersionInfo(root, {}, pico)

        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_result = Mock(error=None, has_software_update=False, has_firmware_update=False)
            mock_check = Mock(return_value=mock_result)
            monkeypatch.setattr("pywinhello.gui.settings.version_info.check_for_update", mock_check)
            panel._on_check()

        mock_check.assert_called_once()

    def test_update_firmware_calls_core_apply_firmware_update(self, root, pico, run_threads_sync):
        panel = VersionInfo(root, {}, pico)

        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_apply = Mock(return_value=True)
            monkeypatch.setattr(
                "pywinhello.gui.settings.version_info.apply_firmware_update", mock_apply
            )
            panel._on_update_firmware()

        mock_apply.assert_called_once_with(pico.protocol)


class TestSettingsPanelUsesCoreServices:
    def test_load_config_calls_core_read_config(self, root, pico, run_threads_sync):
        pico.protocol = Mock()
        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_read_config = Mock(return_value={})
            monkeypatch.setattr("pywinhello.gui.settings.read_config", mock_read_config)
            SettingsPanel(root, pico)

        mock_read_config.assert_called_once_with(pico.protocol)

    def test_clear_calls_protocol_clear(self, root, pico, run_threads_sync):
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr("pywinhello.gui.settings.read_config", Mock(return_value={}))
            panel = SettingsPanel(root, pico)
        root.update()  # flush the after(0, self._build_sections, ...) that creates _action_status

        panel._do_clear()

        pico.protocol.clear.assert_called_once()


class _FakeWizard:
    def __init__(self, root: ctk.CTk, port: str = "COM8") -> None:
        self.content_frame = ctk.CTkFrame(root)
        self.nav_bar = Mock()
        self.collected_data = {"port": port}


class TestPinStepUsesCoreRegisterPin:
    def test_register_calls_core_register_pin(self, root, run_threads_sync):
        wizard = _FakeWizard(root)
        step = PinStep(wizard)
        step.build()
        step._pin_entry.insert(0, "1234")
        step._confirm_entry.insert(0, "1234")

        mock_protocol_cls = MagicMock()
        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_register_pin = Mock()
            monkeypatch.setattr("pywinhello.gui.wizard.step_pin.register_pin", mock_register_pin)
            monkeypatch.setattr("pywinhello.serial.protocol.SerialProtocol", mock_protocol_cls)
            step._on_register()

        mock_register_pin.assert_called_once()
        assert mock_register_pin.call_args.args[1] == "1234"


class TestScheduleStepUsesCoreSaveSchedule:
    def test_save_schedule_calls_core_save_schedule(self, root):
        wizard = _FakeWizard(root)
        step = ScheduleStep(wizard)
        step.build()

        mock_protocol_cls = MagicMock()
        with pytest.MonkeyPatch.context() as monkeypatch:
            mock_save_schedule = Mock()
            monkeypatch.setattr(
                "pywinhello.gui.wizard.step_schedule.save_schedule", mock_save_schedule
            )
            monkeypatch.setattr("pywinhello.serial.protocol.SerialProtocol", mock_protocol_cls)
            step._save_schedule()

        mock_save_schedule.assert_called_once()
        _, hour, minute, days = mock_save_schedule.call_args.args
        assert isinstance(hour, int)
        assert isinstance(minute, int)
        assert days == ["mon", "tue", "wed", "thu", "fri"]
