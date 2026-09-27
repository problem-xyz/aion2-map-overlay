"""The notice after "Import" and "Paste code", in every language it ships in.

It used to be one sentence with a `{source}` slot that Python filled with the English word
`file` or `clipboard`. The UI translated the sentence around that word and never the word, so
the Russian notice ended in "(clipboard)". Each source now has a sentence of its own, and this
checks the one each slot sends in each catalogue, with the route's own name taken out.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.i18n.catalog import available_languages, set_language, t
from map_overlay.store.routes import new_route_doc
from map_overlay.store.share import encode_share

NAME = "Smoke"
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


@pytest.fixture
def route(backend: Backend) -> dict[str, Any]:
    """A one-point route on a map this installation has, so the import needs no dialog."""
    first = backend._routes.maps()[0]
    doc = new_route_doc(NAME, first["id"], first["size"])
    doc["markers"] = [{"x": 10.0, "y": 20.0, "text": ""}]
    return doc


def import_from_file(
    backend: Backend, doc: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "shared.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(backend._dialogs, "open_json", lambda caption: str(path))
    backend.importRouteFile()


def paste_code(
    backend: Backend, doc: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backend._dialogs, "paste", lambda: encode_share(doc))
    backend.pasteRouteCode()


IMPORTS = {"file": import_from_file, "clipboard": paste_code}


@pytest.mark.parametrize("source", sorted(IMPORTS))
def test_the_imported_notice_is_a_whole_sentence_in_every_language(
    backend: Backend,
    route: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    code = f"route.imported.{source}"
    payloads: list[dict[str, Any]] = []
    backend.notify.connect(lambda raw: payloads.append(json.loads(raw)))

    IMPORTS[source](backend, route, tmp_path, monkeypatch)

    notices = [p for p in payloads if p["code"].startswith("route.imported")]
    assert [(p["code"], p["params"]) for p in notices] == [(code, {"name": NAME})]
    try:
        for language in available_languages():
            set_language(language)
            sentence = t(f"notify.{code}", **notices[0]["params"])
            assert NAME in sentence, language
            if language != "en":
                # Nothing English may be left once the route's own name is taken out.
                assert not LATIN_WORD.search(sentence.replace(NAME, "")), (language, sentence)
    finally:
        set_language("en")
