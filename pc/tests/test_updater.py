"""Tests for GitHub API parsing, version comparison, and update logic."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch


from pywinhello.monitor.updater import (
    AutoUpdater,
    ReleaseManifest,
    UpdateCheck,
    apply_software_update,
    cleanup_old_update,
    compare_versions,
    check_for_updates,
)


class TestCompareVersions:
    def test_equal(self):
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_less_than(self):
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_greater_than(self):
        assert compare_versions("1.0.1", "1.0.0") == 1
        assert compare_versions("2.0.0", "1.9.9") == 1

    def test_with_v_prefix(self):
        assert compare_versions("v1.0.0", "1.0.0") == 0
        assert compare_versions("v1.0.0", "v1.0.1") == -1

    def test_with_prerelease(self):
        # Pre-release suffix is stripped
        assert compare_versions("1.0.0-dev", "1.0.0") == 0
        assert compare_versions("1.0.0-beta", "1.0.1") == -1

    def test_short_versions(self):
        assert compare_versions("1.0", "1.0.0") == 0
        assert compare_versions("1", "1.0.0") == 0

    def test_different_lengths(self):
        assert compare_versions("1.0.0", "1.0") == 0
        assert compare_versions("1.1", "1.0.9") == 1


class TestReleaseManifest:
    def test_from_dict(self):
        data = {
            "version": "1.2.0",
            "software_version": "1.2.0",
            "firmware_version": "1.1.0",
            "firmware_hash_rp2040": "sha256:abc123",
            "firmware_hash_rp2350": "sha256:def456",
            "changelog_en": "Bug fixes",
            "force_update": False,
            "min_protocol_version": 2,
        }
        m = ReleaseManifest.from_dict(data)
        assert m.software_version == "1.2.0"
        assert m.firmware_version == "1.1.0"
        assert m.firmware_hash_rp2040 == "sha256:abc123"
        assert m.force_update is False

    def test_from_dict_minimal(self):
        m = ReleaseManifest.from_dict({})
        assert m.version == "0.0.0"
        assert m.software_version == "0.0.0"

    def test_from_dict_version_fallback(self):
        """software_version falls back to version field."""
        m = ReleaseManifest.from_dict({"version": "2.0.0"})
        assert m.software_version == "2.0.0"


def _mock_urlopen(release_data, manifest_data=None):
    """Helper to create mock responses for urllib.request.urlopen."""
    responses = []

    # First call: GitHub API release
    release_resp = MagicMock()
    release_resp.status = 200
    release_resp.headers = MagicMock()
    release_resp.headers.get = lambda key, default=None: {
        "ETag": '"abc123"',
    }.get(key, default)
    release_resp.read.return_value = json.dumps(release_data).encode()
    responses.append(release_resp)

    # Second call: manifest download
    if manifest_data is not None:
        manifest_resp = MagicMock()
        manifest_resp.read.return_value = json.dumps(manifest_data).encode()
        responses.append(manifest_resp)

    return responses


class TestCheckForUpdates:
    @patch("pywinhello.monitor.updater.urllib.request.urlopen")
    @patch("pywinhello.monitor.updater._load_etag", return_value=None)
    @patch("pywinhello.monitor.updater._save_etag")
    def test_update_available(self, mock_save, mock_load, mock_urlopen):
        manifest_data = {
            "version": "2.0.0",
            "software_version": "2.0.0",
            "firmware_version": "1.5.0",
        }
        release_data = {
            "assets": [
                {
                    "name": "manifest.json",
                    "browser_download_url": "https://example.com/manifest.json",
                },
                {
                    "name": "pywinhello-monitor.exe",
                    "browser_download_url": "https://example.com/monitor.exe",
                },
            ]
        }

        mock_urlopen.side_effect = _mock_urlopen(release_data, manifest_data)

        result = check_for_updates(
            current_sw_version="1.0.0",
            current_fw_version="1.0.0",
        )

        assert result.has_software_update is True
        assert result.has_firmware_update is True
        assert result.manifest is not None
        assert result.manifest.software_version == "2.0.0"
        assert "manifest.json" in result.assets

    @patch("pywinhello.monitor.updater.urllib.request.urlopen")
    @patch("pywinhello.monitor.updater._load_etag", return_value='"old_etag"')
    def test_not_modified(self, mock_load, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=304, msg="Not Modified", hdrs=None, fp=None
        )

        result = check_for_updates(current_sw_version="1.0.0")
        assert result.has_software_update is False
        assert result.error is None

    @patch("pywinhello.monitor.updater.urllib.request.urlopen")
    @patch("pywinhello.monitor.updater._load_etag", return_value=None)
    def test_network_error(self, mock_load, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection timeout")

        result = check_for_updates(current_sw_version="1.0.0")
        assert result.error is not None

    @patch("pywinhello.monitor.updater.urllib.request.urlopen")
    @patch("pywinhello.monitor.updater._load_etag", return_value=None)
    @patch("pywinhello.monitor.updater._save_etag")
    def test_no_manifest_in_assets(self, mock_save, mock_load, mock_urlopen):
        release_data = {
            "assets": [{"name": "README.md", "browser_download_url": "..."}]
        }
        mock_urlopen.side_effect = _mock_urlopen(release_data)

        result = check_for_updates(current_sw_version="1.0.0")
        assert result.error is not None
        assert "manifest" in result.error.lower()

    @patch("pywinhello.monitor.updater.urllib.request.urlopen")
    @patch("pywinhello.monitor.updater._load_etag", return_value=None)
    @patch("pywinhello.monitor.updater._save_etag")
    def test_no_firmware_check_when_version_none(self, mock_save, mock_load, mock_urlopen):
        manifest_data = {
            "software_version": "2.0.0",
            "firmware_version": "1.5.0",
        }
        release_data = {
            "assets": [
                {"name": "manifest.json", "browser_download_url": "https://x/m.json"},
            ]
        }
        mock_urlopen.side_effect = _mock_urlopen(release_data, manifest_data)

        result = check_for_updates(
            current_sw_version="1.0.0",
            current_fw_version=None,
        )
        assert result.has_firmware_update is False  # Not checked

    @patch("pywinhello.monitor.updater.urllib.request.urlopen")
    @patch("pywinhello.monitor.updater._load_etag", return_value=None)
    def test_404_response(self, mock_load, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=None
        )

        result = check_for_updates(current_sw_version="1.0.0")
        assert result.error is not None
        assert "No releases" in result.error

    @patch("pywinhello.monitor.updater.urllib.request.urlopen")
    @patch("pywinhello.monitor.updater._load_etag", return_value=None)
    @patch("pywinhello.monitor.updater._save_etag")
    def test_already_up_to_date(self, mock_save, mock_load, mock_urlopen):
        manifest_data = {
            "software_version": "1.0.0",
            "firmware_version": "1.0.0",
        }
        release_data = {
            "assets": [
                {"name": "manifest.json", "browser_download_url": "https://x/m.json"},
            ]
        }
        mock_urlopen.side_effect = _mock_urlopen(release_data, manifest_data)

        result = check_for_updates(
            current_sw_version="1.0.0",
            current_fw_version="1.0.0",
        )
        assert result.has_software_update is False
        assert result.has_firmware_update is False


class TestApplySoftwareUpdate:
    @patch("pywinhello.monitor.updater.sys")
    def test_not_frozen_skips(self, mock_sys):
        mock_sys.frozen = False
        result = apply_software_update(Path("/tmp/new.exe"))
        assert result is False

    @patch("pywinhello.monitor.updater.shutil")
    @patch("pywinhello.monitor.updater.sys")
    def test_frozen_stages_update(self, mock_sys, mock_shutil):
        mock_sys.frozen = True
        mock_sys.executable = "C:\\path\\pywinhello-monitor.exe"

        result = apply_software_update(Path("C:\\tmp\\new.exe"))
        assert result is True
        mock_shutil.copy2.assert_called_once()


class TestCleanupOldUpdate:
    @patch("pywinhello.monitor.updater.sys")
    def test_not_frozen_noop(self, mock_sys):
        mock_sys.frozen = False
        cleanup_old_update()  # Should not raise


class TestAutoUpdater:
    def test_check_once(self):
        updater = AutoUpdater(firmware_version="1.0.0")

        with patch("pywinhello.monitor.updater.check_for_updates") as mock_check:
            mock_check.return_value = UpdateCheck()
            updater.check_once()
            mock_check.assert_called_once_with(current_fw_version="1.0.0")

    def test_start_stop(self):
        updater = AutoUpdater(check_interval=0.05)

        with patch("pywinhello.monitor.updater.check_for_updates") as mock_check:
            with patch("pywinhello.monitor.updater.cleanup_old_update"):
                mock_check.return_value = UpdateCheck()
                updater.start()
                assert updater.is_running
                updater.stop()
                assert not updater.is_running

    def test_initial_state(self):
        updater = AutoUpdater()
        assert not updater.is_running
