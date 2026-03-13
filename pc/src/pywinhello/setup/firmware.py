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


def get_firmware_path(board: BoardVariant, search_dir: Path | None = None) -> Path | None:
    """Find the UF2 firmware file for a specific board variant.

    Args:
        board: Target board variant.
        search_dir: Explicit directory to search first. If ``None``,
            falls through to package data and dev fallback.

    Returns:
        Path to the .uf2 file, or ``None`` if not found.
    """
    filename = f"pywinhello_{board.value}.uf2"

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
        # resources.files returns a Traversable; check if the file exists
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

    logger.warning("Firmware not found for %s (searched: %s)", board.value, filename)
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
