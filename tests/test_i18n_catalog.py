"""The catalogues have to agree with each other, or a language silently loses strings.

These checks are the Python half of "the catalogues are valid". The Vitest side covers what
only the UI can see: that every `t("…")` literal in ui/src exists, and that the plural
categories match Intl.PluralRules.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from map_overlay.i18n.catalog import (
    PLURAL_CATEGORIES,
    available_languages,
    format_code,
    resolve_language,
    set_language,
    t,
)

LOCALES = Path(__file__).resolve().parents[1] / "locales"
PLACEHOLDER = re.compile(r"\{(\w+)\}")
CYRILLIC = re.compile(r"[\u0400-\u04FF]")
# CLDR categories each language actually uses. A missing form is a sentence nobody wrote.
EXPECTED_CATEGORIES = {"en": {"one", "other"}, "ru": {"one", "few", "many", "other"}}


def _flatten(node: dict[str, Any], prefix: str, out: dict[str, Any]) -> None:
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        is_leaf = isinstance(value, dict) and value and all(k in PLURAL_CATEGORIES for k in value)
        if isinstance(value, dict) and not is_leaf:
            _flatten(value, path, out)
        else:
            out[path] = value


def _catalog(language: str) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    _flatten(json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8")), "", flat)
    return flat


def _placeholders(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {name for form in value.values() for name in PLACEHOLDER.findall(form)}
    return set(PLACEHOLDER.findall(value))


def test_every_language_has_the_same_keys() -> None:
    reference = _catalog("en")
    for language in available_languages():
        assert set(_catalog(language)) == set(reference), f"{language} key set differs from en"


def test_plural_leaves_carry_their_language_categories() -> None:
    for language in available_languages():
        for key, value in _catalog(language).items():
            if isinstance(value, dict):
                assert set(value) == EXPECTED_CATEGORIES[language], key


def test_placeholders_match_across_languages() -> None:
    reference = _catalog("en")
    for language in available_languages():
        for key, value in _catalog(language).items():
            assert _placeholders(value) == _placeholders(reference[key]), key


def test_english_catalogue_has_no_cyrillic() -> None:
    raw = (LOCALES / "en.json").read_text(encoding="utf-8")
    assert not CYRILLIC.search(raw)


def test_a_plural_leaf_is_a_leaf_not_a_nested_area() -> None:
    # If a real area were ever named after a CLDR category, flattening would swallow it.
    areas = {key.split(".")[0] for key in _catalog("en")}
    assert not areas & PLURAL_CATEGORIES


@pytest.mark.parametrize(
    ("count", "expected"),
    # These assert the wording in the shipped catalogue, not merely which category is picked,
    # so the Russian is the point of the test.
    [
        (1, "1 точка"),  # allow-cyrillic
        (2, "2 точки"),  # allow-cyrillic
        (5, "5 точек"),  # allow-cyrillic
        (11, "11 точек"),  # allow-cyrillic
        (21, "21 точка"),  # allow-cyrillic
    ],
)
def test_russian_plural_rules(count: int, expected: str) -> None:
    # 11 is the exception 21 is not: both end in 1, only one of them is "one".
    set_language("ru")
    try:
        assert t("common.points", count=count) == expected
    finally:
        set_language("en")


def test_notify_text_stays_english_while_the_app_is_russian() -> None:
    # The `text` on a notify payload is the fallback for a UI that could not translate the
    # code itself, so it must not follow the app's language.
    set_language("ru")
    try:
        assert format_code("route.saved", {"name": "Altgard"}) == "Route “Altgard” saved."
    finally:
        set_language("en")


def test_unknown_key_and_code_degrade_to_themselves() -> None:
    assert t("no.such.key") == "no.such.key"
    assert format_code("no.such.code") == "no.such.code"


# The data-safety codes and the bundled-map codes, with the parameters the
# code that raises them passes.
DATA_SAFETY_CODES = [
    ("data.migration_failed", {"path": "D:\\Games\\MapOverlay\\routes"}),
    ("route.file_too_large", {"limit": 5}),
    ("route.file_skipped_too_large", {"file": "gold.json", "limit": 5}),
    ("route.too_large", {"limit": 5}),
    ("map.manifest_invalid", {"id": "altgard", "reason": "reference.webp is missing"}),
    ("map.unknown", {"id": "custom"}),
    ("legacy.routes_moved", {"names": "Old route, gold"}),
    ("route.starters_updated", {"names": "Asmodians - Level 10-17"}),
]


@pytest.mark.parametrize(("code", "params"), DATA_SAFETY_CODES)
@pytest.mark.parametrize("language", ["en", "ru"])
def test_every_data_safety_code_has_a_filled_sentence(
    language: str, code: str, params: dict[str, Any]
) -> None:
    set_language(language)
    try:
        text = t(f"notify.{code}", **params)
    finally:
        set_language("en")
    assert text != f"notify.{code}"
    assert "{" not in text
    for value in params.values():
        assert str(value) in text


def test_resolve_language_falls_back_to_a_catalogue_that_exists() -> None:
    assert resolve_language("auto", "ru_RU") == "ru"
    assert resolve_language("auto", "de_DE") == "en"
    assert resolve_language("auto", None) == "en"
    assert resolve_language("ru", "en") == "ru"
