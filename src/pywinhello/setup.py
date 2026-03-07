"""Pico HID bridge setup — flash CircuitPython and firmware to a connected Pico.

Automates the full setup:
  1. Detect RPI-RP2 bootloader drive (or CIRCUITPY if already flashed)
  2. Flash CircuitPython UF2 onto the Pico (if in bootloader mode)
  3. Download adafruit_hid library from the CircuitPython bundle
  4. Copy boot.py + code.py firmware to the drive
  5. Verify the device responds to PING

Supports: Pico, Pico W, Pico 2, Pico 2 W.
"""

from __future__ import annotations

import importlib.resources
import io
import logging
import platform
import shutil
import time
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

# CircuitPython bundle URL template
_BUNDLE_URL = (
    "https://github.com/adafruit/Adafruit_CircuitPython_Bundle/"
    "releases/download/{tag}/adafruit-circuitpython-bundle-9.x-mpy-{tag}.zip"
)
_BUNDLE_TAG_LATEST_API = (
    "https://api.github.com/repos/adafruit/Adafruit_CircuitPython_Bundle/releases/latest"
)

# CircuitPython UF2 download — board_id → circuitpython.org board slug
BOARD_SLUGS = {
    "pico": "raspberry_pi_pico",
    "pico_w": "raspberry_pi_pico_w",
    "pico2": "raspberry_pi_pico2",
    "pico2_w": "raspberry_pi_pico2_w",
}

# INFO_UF2.TXT board ID strings → our board keys
_UF2_BOARD_IDS = {
    "RPI-RP2": "pico",       # Pico or Pico W (RP2040) — can't distinguish
    "RP2350": "pico2",       # Pico 2 or Pico 2 W (RP2350) — can't distinguish
}

# CircuitPython S3 download URL pattern
_CIRCUITPY_S3_PATTERN = (
    "https://downloads.circuitpython.org/bin/{slug}/en_US/"
    "adafruit-circuitpython-{slug}-en_US-{version}.uf2"
)
_CIRCUITPY_LATEST_API = (
    "https://api.github.com/repos/adafruit/circuitpython/releases/latest"
)


def _firmware_dir() -> Path:
    """Locate firmware files via importlib.resources (works from pip install)."""
    ref = importlib.resources.files("pywinhello._data.firmware")
    # files() returns a Traversable; for Path we need as_file or resolve
    boot = ref / "boot.py"
    # If running from source, this is already a real path
    if hasattr(boot, "_path"):
        return Path(boot._path).parent
    # Installed package — resolve to actual filesystem path
    path = Path(str(boot)).parent
    if path.exists():
        return path
    raise FileNotFoundError(
        "Firmware files (boot.py, code.py) not found in package data."
    )


# ---------------------------------------------------------------------------
# Drive detection
# ---------------------------------------------------------------------------

def _find_windows_drive_by_label(label: str) -> Path | None:
    """Find a removable drive on Windows by volume label."""
    import ctypes

    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    buf = ctypes.create_unicode_buffer(256)
    for i in range(26):
        if bitmask & (1 << i):
            drive = f"{chr(65 + i)}:\\"
            result = ctypes.windll.kernel32.GetVolumeInformationW(
                drive, buf, 256, None, None, None, None, 0
            )
            if result and buf.value == label:
                return Path(drive)
    return None


def find_rpi_rp2_drive() -> Path | None:
    """Find the RPI-RP2 bootloader drive (Pico in BOOTSEL mode)."""
    if platform.system() == "Windows":
        return _find_windows_drive_by_label("RPI-RP2")
    else:
        for candidate in [
            Path("/Volumes/RPI-RP2"),
            *Path("/media").glob("*/RPI-RP2"),
            *Path("/run/media").glob("*/RPI-RP2"),
        ]:
            if candidate.is_dir():
                return candidate
    return None


def find_circuitpy_drive() -> Path | None:
    """Find the CIRCUITPY drive on Windows or macOS/Linux."""
    if platform.system() == "Windows":
        import ctypes

        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                drive = f"{chr(65 + i)}:\\"
                label_path = Path(drive) / "boot_out.txt"
                if label_path.exists():
                    content = label_path.read_text(errors="ignore")
                    if "CircuitPython" in content:
                        return Path(drive)
    else:
        for candidate in [
            Path("/Volumes/CIRCUITPY"),
            *Path("/media").glob("*/CIRCUITPY"),
            *Path("/run/media").glob("*/CIRCUITPY"),
        ]:
            if candidate.is_dir():
                return candidate

    return None


# ---------------------------------------------------------------------------
# Board detection from bootloader
# ---------------------------------------------------------------------------

def detect_board_from_rpi_drive(drive: Path) -> str | None:
    """Read INFO_UF2.TXT from the RPI-RP2 drive to identify the board family.

    Returns a board key like "pico" or "pico2", or None if unrecognized.
    Note: cannot distinguish W vs non-W variants from bootloader info alone.
    """
    info_file = drive / "INFO_UF2.TXT"
    if not info_file.exists():
        return None

    content = info_file.read_text(errors="ignore")
    for line in content.splitlines():
        if line.startswith("Board-ID:"):
            board_id = line.split(":", 1)[1].strip()
            return _UF2_BOARD_IDS.get(board_id)

    # Fallback: check Model line
    for line in content.splitlines():
        if "RP2350" in line:
            return "pico2"
        if "RP2040" in line or "Pico" in line:
            return "pico"

    return None


# ---------------------------------------------------------------------------
# CircuitPython UF2 download and flash
# ---------------------------------------------------------------------------

def _get_latest_circuitpython_version() -> str:
    """Fetch the latest stable CircuitPython release version."""
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        _CIRCUITPY_LATEST_API,
        headers={"Accept": "application/vnd.github.v3+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data["tag_name"]
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot reach GitHub API to check CircuitPython version.\n"
            f"  Check your internet connection.\n"
            f"  Details: {e}"
        ) from e


def download_circuitpython_uf2(board: str) -> bytes:
    """Download the CircuitPython UF2 for the given board.

    Args:
        board: Board key (e.g. "pico_w", "pico2"). Must be in BOARD_SLUGS.

    Returns:
        Raw UF2 file bytes.
    """
    import urllib.error
    import urllib.request

    slug = BOARD_SLUGS.get(board)
    if not slug:
        raise ValueError(f"Unknown board: {board!r}. Choose from: {list(BOARD_SLUGS)}")

    print("  Fetching latest CircuitPython version...")
    version = _get_latest_circuitpython_version()
    print(f"  Latest version: {version}")

    url = _CIRCUITPY_S3_PATTERN.format(slug=slug, version=version)
    print(f"  Downloading UF2 for {board} ({slug})...")

    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(
                f"UF2 not found for board '{board}' version {version}.\n"
                f"  The board name or version may be wrong.\n"
                f"  Try specifying the board manually: --board pico_w"
            ) from e
        raise ConnectionError(f"HTTP {e.code} downloading UF2: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot download UF2 — check your internet connection.\n"
            f"  Details: {e}"
        ) from e

    if len(data) < 1024:
        raise RuntimeError(
            f"Downloaded file is suspiciously small ({len(data)} bytes)."
        )

    print(f"  Downloaded {len(data) / 1024:.0f} KB")
    return data


def flash_circuitpython(
    rpi_drive: Path,
    uf2_data: bytes,
    auto_wait_timeout: float = 15.0,
) -> Path:
    """Copy UF2 to RPI-RP2 drive and wait for CIRCUITPY to appear.

    Args:
        rpi_drive: Path to the RPI-RP2 bootloader drive.
        uf2_data: Raw UF2 file content.
        auto_wait_timeout: Seconds to auto-wait before prompting user to replug.

    Returns:
        Path to the CIRCUITPY drive.
    """
    uf2_path = rpi_drive / "firmware.uf2"
    print(f"  Writing UF2 to {uf2_path} ({len(uf2_data) / 1024:.0f} KB)...")
    try:
        uf2_path.write_bytes(uf2_data)
    except OSError as e:
        raise OSError(
            f"Failed to write UF2 to {uf2_path}: {e}\n"
            f"  Make sure the RPI-RP2 drive is still connected."
        ) from e

    print("  UF2 copied. Pico is rebooting into CircuitPython...")
    print("  Waiting for CIRCUITPY drive...")

    start = time.monotonic()
    while time.monotonic() - start < auto_wait_timeout:
        time.sleep(1)
        drive = find_circuitpy_drive()
        if drive is not None:
            elapsed = time.monotonic() - start
            print(f"  CIRCUITPY detected at {drive} (took {elapsed:.1f}s)")
            return drive

    print()
    print("  CIRCUITPY drive not detected yet.")
    print("  Please UNPLUG the Pico, wait 2 seconds, then PLUG IT BACK IN.")
    input("  Press Enter after re-plugging... ")

    print("  Waiting for CIRCUITPY drive...")
    start = time.monotonic()
    while time.monotonic() - start < 30.0:
        time.sleep(1)
        drive = find_circuitpy_drive()
        if drive is not None:
            elapsed = time.monotonic() - start
            print(f"  CIRCUITPY detected at {drive} (took {elapsed:.1f}s)")
            return drive

    raise TimeoutError(
        "CIRCUITPY drive did not appear after re-plugging.\n"
        "Try unplugging, waiting 5 seconds, re-plugging, then run:\n"
        "  pywinhello setup-pico"
    )


# ---------------------------------------------------------------------------
# Bundle download
# ---------------------------------------------------------------------------

def _get_latest_bundle_tag() -> str:
    """Fetch the latest release tag from GitHub."""
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        _BUNDLE_TAG_LATEST_API,
        headers={"Accept": "application/vnd.github.v3+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data["tag_name"]
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot reach GitHub API to check bundle version.\n"
            f"  Details: {e}"
        ) from e


def download_adafruit_hid(dest_dir: Path, bundle_tag: str | None = None) -> Path:
    """Download and extract adafruit_hid from the CircuitPython bundle.

    Args:
        dest_dir: Directory to extract to (e.g. CIRCUITPY/lib/).
        bundle_tag: Release tag (e.g. "20260301"). Auto-detects latest if None.

    Returns:
        Path to the extracted adafruit_hid directory.
    """
    import urllib.error
    import urllib.request

    if bundle_tag is None:
        print("  Fetching latest bundle version from GitHub...")
        bundle_tag = _get_latest_bundle_tag()

    url = _BUNDLE_URL.format(tag=bundle_tag)
    print(f"  Downloading bundle {bundle_tag}...")

    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            zip_bytes = resp.read()
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot download adafruit_hid bundle.\n"
            f"  Check your internet connection.\n"
            f"  Details: {e}"
        ) from e

    print(f"  Downloaded {len(zip_bytes) / 1024 / 1024:.1f} MB, extracting adafruit_hid...")

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise RuntimeError(
            f"Downloaded bundle is not a valid zip file.\n"
            f"  Try running the command again. Details: {e}"
        ) from e

    with zf:
        hid_prefix = None
        for name in zf.namelist():
            if "/lib/adafruit_hid/" in name:
                hid_prefix = name[: name.index("/lib/adafruit_hid/") + len("/lib/adafruit_hid/")]
                break

        if not hid_prefix:
            raise FileNotFoundError("adafruit_hid not found in bundle zip")

        hid_dest = dest_dir / "adafruit_hid"
        if hid_dest.exists():
            shutil.rmtree(hid_dest)
        hid_dest.mkdir(parents=True)

        for info in zf.infolist():
            if info.filename.startswith(hid_prefix) and not info.is_dir():
                relative = info.filename[len(hid_prefix):]
                if relative:
                    target = hid_dest / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as dst:
                        dst.write(src.read())

    print(f"  Extracted adafruit_hid to {hid_dest}")
    return hid_dest


# ---------------------------------------------------------------------------
# Firmware copy
# ---------------------------------------------------------------------------

def copy_firmware(drive: Path) -> None:
    """Copy boot.py and code.py to the CIRCUITPY drive."""
    fw_dir = _firmware_dir()
    for filename in ("boot.py", "code.py"):
        src = fw_dir / filename
        dst = drive / filename
        if not src.exists():
            raise FileNotFoundError(f"Firmware file not found: {src}")
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            raise OSError(
                f"Failed to copy {filename} to {dst}: {e}\n"
                f"  Make sure the CIRCUITPY drive is still connected."
            ) from e
        print(f"  Copied {filename} -> {dst}")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify_pico() -> bool:
    """Send PING to the Pico and check for PONG response."""
    from pywinhello.hid import HIDKeyboard

    try:
        with HIDKeyboard() as kb:
            if kb.ping():
                print(f"  PONG received from {kb._port_name}")
                return True
            else:
                print("  No PONG response — Pico connected but firmware may not be running.")
                return False
    except ConnectionError:
        print("  Pico not found on any COM port.")
        print("  Make sure it's plugged in and has CircuitPython + firmware installed.")
        return False
    except TimeoutError:
        print("  Pico found but not responding (timeout).")
        print("  Try unplugging and re-plugging the Pico.")
        return False
    except Exception as e:
        print(f"  Verify failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Board resolution
# ---------------------------------------------------------------------------

def resolve_board(board: str | None, rpi_drive: Path | None) -> str:
    """Determine the board variant from explicit arg or bootloader detection.

    For RP2040 boards (Pico vs Pico W), defaults to pico_w since W is more
    common and the UF2 works on both. User can override with --board.
    """
    if board:
        return board

    if rpi_drive:
        family = detect_board_from_rpi_drive(rpi_drive)
        if family == "pico":
            print("  Detected RP2040 board (Pico or Pico W)")
            print("  Defaulting to pico_w — use --board pico if you have a non-W Pico")
            return "pico_w"
        if family == "pico2":
            print("  Detected RP2350 board (Pico 2 or Pico 2 W)")
            print("  Defaulting to pico2 — use --board pico2_w if you have a Pico 2 W")
            return "pico2"

        info_file = rpi_drive / "INFO_UF2.TXT"
        if info_file.exists():
            content = info_file.read_text(errors="ignore").strip()
            print("  WARNING: Unrecognized board. INFO_UF2.TXT contents:")
            for line in content.splitlines()[:5]:
                print(f"    {line}")
            print()
            confirm = input("  Try pico_w anyway? [Y/n] ").strip()
            if confirm.lower() in ("n", "no"):
                raise SystemExit("Aborted. Re-run with --board <variant>")
            return "pico_w"

    print("  Could not detect board variant. Defaulting to pico_w.")
    print("  Use --board to specify: pico, pico_w, pico2, pico2_w")
    return "pico_w"


# ---------------------------------------------------------------------------
# Full setup flow
# ---------------------------------------------------------------------------

def run_setup(
    *,
    drive: Path | None = None,
    board: str | None = None,
    bundle_tag: str | None = None,
    verify: bool = True,
    skip_verify: bool = False,
) -> bool:
    """Run the full Pico HID setup flow.

    Args:
        drive: Explicit CIRCUITPY drive path. Auto-detected if None.
        board: Board variant for UF2 download. Auto-detected if None.
        bundle_tag: CircuitPython bundle release tag. Latest if None.
        verify: Whether to verify PING after setup.
        skip_verify: Skip the verification step.

    Returns:
        True if setup completed successfully.
    """
    # Step 1: Detect drive state
    if drive is not None:
        print(f"Step 1: Using specified drive {drive}")
        if not drive.exists():
            print(f"ERROR: Drive {drive} does not exist")
            return False
    else:
        print("Step 1: Detecting Pico...")

        drive = find_circuitpy_drive()
        if drive is not None:
            print(f"  Found CIRCUITPY at {drive} — CircuitPython already installed")
        else:
            rpi_drive = find_rpi_rp2_drive()
            if rpi_drive is not None:
                print(f"  Found Pico in bootloader mode at {rpi_drive}")
                print()
                confirm = input("  Ready to flash CircuitPython. Continue? [Y/n] ").strip()
                if confirm.lower() in ("n", "no"):
                    print("Aborted.")
                    return False

                board = resolve_board(board, rpi_drive)

                print(f"\nStep 1b: Downloading CircuitPython for {board}...")
                try:
                    uf2_data = download_circuitpython_uf2(board)
                except (ConnectionError, FileNotFoundError, RuntimeError) as e:
                    print(f"ERROR: {e}")
                    return False

                print("\nStep 1c: Flashing CircuitPython...")
                try:
                    drive = flash_circuitpython(rpi_drive, uf2_data)
                except (TimeoutError, OSError) as e:
                    print(f"ERROR: {e}")
                    return False
            else:
                print(
                    "ERROR: No Pico detected.\n"
                    "\n"
                    "To set up a new Pico:\n"
                    "  1. Hold the BOOTSEL button on the Pico\n"
                    "  2. While holding BOOTSEL, plug the USB cable into your PC\n"
                    "  3. Release BOOTSEL\n"
                    "  4. Run this command again\n"
                    "\n"
                    "If your Pico already has CircuitPython, make sure it's plugged in.\n"
                    "You can also specify the drive manually: --drive E:\n"
                )
                return False

    # Step 2: Download adafruit_hid
    print("\nStep 2: Installing adafruit_hid library...")
    lib_dir = drive / "lib"
    lib_dir.mkdir(exist_ok=True)
    try:
        download_adafruit_hid(lib_dir, bundle_tag=bundle_tag)
    except (ConnectionError, RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        return False
    except OSError as e:
        print(f"ERROR: Failed to write to CIRCUITPY drive: {e}")
        return False

    # Step 3: Copy firmware
    print("\nStep 3: Copying firmware files...")
    try:
        copy_firmware(drive)
    except Exception as e:
        print(f"ERROR: {e}")
        return False

    print("\nSetup complete! The Pico will reboot automatically.")

    # Step 4: Verify
    if not skip_verify and verify:
        print("\nStep 4: Verifying (waiting 5s for reboot)...")
        time.sleep(5)
        ok = verify_pico()
        if ok:
            print("\nAll good! HID bridge is working.")
        else:
            print(
                "\nVerification failed. The Pico may still be rebooting.\n"
                "Try again with: pywinhello ping"
            )
            return False
    else:
        print("\nSkipped verification. Test manually with: pywinhello ping")

    return True
