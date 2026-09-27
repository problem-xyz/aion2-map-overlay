"""The object sets that ship with the maps: listed at once, loaded in full, never removable."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store import maps as maps_store

REPO = Path(__file__).resolve().parents[2]

A_SET = {
    "mapName": "Altgard",
    "categories": [{"id": "tp", "name": "Teleports", "color": "#6ea8ff"}],
    "nodes": [{"categoryId": "tp", "x": 10, "y": 20, "title": "Gate", "description": ""}],
}


@pytest.fixture
def shipped_set(test_maps_root: Callable[[], Path]) -> Iterator[Path]:
    folder = test_maps_root().parent / "object-sets"
    path = folder / "altgard.json"
    atomic_write_json(path, A_SET)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs, shipped_set: Path) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def objects_of(backend: Backend, map_id: str) -> list[dict]:
    state = json.loads(backend.getState())
    return next(m for m in state["maps"] if m["id"] == map_id)["objects"]


def test_a_shipped_set_is_on_its_map_without_an_import(backend: Backend) -> None:
    assert objects_of(backend, "altgard") == [
        {"file": "bundled/altgard.json", "mapName": "Altgard", "nodes": 1, "bundled": True}
    ]
    assert objects_of(backend, "verteron") == []


def test_the_editor_gets_the_shipped_set_in_full(backend: Backend) -> None:
    sets = json.loads(backend.getObjects("altgard"))
    assert [s["file"] for s in sets] == ["bundled/altgard.json"]
    assert sets[0]["bundled"] is True
    assert sets[0]["nodes"][0]["t"] == "Gate"


def test_a_set_the_user_imported_before_api_8_is_not_read(backend: Backend) -> None:
    """A map's objects ship with it: an old import left in maps/<id>/objects/ is ignored."""
    odir = backend.dirs.maps / "altgard" / "objects"
    atomic_write_json(
        odir / "mine.json",
        {
            "mapName": "Mine",
            "categories": [{"id": "a", "name": "A"}],
            "nodes": [{"categoryId": "a", "x": 1, "y": 1, "title": "x"}],
        },
    )
    assert [s["file"] for s in objects_of(backend, "altgard")] == ["bundled/altgard.json"]
    assert [s["file"] for s in json.loads(backend.getObjects("altgard"))] == [
        "bundled/altgard.json"
    ]


def test_a_broken_shipped_set_is_left_out_and_the_map_still_loads(
    test_maps_root: Callable[[], Path], caplog: pytest.LogCaptureFixture
) -> None:
    folder = test_maps_root().parent / "object-sets"
    path = folder / "verteron.json"
    atomic_write_json(path, {"nodes": "not a list"})
    try:
        specs = maps_store.load_bundled_maps()
    finally:
        path.unlink()
    verteron = next(s for s in specs if s.id == "verteron")
    assert verteron.objects == ()
    assert any("not usable" in r.getMessage() for r in caplog.records)


def test_the_sets_that_ship_belong_to_the_maps_that_ship() -> None:
    specs = maps_store.load_bundled_maps(
        REPO / "assets" / "maps", objects_root=REPO / "assets" / "object-sets"
    )
    for spec in specs:
        assert [o.file for o in spec.objects] == [f"bundled/{spec.id}.json"], spec.id
        assert spec.objects[0].nodes > 0
