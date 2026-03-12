"""Internationalization loader for pywinhello GUI.

Loads locale JSON files (ja.json / en.json) and provides a flat
key-path accessor (e.g. ``t("wizard.step1.title")``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_LOCALE_DIR = Path(__file__).parent
_SUPPORTED_LOCALES = ("ja", "en")
_DEFAULT_LOCALE = "ja"

# Module-level cache: locale -> nested dict
_cache: dict[str, dict[str, Any]] = {}

# Current active locale
_current_locale: str = _DEFAULT_LOCALE


def load_strings(locale: str) -> dict[str, Any]:
    """Load and cache locale strings from JSON.

    Args:
        locale: Language code ("ja" or "en").

    Returns:
        Nested dictionary of all locale strings.

    Raises:
        FileNotFoundError: If the locale file does not exist.
        ValueError: If the locale is not supported.
    """
    if locale not in _SUPPORTED_LOCALES:
        raise ValueError(
            f"Unsupported locale '{locale}'. Supported: {_SUPPORTED_LOCALES}"
        )

    if locale in _cache:
        return _cache[locale]

    path = _LOCALE_DIR / f"{locale}.json"
    if not path.exists():
        raise FileNotFoundError(f"Locale file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    _cache[locale] = data
    return data


def get_locale() -> str:
    """Return the current active locale code."""
    return _current_locale


def set_locale(locale: str) -> None:
    """Set the active locale.

    Args:
        locale: Language code ("ja" or "en").
    """
    global _current_locale
    if locale not in _SUPPORTED_LOCALES:
        raise ValueError(
            f"Unsupported locale '{locale}'. Supported: {_SUPPORTED_LOCALES}"
        )
    _current_locale = locale
    # Pre-load into cache
    load_strings(locale)


def t(key_path: str, **kwargs: Any) -> str:
    """Translate a dot-separated key path using the current locale.

    Args:
        key_path: Dot-separated path, e.g. "wizard.step1.title".
        **kwargs: Format arguments for string interpolation.

    Returns:
        Translated string, or the key_path itself if not found.

    Examples:
        >>> t("wizard.step_label", current=1, total=4)
        'Step 1/4'
    """
    strings = load_strings(_current_locale)
    parts = key_path.split(".")
    node: Any = strings
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return key_path  # Fallback: return the key itself

    if not isinstance(node, str):
        return key_path

    if kwargs:
        try:
            return node.format(**kwargs)
        except (KeyError, IndexError):
            return node

    return node


def get_supported_locales() -> tuple[str, ...]:
    """Return tuple of supported locale codes."""
    return _SUPPORTED_LOCALES


def detect_default_locale() -> str:
    """Detect the default locale.

    Checks (in order):
    1. Pico config ``locale`` field (if available)
    2. Windows system locale
    3. Falls back to "ja"
    """
    # Try to read from Pico config (serial module may not exist yet)
    try:
        from pywinhello.serial.device import PicoDevice

        dev = PicoDevice.find()
        if dev is not None:
            cfg = dev.get_config()
            if cfg and "locale" in cfg:
                locale = cfg["locale"]
                if locale in _SUPPORTED_LOCALES:
                    return locale
    except Exception:
        pass

    # Try Windows system locale
    try:
        import locale as sys_locale

        lang, _ = sys_locale.getdefaultlocale()
        if lang and lang.startswith("ja"):
            return "ja"
        if lang and lang.startswith("en"):
            return "en"
    except Exception:
        pass

    return _DEFAULT_LOCALE
