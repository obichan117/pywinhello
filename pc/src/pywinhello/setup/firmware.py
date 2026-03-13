"""Board-aware firmware resolution — find the right UF2 for a board variant.

Firmware files follow the naming convention ``pywinhello_{variant}.uf2``
where variant is one of: pico, pico_w, pico_2, pico_2_w.

Search order:
1. Explicit directory (if provided)
2. Package data (``pywinhello/_data/firmware/``)
3. Adjacent ``_data/firmware/`` directory (dev fallback)
"""

from __future__ import annotations

import logging
from pathlib import Path

from pywinhello.models import BoardVariant

logger = logging.getLogger(__name__)


def _same_chip_variants(board: BoardVariant) -> list[BoardVariant]:
    """Return board variants that share the same chip (and firmware binary).

    The requested board is always first (exact match preferred). Remaining
    siblings follow as fallbacks — BOOTSEL mode can't distinguish W from
    non-W, and the firmware auto-detects WiFi at runtime.
    """
    rp2040 = [BoardVariant.PICO, BoardVariant.PICO_W]
    rp2350 = [BoardVariant.PICO_2, BoardVariant.PICO_2_W]
    family = rp2040 if board in rp2040 else rp2350
    # Put exact match first
    return [board] + [v for v in family if v != board]


def _search_firmware(filename: str, search_dir: Path | None) -> Path | None:
    """Search for a firmware file across all known locations."""
    # 1. Explicit directory
    if search_dir is not None:
        candidate = search_dir / filename
        if candidate.exists():
            logger.info("Found firmware: %s", candidate)
            return candidate

    # 2. Package data
    try:
        import importlib.resources as resources

        data_dir = resources.files("pywinhello") / "_data" / "firmware"
        candidate_path = data_dir / filename  # type: ignore[operator]
        if hasattr(candidate_path, "is_file") and candidate_path.is_file():
            resolved = Path(str(candidate_path))
            logger.info("Found firmware in package data: %s", resolved)
            return resolved
    except (ImportError, FileNotFoundError, TypeError):
        pass

    # 3. Dev fallback — adjacent _data/firmware/
    local = Path(__file__).parent.parent / "_data" / "firmware"
    candidate = local / filename
    if candidate.exists():
        logger.info("Found firmware (dev fallback): %s", candidate)
        return candidate

    return None


def get_firmware_path(board: BoardVariant, search_dir: Path | None = None) -> Path | None:
    """Find the UF2 firmware file for a specific board variant.

    Since BOOTSEL mode can't distinguish W from non-W, this also checks
    sibling variants on the same chip. A ``pywinhello_pico_w.uf2`` works
    for both Pico and Pico W (the firmware auto-detects WiFi at runtime).

    Args:
        board: Target board variant.
        search_dir: Explicit directory to search first. If ``None``,
            falls through to package data and dev fallback.

    Returns:
        Path to the .uf2 file, or ``None`` if not found.
    """
    # Try exact match first, then same-chip siblings
    for variant in _same_chip_variants(board):
        filename = f"pywinhello_{variant.value}.uf2"
        result = _search_firmware(filename, search_dir)
        if result is not None:
            return result

    logger.warning(
        "Firmware not found for %s (searched all %s variants)",
        board.value,
        "RP2350" if board in (BoardVariant.PICO_2, BoardVariant.PICO_2_W) else "RP2040",
    )
    return None


def list_bundled_firmware() -> dict[BoardVariant, Path]:
    """Enumerate all available UF2 firmware files.

    Returns:
        Mapping of board variant → firmware path for all found variants.
    """
    found: dict[BoardVariant, Path] = {}
    for variant in BoardVariant:
        path = get_firmware_path(variant)
        if path is not None:
            found[variant] = path
    return found
