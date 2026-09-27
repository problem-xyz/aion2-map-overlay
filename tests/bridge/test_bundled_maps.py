"""The two bundled maps as the Backend serves them.

They arrive with the app, so the Backend cuts them into tiles on the first start, lists them and
nothing else, and starts a route only on one of them. Built on the real Backend with the test
registry standing in for the shipped images (tests/conftest.py).
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from map_overlay.bridge.backend import Backend
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Region
from map_overlay.store import routes
from map_overlay.store.images import imwrite
from map_overlay.store.maps import load_bundled_maps

WAIT_MS = 10000
REGION = Region(left=0, top=0, width=400, height=300)


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def notices(backend: Backend) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []
    backend.notify.connect(lambda raw: seen.append(json.loads(raw)))
    return seen


@pytest.mark.builds_tiles
def test_the_bundled_maps_are_cut_into_tiles_on_the_first_start(
    qapp: QApplication, dirs: DataDirs, qtbot: QtBot
) -> None:
    backend = Backend(dirs)
    try:
        seen = notices(backend)
        qtbot.waitUntil(lambda: not backend._tiles.busy(), timeout=WAIT_MS)
        state = json.loads(backend.getState())
    finally:
        backend.shutdown()

    assert [(m["id"], m["tiles"]) for m in state["maps"]] == [
        ("altgard", {"ready": True, "zMax": 1, "tile": 256}),
        ("verteron", {"ready": True, "zMax": 2, "tile": 256}),
    ]
    assert [n["params"] for n in seen if n["code"] == "map.tiles_ready"] == [
        {"label": "Altgard"},
        {"label": "Verteron"},
    ]
    assert (dirs.maps / "altgard" / "tiles" / "done.json").is_file()
    # 640x480 pads out to 1024, so the full-resolution level 2 is a 4x4 grid.
    assert (dirs.maps / "verteron" / "tiles" / "2" / "3" / "3.jpg").is_file()


@pytest.mark.builds_tiles
def test_a_map_that_ships_a_detail_image_is_cut_from_it(
    qapp: QApplication,
    dirs: DataDirs,
    qtbot: QtBot,
    tmp_path: Path,
    gradient: Callable[..., np.ndarray],
) -> None:
    folder = tmp_path / "assets" / "altgard"
    imwrite(folder / "reference.webp", gradient(512, 384))
    imwrite(folder / "detail.webp", gradient(1024, 768))
    atomic_write_json(
        folder / "manifest.json",
        {"id": "altgard", "label": "Altgard", "size": [512, 384], "detail": [1024, 768]},
    )
    backend = Backend(dirs, maps=load_bundled_maps(folder.parent, ids=("altgard",)))
    try:
        qtbot.waitUntil(lambda: not backend._tiles.busy(), timeout=WAIT_MS)
        (altgard,) = json.loads(backend.getState())["maps"]
    finally:
        backend.shutdown()

    assert altgard["size"] == [512, 384]
    assert altgard["tiles"] == {"ready": True, "zMax": 1, "tile": 256, "zNative": 2}
    # 1024x768 pads out to 1024: the level past the map's own is a 4x4 grid.
    assert (dirs.maps / "altgard" / "tiles" / "2" / "3" / "3.jpg").is_file()


def test_a_folder_placed_under_maps_by_hand_is_not_a_map(
    backend: Backend, dirs: DataDirs, gradient: Callable[..., np.ndarray]
) -> None:
    """The registry is the list; what an older version's user put there is left alone."""
    imwrite(dirs.maps / "custom" / "reference.png", gradient(64, 48))

    state = json.loads(backend.getState())

    assert [m["id"] for m in state["maps"]] == ["altgard", "verteron"]
    assert all(m["thumb"].startswith("data:image/jpeg;base64,") for m in state["maps"])
    assert (dirs.maps / "custom" / "reference.png").is_file()


def test_a_new_route_is_born_on_the_first_bundled_map(backend: Backend) -> None:
    doc, error = backend._routes.editor_doc("")

    assert error is None
    assert doc is not None
    assert (doc["map"], doc["mapSize"]) == ("altgard", [512, 384])


def test_starting_a_route_on_a_map_this_version_does_not_have_says_so(
    backend: Backend, dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A route from a version that let users add maps: it is listed, and it cannot run."""
    routes.save_route(dirs, "old", routes.new_route_doc("Old", "custom", [8192, 8192]))
    backend.setRoute("old")
    backend._store.set_state(region=REGION)
    monkeypatch.setattr(backend, "_revalidate_screens", lambda: False)
    seen = notices(backend)

    backend.start()

    assert not backend.running
    assert (seen[-1]["level"], seen[-1]["code"], seen[-1]["params"]) == (
        "error",
        "map.unknown",
        {"id": "custom"},
    )
    assert "custom" in seen[-1]["text"]
    listed = json.loads(backend.getState())["routes"]
    assert [(r["id"], r["map"], r["mapLabel"]) for r in listed] == [("old", "custom", "")]
