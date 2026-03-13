"""OTA firmware push over serial.

Sends the FLASH command followed by a binary firmware image.
The Pico receives the image, writes to flash, verifies CRC, and reboots.

Protocol::

    PC: FLASH:{size}
    Pico: READY
    PC: <binary data in chunks>
    Pico: OK:crc32={checksum}  (on success)
    Pico: ERR:message           (on failure)
    Pico reboots automatically on success
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pywinhello.serial.protocol import SerialProtocol, parse_response

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 4096
_FLASH_COMPLETE_TIMEOUT = 30.0
_POST_REBOOT_DELAY = 5.0


@dataclass(frozen=True)
class FlashResult:
    """Result of a firmware flash operation."""

    success: bool
    """Whether the flash completed successfully."""

    firmware_path: str
    """Path to the firmware file that was flashed."""

    size: int
    """Size of the firmware in bytes."""

    sha256: str
    """SHA-256 hash of the firmware file."""

    elapsed: float
    """Seconds taken for the flash operation."""

    error: str | None = None
    """Error message if the flash failed."""


def flash_firmware(
    protocol: SerialProtocol,
    firmware_path: str | Path,
    expected_hash: str | None = None,
    chunk_size: int = _CHUNK_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
) -> FlashResult:
    """Flash firmware to the Pico over serial.

    Args:
        protocol: Connected SerialProtocol instance.
        firmware_path: Path to the .uf2 or .bin firmware file.
        expected_hash: Expected SHA-256 hash (verified before sending).
        chunk_size: Size of each data chunk sent over serial.
        on_progress: Optional callback(bytes_sent, total_bytes) for progress reporting.

    Returns:
        FlashResult with the outcome.
    """
    start = time.time()
    path = Path(firmware_path)

    if not path.exists():
        return FlashResult(
            success=False,
            firmware_path=str(path),
            size=0,
            sha256="",
            elapsed=time.time() - start,
            error=f"Firmware file not found: {path}",
        )

    data = path.read_bytes()
    size = len(data)
    sha256 = hashlib.sha256(data).hexdigest()

    # Verify hash if provided
    if expected_hash is not None:
        clean_hash = expected_hash.removeprefix("sha256:")
        if sha256 != clean_hash:
            return FlashResult(
                success=False,
                firmware_path=str(path),
                size=size,
                sha256=sha256,
                elapsed=time.time() - start,
                error=f"Hash mismatch: expected {clean_hash}, got {sha256}",
            )

    logger.info("Flashing %s (%d bytes, sha256=%s)", path.name, size, sha256[:16])

    try:
        # Initiate flash mode
        protocol.flash_begin(size)
        logger.debug("Pico acknowledged FLASH, streaming data...")

        # Stream firmware data in chunks
        sent = 0
        while sent < size:
            end = min(sent + chunk_size, size)
            protocol.write_raw(data[sent:end])
            sent = end
            if on_progress is not None:
                on_progress(sent, size)

        logger.debug("All %d bytes sent, waiting for verification...", size)

        # Wait for Pico to verify and respond
        resp_line = protocol.read_line(timeout=_FLASH_COMPLETE_TIMEOUT)
        resp = parse_response(resp_line)

        if not resp.ok:
            return FlashResult(
                success=False,
                firmware_path=str(path),
                size=size,
                sha256=sha256,
                elapsed=time.time() - start,
                error=f"Flash verification failed: {resp.data}",
            )

        logger.info("Flash complete, Pico rebooting...")
        return FlashResult(
            success=True,
            firmware_path=str(path),
            size=size,
            sha256=sha256,
            elapsed=time.time() - start,
        )

    except Exception as e:
        return FlashResult(
            success=False,
            firmware_path=str(path),
            size=size,
            sha256=sha256,
            elapsed=time.time() - start,
            error=str(e),
        )


def flash_and_verify(
    protocol: SerialProtocol,
    firmware_path: str | Path,
    expected_hash: str | None = None,
    expected_version: str | None = None,
    post_reboot_delay: float = _POST_REBOOT_DELAY,
    on_progress: Callable[[int, int], None] | None = None,
) -> FlashResult:
    """Flash firmware and verify the new version after reboot.

    Flashes the firmware, waits for the Pico to reboot, then sends PING
    to verify the new firmware version.

    Args:
        protocol: Connected SerialProtocol instance.
        firmware_path: Path to the firmware file.
        expected_hash: Expected SHA-256 hash of the firmware.
        expected_version: Expected firmware version string after reboot.
        post_reboot_delay: Seconds to wait for Pico reboot before PING.
        on_progress: Optional progress callback.

    Returns:
        FlashResult with the outcome.
    """
    result = flash_firmware(
        protocol,
        firmware_path,
        expected_hash=expected_hash,
        on_progress=on_progress,
    )

    if not result.success:
        return result

    if expected_version is not None:
        # Wait for reboot and verify
        logger.info("Waiting %.1fs for Pico reboot...", post_reboot_delay)
        time.sleep(post_reboot_delay)

        try:
            ping_info = protocol.ping()
            if ping_info.firmware_version != expected_version:
                return FlashResult(
                    success=False,
                    firmware_path=result.firmware_path,
                    size=result.size,
                    sha256=result.sha256,
                    elapsed=result.elapsed,
                    error=(
                        f"Version mismatch after flash: "
                        f"expected {expected_version}, got {ping_info.firmware_version}"
                    ),
                )
            logger.info("Firmware verified: v%s", ping_info.firmware_version)
        except Exception as e:
            return FlashResult(
                success=False,
                firmware_path=result.firmware_path,
                size=result.size,
                sha256=result.sha256,
                elapsed=result.elapsed,
                error=f"Post-flash verification failed: {e}",
            )

    return result
