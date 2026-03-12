"""Auto-updater — checks GitHub Releases daily for software/firmware updates.

- Software update: download new exe, rename-on-restart pattern
- Firmware update: download .uf2, verify hash, flash via serial
- ETag caching to minimize API requests
- No telemetry — only the version check HTTP request
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from pywinhello.serial.protocol import SerialProtocol

logger = logging.getLogger(__name__)

_GITHUB_API_URL = "https://api.github.com/repos/obichan117/pywinhello/releases/latest"
_CHECK_INTERVAL_SEC = 86400  # 24 hours
_ETAG_CACHE_FILE = "pywinhello_update_etag.json"
_UPDATE_DIR = "pywinhello_updates"

# Current software version (read from package metadata at runtime)
_CURRENT_VERSION: str | None = None


def get_current_version() -> str:
    """Get the current installed software version."""
    global _CURRENT_VERSION
    if _CURRENT_VERSION is not None:
        return _CURRENT_VERSION

    try:
        from importlib.metadata import version

        _CURRENT_VERSION = version("pywinhello")
    except Exception:
        _CURRENT_VERSION = "0.0.0"
    return _CURRENT_VERSION


@dataclass(frozen=True)
class ReleaseManifest:
    """Parsed manifest.json from a GitHub release."""

    version: str
    software_version: str
    firmware_version: str
    firmware_hash_rp2040: str = ""
    firmware_hash_rp2350: str = ""
    changelog_en: str = ""
    changelog_ja: str = ""
    force_update: bool = False
    min_protocol_version: int = 2

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleaseManifest:
        """Parse from a manifest dict."""
        return cls(
            version=data.get("version", "0.0.0"),
            software_version=data.get("software_version", data.get("version", "0.0.0")),
            firmware_version=data.get("firmware_version", "0.0.0"),
            firmware_hash_rp2040=data.get("firmware_hash_rp2040", ""),
            firmware_hash_rp2350=data.get("firmware_hash_rp2350", ""),
            changelog_en=data.get("changelog_en", ""),
            changelog_ja=data.get("changelog_ja", ""),
            force_update=data.get("force_update", False),
            min_protocol_version=data.get("min_protocol_version", 2),
        )


@dataclass
class UpdateCheck:
    """Result of a version check against GitHub releases."""

    has_software_update: bool = False
    has_firmware_update: bool = False
    manifest: ReleaseManifest | None = None
    assets: dict[str, str] = field(default_factory=dict)
    """Map of asset filename -> download URL."""

    error: str | None = None


def _get_cache_dir() -> Path:
    """Get the cache directory for update state."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".cache"
    cache_dir = base / "pywinhello"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _load_etag() -> str | None:
    """Load cached ETag for conditional requests."""
    cache_file = _get_cache_dir() / _ETAG_CACHE_FILE
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        return data.get("etag")
    except Exception:
        return None


def _save_etag(etag: str) -> None:
    """Save ETag to cache file."""
    cache_file = _get_cache_dir() / _ETAG_CACHE_FILE
    try:
        cache_file.write_text(json.dumps({"etag": etag}))
    except Exception:
        logger.debug("Failed to save ETag cache")


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semver-like version strings.

    Returns:
        -1 if v1 < v2, 0 if equal, 1 if v1 > v2.
    """

    def parse(v: str) -> tuple[int, ...]:
        # Strip common prefixes
        v = v.lstrip("v").split("-")[0]
        parts = []
        for p in v.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        # Pad to 3 components
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)

    p1, p2 = parse(v1), parse(v2)
    if p1 < p2:
        return -1
    if p1 > p2:
        return 1
    return 0


def check_for_updates(
    current_sw_version: str | None = None,
    current_fw_version: str | None = None,
) -> UpdateCheck:
    """Check GitHub Releases API for available updates.

    Uses ETag caching to avoid rate limits (1 request/day is well within
    the 60/hour unauthenticated limit).

    Args:
        current_sw_version: Installed software version. None = auto-detect.
        current_fw_version: Pico firmware version. None = skip firmware check.

    Returns:
        UpdateCheck with results.
    """
    if current_sw_version is None:
        current_sw_version = get_current_version()

    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
    }

    # ETag for conditional request
    cached_etag = _load_etag()
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    try:
        resp = requests.get(_GITHUB_API_URL, headers=headers, timeout=10)
    except requests.RequestException as e:
        return UpdateCheck(error=f"Network error: {e}")

    if resp.status_code == 304:
        # Not modified — no new release since last check
        logger.debug("GitHub API returned 304 Not Modified")
        return UpdateCheck()

    if resp.status_code == 404:
        return UpdateCheck(error="No releases found")

    if resp.status_code != 200:
        return UpdateCheck(error=f"GitHub API error: {resp.status_code}")

    # Save new ETag
    etag = resp.headers.get("ETag")
    if etag:
        _save_etag(etag)

    try:
        release_data = resp.json()
    except ValueError:
        return UpdateCheck(error="Invalid JSON from GitHub API")

    # Find manifest.json in release assets
    assets: dict[str, str] = {}
    manifest_url: str | None = None
    for asset in release_data.get("assets", []):
        name = asset.get("name", "")
        url = asset.get("browser_download_url", "")
        assets[name] = url
        if name == "manifest.json":
            manifest_url = url

    if not manifest_url:
        return UpdateCheck(
            error="No manifest.json in release assets",
            assets=assets,
        )

    # Download and parse manifest
    try:
        manifest_resp = requests.get(manifest_url, timeout=10)
        manifest_resp.raise_for_status()
        manifest = ReleaseManifest.from_dict(manifest_resp.json())
    except Exception as e:
        return UpdateCheck(error=f"Failed to parse manifest: {e}", assets=assets)

    # Compare versions
    has_sw_update = compare_versions(current_sw_version, manifest.software_version) < 0
    has_fw_update = False
    if current_fw_version is not None:
        has_fw_update = compare_versions(current_fw_version, manifest.firmware_version) < 0

    return UpdateCheck(
        has_software_update=has_sw_update,
        has_firmware_update=has_fw_update,
        manifest=manifest,
        assets=assets,
    )


def download_asset(url: str, dest: Path) -> bool:
    """Download a release asset to a local path.

    Args:
        url: Download URL for the asset.
        dest: Local file path to save to.

    Returns:
        True if download succeeded.
    """
    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("Downloaded %s -> %s", url.rsplit("/", 1)[-1], dest)
        return True
    except Exception as e:
        logger.error("Download failed: %s", e)
        return False


def apply_software_update(new_exe_path: Path) -> bool:
    """Stage a software update for rename-on-restart.

    Saves the new exe as ``<current>.new``. On next startup,
    ``cleanup_old_update()`` renames files.

    Args:
        new_exe_path: Path to the downloaded new executable.

    Returns:
        True if staging succeeded.
    """
    if not getattr(sys, "frozen", False):
        logger.warning("Software self-update only works in PyInstaller builds")
        return False

    current_exe = Path(sys.executable)
    staged_path = current_exe.with_suffix(".exe.new")

    try:
        shutil.copy2(new_exe_path, staged_path)
        logger.info("Staged software update: %s", staged_path)
        return True
    except Exception as e:
        logger.error("Failed to stage software update: %s", e)
        return False


def cleanup_old_update() -> None:
    """Apply pending rename-on-restart update and clean up old files.

    Called on startup. Performs the rename dance:
    1. If ``.exe.new`` exists: rename ``.exe`` -> ``.exe.old``, ``.exe.new`` -> ``.exe``
    2. If ``.exe.old`` exists: delete it
    """
    if not getattr(sys, "frozen", False):
        return

    current_exe = Path(sys.executable)
    old_path = current_exe.with_suffix(".exe.old")
    new_path = current_exe.with_suffix(".exe.new")

    # Clean up old version
    if old_path.exists():
        try:
            old_path.unlink()
            logger.info("Cleaned up old version: %s", old_path)
        except Exception:
            logger.debug("Could not delete old version (may still be locked)")

    # Apply staged update
    if new_path.exists():
        try:
            if current_exe.exists():
                current_exe.rename(old_path)
            new_path.rename(current_exe)
            logger.info("Applied software update: %s", current_exe)
        except Exception as e:
            logger.error("Failed to apply update: %s", e)


def apply_firmware_update(
    protocol: SerialProtocol,
    firmware_path: Path,
    expected_hash: str | None = None,
    expected_version: str | None = None,
) -> bool:
    """Flash firmware update to Pico via serial.

    Args:
        protocol: Connected SerialProtocol instance.
        firmware_path: Path to the downloaded firmware file.
        expected_hash: Expected SHA-256 hash.
        expected_version: Expected firmware version after reboot.

    Returns:
        True if the flash succeeded and version was verified.
    """
    from pywinhello.serial.flasher import flash_and_verify

    result = flash_and_verify(
        protocol,
        firmware_path,
        expected_hash=expected_hash,
        expected_version=expected_version,
    )

    if result.success:
        logger.info("Firmware updated successfully: %s", firmware_path.name)
    else:
        logger.error("Firmware update failed: %s", result.error)

    return result.success


class AutoUpdater:
    """Background auto-updater that checks GitHub daily.

    Usage::

        updater = AutoUpdater(protocol=device.protocol, device_type="rp2040")
        updater.start()
        # ... checks daily in background ...
        updater.stop()
    """

    def __init__(
        self,
        protocol: SerialProtocol | None = None,
        device_type: str | None = None,
        firmware_version: str | None = None,
        check_interval: float = _CHECK_INTERVAL_SEC,
    ) -> None:
        self._protocol = protocol
        self._device_type = device_type
        self._firmware_version = firmware_version
        self._check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """Whether the updater thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the auto-update check loop."""
        if self.is_running:
            return

        # Clean up any pending updates from previous session
        cleanup_old_update()

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._check_loop,
            name="auto-updater",
            daemon=True,
        )
        self._thread.start()
        logger.info("AutoUpdater started (interval=%ds)", self._check_interval)

    def stop(self) -> None:
        """Stop the auto-update loop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None

    def check_once(self) -> UpdateCheck:
        """Perform a single update check (blocking)."""
        return check_for_updates(
            current_fw_version=self._firmware_version,
        )

    def _check_loop(self) -> None:
        """Background loop: check on startup, then every check_interval."""
        # Initial check
        self._do_check()

        while not self._stop_event.is_set():
            self._stop_event.wait(self._check_interval)
            if not self._stop_event.is_set():
                self._do_check()

    def _do_check(self) -> None:
        """Perform update check and apply if available."""
        try:
            result = self.check_once()

            if result.error:
                logger.debug("Update check: %s", result.error)
                return

            if result.has_software_update and result.manifest:
                logger.info(
                    "Software update available: %s -> %s",
                    get_current_version(),
                    result.manifest.software_version,
                )
                self._apply_software(result)

            if result.has_firmware_update and result.manifest and self._protocol:
                logger.info(
                    "Firmware update available: %s -> %s",
                    self._firmware_version,
                    result.manifest.firmware_version,
                )
                self._apply_firmware(result)

        except Exception:
            logger.exception("Update check failed")

    def _apply_software(self, result: UpdateCheck) -> None:
        """Download and stage a software update."""
        # Find the exe asset
        exe_name = "pywinhello-monitor.exe"
        if exe_name not in result.assets:
            logger.debug("No %s in release assets", exe_name)
            return

        dest = _get_cache_dir() / _UPDATE_DIR / exe_name
        if download_asset(result.assets[exe_name], dest):
            apply_software_update(dest)

    def _apply_firmware(self, result: UpdateCheck) -> None:
        """Download and flash a firmware update."""
        if not self._protocol or not self._device_type or not result.manifest:
            return

        # Pick the right firmware file and hash
        fw_name = f"firmware_{self._device_type}.uf2"
        if fw_name not in result.assets:
            logger.debug("No %s in release assets", fw_name)
            return

        if self._device_type == "rp2040":
            expected_hash = result.manifest.firmware_hash_rp2040
        elif self._device_type == "rp2350":
            expected_hash = result.manifest.firmware_hash_rp2350
        else:
            expected_hash = None

        dest = _get_cache_dir() / _UPDATE_DIR / fw_name
        if download_asset(result.assets[fw_name], dest):
            apply_firmware_update(
                self._protocol,
                dest,
                expected_hash=expected_hash or None,
                expected_version=result.manifest.firmware_version,
            )
