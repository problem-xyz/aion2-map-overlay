"""Import and Paste code through Backend, with only the dialogs and the clipboard stubbed.

Two things an import owes the user beyond adding the route:

* a notice when the points were rescaled. A route whose own map was there but at another size
  always got one; a route whose map was missing, and which the user moved onto one of theirs,
  was rescaled onto it without a word.
* an open editor showing the route that was just added. Import and Paste code are buttons in
  the editor too, and the route they add becomes the active one; the editor stayed on the
  document it had open while the panel and the overlay moved to the new route.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes, share
from map_overlay.store.maps import MapSpec

MAP_SIZE = [512, 384]  # the first map of the test registry, the one `choose_first_map` picks


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


@pytest.fixture
def map_id(bundled: tuple[MapSpec, ...]) -> str:
    first = bundled[0]
    assert list(first.size) == MAP_SIZE
    return first.id


def route_doc(map_name: str, size: list[int]) -> dict[str, Any]:
    doc = routes.new_route_doc("Gold", map_name, size)
    doc["markers"] = [
        {"x": 100.0, "y": 50.0, "text": "chest"},
        {"x": 400.0, "y": 300.0, "text": ""},
    ]
    return routes.validate_route(doc)


def notices(backend: Backend) -> list[str]:
    codes: list[str] = []
    backend.notify.connect(lambda payload: codes.append(json.loads(payload)["code"]))
    return codes


def active_route(backend: Backend) -> dict[str, Any]:
    """The route the import made active, as it was stored."""
    assert backend.route is not None, "the import did not make a route active"
    return routes.load_route(backend.dirs, backend.route)


def import_file(
    backend: Backend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, doc: dict[str, Any]
) -> None:
    path = tmp_path / "shared.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(backend._dialogs, "open_json", lambda caption: str(path))
    backend.importRouteFile()


def paste_code(
    backend: Backend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, doc: dict[str, Any]
) -> None:
    code = share.encode_share(doc)
    monkeypatch.setattr(backend._dialogs, "paste", lambda: code)
    backend.pasteRouteCode()


def choose_first_map(monkeypatch: pytest.MonkeyPatch, backend: Backend) -> list[str]:
    asked: list[str] = []

    def ask_choice(title: str, label: str, items: list[str], current: int = 0) -> str:
        asked.append(label)
        return items[0]

    monkeypatch.setattr(backend._dialogs, "ask_choice", ask_choice)
    return asked


# ---------------------------------------------------------------------- the rescale notice
def test_a_route_moved_onto_a_map_of_another_size_says_it_was_rescaled(
    backend: Backend, map_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = choose_first_map(monkeypatch, backend)
    codes = notices(backend)

    import_file(backend, tmp_path, monkeypatch, route_doc("nosuchmap", [1024, 768]))

    assert asked, "the missing map has to be asked about"
    assert codes == ["route.rescaled", "route.imported.file"]
    stored = active_route(backend)
    assert stored["map"] == map_id
    assert stored["mapSize"] == MAP_SIZE
    assert [(m["x"], m["y"]) for m in stored["markers"]] == [(50.0, 25.0), (200.0, 150.0)]


def test_a_route_moved_onto_a_map_of_the_same_size_is_not_called_rescaled(
    backend: Backend, map_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    choose_first_map(monkeypatch, backend)
    codes = notices(backend)

    import_file(backend, tmp_path, monkeypatch, route_doc("nosuchmap", MAP_SIZE))

    assert codes == ["route.imported.file"]
    assert active_route(backend)["map"] == map_id


def test_a_route_on_its_own_map_at_another_size_still_says_so(
    backend: Backend, map_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codes = notices(backend)

    import_file(backend, tmp_path, monkeypatch, route_doc(map_id, [1024, 768]))

    assert codes == ["route.rescaled", "route.imported.file"]


# ---------------------------------------------------------------------- the open editor
@pytest.mark.parametrize("bring_in", [import_file, paste_code], ids=["import", "paste code"])
def test_an_import_with_the_editor_open_switches_it_to_the_new_route(
    backend: Backend,
    map_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bring_in: Callable[..., None],
) -> None:
    monkeypatch.setattr(backend._windows, "editor_visible", lambda: True)
    before = json.loads(backend.getEditorRoute())
    requests: list[str] = []
    backend.editorRequest.connect(requests.append)

    bring_in(backend, tmp_path, monkeypatch, route_doc(map_id, MAP_SIZE))

    assert len(requests) == 1
    req = json.loads(requests[0])
    assert req["seq"] > before["seq"], "the page ignores a request it has already seen"
    assert req["id"] == backend.route
    assert req["doc"] == active_route(backend)
    # A page that (re)loads now asks for the same thing the signal carried.
    assert json.loads(backend.getEditorRoute()) == req


def test_an_import_with_the_editor_closed_sends_it_nothing(
    backend: Backend, map_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: list[str] = []
    backend.editorRequest.connect(requests.append)

    import_file(backend, tmp_path, monkeypatch, route_doc(map_id, MAP_SIZE))

    assert backend.route
    assert requests == []
