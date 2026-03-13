"""Tests for GUI internationalization module."""

from __future__ import annotations

import pytest

from pywinhello.gui.i18n import (
    get_locale,
    get_supported_locales,
    load_strings,
    set_locale,
    t,
)


@pytest.fixture(autouse=True)
def _reset_locale():
    """Reset locale to default (ja) before each test."""
    set_locale("ja")
    yield
    set_locale("ja")


class TestLoadStrings:
    def test_load_ja(self):
        strings = load_strings("ja")
        assert isinstance(strings, dict)
        assert strings["app"]["title"] == "pywinhello"

    def test_load_en(self):
        strings = load_strings("en")
        assert isinstance(strings, dict)
        assert strings["app"]["title"] == "pywinhello"

    def test_unsupported_locale_raises(self):
        with pytest.raises(ValueError, match="Unsupported locale"):
            load_strings("fr")

    def test_caching(self):
        first = load_strings("ja")
        second = load_strings("ja")
        assert first is second


class TestSetGetLocale:
    def test_default_is_ja(self):
        assert get_locale() == "ja"

    def test_set_en(self):
        set_locale("en")
        assert get_locale() == "en"

    def test_set_invalid_raises(self):
        with pytest.raises(ValueError, match="Unsupported locale"):
            set_locale("de")


class TestTranslation:
    def test_simple_key(self):
        assert t("app.title") == "pywinhello"

    def test_nested_key(self):
        result = t("wizard.step1.title")
        assert result == "デバイスの確認"

    def test_missing_key_returns_key(self):
        assert t("nonexistent.key") == "nonexistent.key"

    def test_format_args(self):
        result = t("wizard.step_label", current=2, total=4)
        assert result == "ステップ 2/4"

    def test_en_translation(self):
        set_locale("en")
        assert t("wizard.step1.title") == "Device Detection"

    def test_en_format_args(self):
        set_locale("en")
        result = t("wizard.step_label", current=1, total=4)
        assert result == "Step 1/4"

    def test_deeply_nested(self):
        result = t("settings.advanced.boot_wait")
        assert result == "起動後の待機時間"

    def test_common_strings(self):
        assert t("common.ok") == "OK"
        assert t("common.cancel") == "キャンセル"

    def test_en_common_strings(self):
        set_locale("en")
        assert t("common.ok") == "OK"
        assert t("common.cancel") == "Cancel"

    def test_partial_path_returns_key(self):
        # "wizard" alone is a dict, not a string
        assert t("wizard") == "wizard"

    def test_format_with_bad_args_returns_template(self):
        # Missing format args — returns the template without interpolation
        result = t("wizard.step_label")
        assert "{current}" in result


class TestSupportedLocales:
    def test_supported_locales(self):
        locales = get_supported_locales()
        assert "ja" in locales
        assert "en" in locales

    def test_both_locales_have_same_keys(self):
        ja = load_strings("ja")
        en = load_strings("en")

        def get_keys(d: dict, prefix: str = "") -> set[str]:
            keys: set[str] = set()
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.update(get_keys(v, full))
                else:
                    keys.add(full)
            return keys

        ja_keys = get_keys(ja)
        en_keys = get_keys(en)
        missing = ja_keys - en_keys
        extra = en_keys - ja_keys
        assert ja_keys == en_keys, f"ja-only={missing}, en-only={extra}"
