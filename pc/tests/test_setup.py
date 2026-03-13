"""Tests for setup module — detect, bootsel, firmware, provision."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pywinhello.models import BoardVariant
from pywinhello.setup import BUNDLED_FW_VERSION, ProvisionResult, provision
from pywinhello.setup.bootsel import flash_uf2, parse_board_info
from pywinhello.setup.detect import DetectedDevice, DeviceState, detect  # noqa: E501
from pywinhello.setup.firmware import get_firmware_path, list_bundled_firmware  # noqa: E501

# --- TestDetect ---


class TestDetect:
    @patch("pywinhello.setup.detect._detect_serial", return_value=None)
    @patch("pywinhello.setup.detect._detect_bootsel", return_value=None)
    def test_not_found(self, mock_bootsel, mock_serial):
        result = detect()
        assert result.state == DeviceState.NOT_FOUND

    @patch("pywinhello.setup.detect._detect_serial")
    @patch("pywinhello.setup.detect._detect_bootsel")
    def test_bootsel_takes_priority(self, mock_bootsel, mock_serial):
        bootsel_device = DetectedDevice(
            state=DeviceState.BOOTSEL,
            board=BoardVariant.PICO_W,
            drive="E:/",
        )
        mock_bootsel.return_value = bootsel_device
        mock_serial.return_value = None

        result = detect()
        assert result.state == DeviceState.BOOTSEL
        assert result.board == BoardVariant.PICO_W
        mock_serial.assert_not_called()

    @patch("pywinhello.setup.detect._detect_serial")
    @patch("pywinhello.setup.detect._detect_bootsel")
    def test_serial_running(self, mock_bootsel, mock_serial):
        mock_bootsel.return_value = None
        serial_device = DetectedDevice(
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_2_W,
            port="COM8",
            firmware_version="1.0.0",
        )
        mock_serial.return_value = serial_device

        result = detect()
        assert result.state == DeviceState.RUNNING_PYWINHELLO
        assert result.firmware_version == "1.0.0"

    @patch("pywinhello.setup.detect._detect_serial")
    @patch("pywinhello.setup.detect._detect_bootsel")
    def test_unknown_firmware(self, mock_bootsel, mock_serial):
        mock_bootsel.return_value = None
        mock_serial.return_value = DetectedDevice(
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=BoardVariant.PICO,
            port="COM3",
        )

        result = detect()
        assert result.state == DeviceState.UNKNOWN_FIRMWARE


# --- TestBootsel ---


class TestBootsel:
    def test_parse_board_info_pico(self, tmp_path):
        info = tmp_path / "INFO_UF2.TXT"
        info.write_text("Model: Raspberry Pi Pico\nBoard-ID: RPI-RP2\nChip: RP2040\n")
        assert parse_board_info(tmp_path) == BoardVariant.PICO

    def test_parse_board_info_pico_w(self, tmp_path):
        info = tmp_path / "INFO_UF2.TXT"
        info.write_text("Model: Raspberry Pi Pico W\nBoard-ID: RPI-RP2\nChip: RP2040\n")
        assert parse_board_info(tmp_path) == BoardVariant.PICO_W

    def test_parse_board_info_pico_2(self, tmp_path):
        info = tmp_path / "INFO_UF2.TXT"
        info.write_text("Model: Raspberry Pi Pico 2\nBoard-ID: RPI-RP2\nChip: RP2350\n")
        assert parse_board_info(tmp_path) == BoardVariant.PICO_2

    def test_parse_board_info_pico_2_w(self, tmp_path):
        info = tmp_path / "INFO_UF2.TXT"
        info.write_text("Model: Raspberry Pi Pico 2 W\nBoard-ID: RPI-RP2\nChip: RP2350\n")
        assert parse_board_info(tmp_path) == BoardVariant.PICO_2_W

    def test_parse_board_info_missing_file(self, tmp_path):
        assert parse_board_info(tmp_path) is None

    def test_flash_uf2_copies_file(self, tmp_path):
        fw = tmp_path / "firmware.uf2"
        fw.write_bytes(b"\x00" * 1024)
        drive = tmp_path / "drive"
        drive.mkdir()

        result = flash_uf2(drive, fw, wait_reboot=False)
        assert result is True
        assert (drive / "firmware.uf2").exists()

    def test_flash_uf2_missing_firmware(self, tmp_path):
        drive = tmp_path / "drive"
        drive.mkdir()
        with pytest.raises(FileNotFoundError):
            flash_uf2(drive, tmp_path / "missing.uf2")


# --- TestFirmware ---


class TestFirmware:
    def test_get_firmware_path_explicit_dir(self, tmp_path):
        fw = tmp_path / "pywinhello_pico_w.uf2"
        fw.write_bytes(b"\x00")

        result = get_firmware_path(BoardVariant.PICO_W, search_dir=tmp_path)
        assert result == fw

    def test_get_firmware_path_not_found(self, tmp_path):
        result = get_firmware_path(BoardVariant.PICO_2, search_dir=tmp_path)
        assert result is None

    def test_get_firmware_path_variant_naming(self, tmp_path):
        for variant in BoardVariant:
            fw = tmp_path / f"pywinhello_{variant.value}.uf2"
            fw.write_bytes(b"\x00")

        for variant in BoardVariant:
            result = get_firmware_path(variant, search_dir=tmp_path)
            assert result is not None
            assert variant.value in result.name

    def test_list_bundled_firmware_empty(self, tmp_path):
        # With no firmware files anywhere, should return empty
        with patch(
            "pywinhello.setup.firmware.get_firmware_path",
            return_value=None,
        ):
            result = list_bundled_firmware()
            assert result == {}


# --- TestNeedsUpdate ---


class TestNeedsUpdate:
    def test_none_version(self):
        from pywinhello.setup import _needs_update

        assert _needs_update(None) is True

    def test_zero_version(self):
        from pywinhello.setup import _needs_update

        assert _needs_update("0.0.0") is True

    def test_same_version(self):
        from pywinhello.setup import _needs_update

        assert _needs_update(BUNDLED_FW_VERSION) is False

    def test_older_version(self):
        from pywinhello.setup import _needs_update

        assert _needs_update("0.9.0") is True

    def test_newer_version(self):
        from pywinhello.setup import _needs_update

        assert _needs_update("99.0.0") is False

    def test_invalid_version(self):
        from pywinhello.setup import _needs_update

        assert _needs_update("invalid") is True


# --- TestProvision ---


class TestProvision:
    @patch("pywinhello.setup.detect")
    def test_provision_not_found(self, mock_detect_fn):
        mock_detect_fn.return_value = DetectedDevice(state=DeviceState.NOT_FOUND)

        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert not result.success
        assert result.state == DeviceState.NOT_FOUND

    @patch("pywinhello.setup.detect")
    @patch("pywinhello.setup._reboot_and_flash_uf2")
    def test_provision_unknown_firmware_tries_reboot(
        self, mock_reboot, mock_detect_fn
    ):
        mock_detect_fn.return_value = DetectedDevice(
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=BoardVariant.PICO,
            port="COM3",
        )
        mock_reboot.return_value = ProvisionResult(
            success=False,
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=BoardVariant.PICO,
            message="REBOOT failed",
        )


        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        # Should have tried REBOOT before giving up
        mock_reboot.assert_called_once()
        assert not result.success
        assert "BOOTSEL" in result.message

    @patch("pywinhello.setup.detect")
    def test_provision_already_up_to_date(self, mock_detect_fn):
        mock_detect_fn.return_value = DetectedDevice(
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_W,
            port="COM8",
            firmware_version=BUNDLED_FW_VERSION,
        )

        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert result.success
        assert result.firmware_version == BUNDLED_FW_VERSION

    @patch("pywinhello.setup.detect")
    @patch("pywinhello.setup._ota_update")
    def test_provision_outdated_triggers_ota(self, mock_ota, mock_detect_fn):
        mock_detect_fn.return_value = DetectedDevice(
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_W,
            port="COM8",
            firmware_version="0.9.0",
        )
        mock_ota.return_value = ProvisionResult(
            success=True,
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_W,
            firmware_version=BUNDLED_FW_VERSION,
            message="Updated.",
        )


        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert result.success
        mock_ota.assert_called_once()

    @patch("pywinhello.setup.detect")
    @patch("pywinhello.setup._reboot_and_flash_uf2")
    @patch("pywinhello.setup._ota_update")
    def test_provision_ota_fails_falls_back_to_reboot(
        self, mock_ota, mock_reboot, mock_detect_fn
    ):
        mock_detect_fn.return_value = DetectedDevice(
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_W,
            port="COM8",
            firmware_version="0.9.0",
        )
        mock_ota.return_value = ProvisionResult(
            success=False,
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_W,
            message="OTA failed",
        )
        mock_reboot.return_value = ProvisionResult(
            success=True,
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_W,
            firmware_version=BUNDLED_FW_VERSION,
            message="Flashed via REBOOT.",
        )


        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert result.success
        mock_ota.assert_called_once()
        mock_reboot.assert_called_once()

    @patch("pywinhello.setup.detect")
    @patch("pywinhello.setup.flash_uf2")
    @patch("pywinhello.setup.get_firmware_path")
    def test_provision_bootsel_flash_and_verify(
        self, mock_fw_path, mock_flash, mock_detect_fn
    ):
        # First detect: BOOTSEL, second detect (verify): running
        mock_detect_fn.side_effect = [
            DetectedDevice(
                state=DeviceState.BOOTSEL,
                board=BoardVariant.PICO_W,
                drive="E:/",
            ),
            DetectedDevice(
                state=DeviceState.RUNNING_PYWINHELLO,
                board=BoardVariant.PICO_W,
                port="COM8",
                firmware_version="1.0.0",
            ),
        ]
        mock_fw_path.return_value = Path("/fake/pywinhello_pico_w.uf2")
        mock_flash.return_value = True

        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert result.success
        assert result.firmware_version == "1.0.0"
        mock_flash.assert_called_once()

    @patch("pywinhello.setup.detect")
    @patch("pywinhello.setup.get_firmware_path")
    def test_provision_bootsel_no_firmware(self, mock_fw_path, mock_detect_fn):
        mock_detect_fn.return_value = DetectedDevice(
            state=DeviceState.BOOTSEL,
            board=BoardVariant.PICO_2,
            drive="E:/",
        )
        mock_fw_path.return_value = None

        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert not result.success
        assert "No firmware" in result.message

    @patch("pywinhello.setup.detect")
    @patch("pywinhello.setup._reboot_and_flash_uf2")
    def test_provision_unknown_firmware_reboot_succeeds(
        self, mock_reboot, mock_detect_fn
    ):
        mock_detect_fn.return_value = DetectedDevice(
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=BoardVariant.PICO_W,
            port="COM3",
        )
        mock_reboot.return_value = ProvisionResult(
            success=True,
            state=DeviceState.RUNNING_PYWINHELLO,
            board=BoardVariant.PICO_W,
            firmware_version=BUNDLED_FW_VERSION,
            message="Success!",
        )


        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert result.success
        mock_reboot.assert_called_once()

    @patch("pywinhello.setup.detect")
    def test_provision_unknown_firmware_no_board(self, mock_detect_fn):
        """Unknown firmware with no board detected — can't try REBOOT."""
        mock_detect_fn.return_value = DetectedDevice(
            state=DeviceState.UNKNOWN_FIRMWARE,
            board=None,
            port="COM3",
        )

        with patch("pywinhello.setup.detect", mock_detect_fn):
            result = provision()

        assert not result.success
        assert "BOOTSEL" in result.message
