"""Wording for every language, loaded from the shared locales/*.json catalogues.

The catalogues are shared with the UI: the same files are globbed by ui/src/shared/i18n, so a
sentence exists once and both sides read it. Keys are dotted paths into the JSON, areas are
common / panel / editor / steps / notify / native, and a placeholder is {name} in every
language because str.format and String.replace agree on that much.

Python handles the half the UI cannot: the native Qt strings, and the English fallback text
carried on every notify payload. The notify `text` is deliberately always English -- it is what
a UI that could not translate the code itself falls back to, so it must not follow the app's
current language.

Nothing here raises. A missing catalogue, a missing key or a misspelled placeholder is a bug
worth logging, never a reason to take the app down over a toast.
"""

import json
import logging
from typing import Any, TypedDict

from map_overlay.core.paths import resource_path

log = logging.getLogger(__name__)

FALLBACK_LANGUAGE = "en"

# A dict whose keys are all CLDR categories is a plural leaf, not another level of nesting.
PLURAL_CATEGORIES = frozenset({"zero", "one", "two", "few", "many", "other"})

Catalog = dict[str, Any]


class _State(TypedDict):
    catalogs: dict[str, Catalog] | None
    language: str


# Module state lives in one dict so that reading it needs no `global`: the catalogues are
# loaded once and the language is chosen by the settings layer at startup.
_state: _State = {"catalogs": None, "language": FALLBACK_LANGUAGE}


def _is_plural_leaf(node: dict[str, Any]) -> bool:
    return bool(node) and all(
        key in PLURAL_CATEGORIES and isinstance(value, str) for key, value in node.items()
    )


def _flatten(node: dict[str, Any], prefix: str, out: Catalog) -> None:
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and not _is_plural_leaf(value):
            _flatten(value, path, out)
        else:
            out[path] = value


def _load() -> dict[str, Catalog]:
    cached = _state["catalogs"]
    if cached is not None:
        return cached
    loaded: dict[str, Catalog] = {}
    _state["catalogs"] = loaded
    folder = resource_path("locales")
    try:
        files = sorted(folder.glob("*.json"))
    except OSError:
        log.exception("cannot list %s", folder)
        files = []
    if not files:
        log.error("no locale catalogues under %s; every string will fall back to its key", folder)
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            log.exception("cannot read locale catalogue %s", path)
            continue
        flat: Catalog = {}
        _flatten(data, "", flat)
        loaded[path.stem] = flat
    return loaded


def available_languages() -> list[str]:
    """Which catalogues shipped, e.g. ["en", "ru"]. A new language is a new file, nothing else."""
    return sorted(_load())


def resolve_language(setting: str, system: str | None) -> str:
    """Turn the `auto | en | ru` setting into a language that actually has a catalogue.

    `system` is the OS language (QLocale.system().name()[:2] at the call site, so that this
    module stays free of Qt). Anything unrecognised lands on English.
    """
    have = set(available_languages())
    if setting != "auto":
        return setting if setting in have else FALLBACK_LANGUAGE
    short = (system or "")[:2].lower()
    return short if short in have else FALLBACK_LANGUAGE


def set_language(language: str) -> None:
    """Choose the language for `t`. Unknown languages fall back rather than failing."""
    if language not in _load():
        log.warning("no catalogue for %r, staying on %s", language, FALLBACK_LANGUAGE)
        _state["language"] = FALLBACK_LANGUAGE
        return
    _state["language"] = language


def current_language() -> str:
    """The language `t` is answering in. The steps page is told this so it matches the window."""
    return str(_state["language"])


def _plural_category(language: str, count: Any) -> str:
    """CLDR category for a count. Hand-written: Python has no Intl.PluralRules."""
    if not isinstance(count, int) or isinstance(count, bool):
        return "other"
    n = abs(count)
    if language == "ru":
        mod10, mod100 = n % 10, n % 100
        if mod10 == 1 and mod100 != 11:
            return "one"
        if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
            return "few"
        return "many"
    return "one" if n == 1 else "other"


def _select(template: Any, language: str, params: dict[str, Any]) -> str | None:
    """Pick the plural form when the entry is a leaf of categories; otherwise pass it through."""
    if isinstance(template, str):
        return template
    if not isinstance(template, dict):
        return None
    category = _plural_category(language, params.get("count"))
    chosen = template.get(category) or template.get("other")
    return chosen if isinstance(chosen, str) else None


def _lookup(key: str, language: str, params: dict[str, Any]) -> str | None:
    catalogs = _load()
    for candidate in (language, FALLBACK_LANGUAGE):
        entry = catalogs.get(candidate, {}).get(key)
        if entry is None:
            continue
        template = _select(entry, candidate, params)
        if template is not None:
            return template
    return None


def _fill(template: str, params: dict[str, Any], what: str) -> str:
    try:
        return template.format(**params)
    except KeyError, IndexError, ValueError:
        log.warning("cannot format %r with %r", what, params, exc_info=True)
        return template


def t(key: str, **params: Any) -> str:
    """A string in the current language: window titles, dialog captions, prompts.

    Falls back to English, then to the key itself, which is visible enough in the UI to be
    noticed and harmless enough not to break the window that wanted it.
    """
    template = _lookup(key, current_language(), params)
    if template is None:
        log.warning("no string for %r", key)
        return key
    return _fill(template, params, key)


def format_code(code: str, params: dict[str, Any] | None = None) -> str:
    """The English sentence for a notification code, for the `text` on a notify payload.

    Always English, whatever the app's language: this is the fallback a UI shows when it cannot
    translate the code itself, and the UI is the side that knows the user's language.
    """
    args = params or {}
    template = _lookup(f"notify.{code}", FALLBACK_LANGUAGE, args)
    if template is None:
        log.warning("no message for code %r", code)
        return code
    filled = _fill(template, args, code)
    return code if filled is template and "{" in template else filled
