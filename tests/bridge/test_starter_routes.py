"""The starter routes that ship with the app: in routes/ on a new install, each only once."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store.maps import BUNDLED_MAP_IDS
from map_overlay.store.routes import (
    ROUTE_FORMAT,
    ROUTE_VERSION,
    read_route_file,
    route_path,
    seed_bundled_routes,
)

REPO = Path(__file__).resolve().parents[2]
SHIPPED = REPO / "assets" / "routes"


def starter(name: str) -> dict:
    return {
        "format": ROUTE_FORMAT,
        "version": ROUTE_VERSION,
        "name": name,
        "map": "altgard",
        "mapSize": [512, 384],
        "markers": [{"x": 10, "y": 20, "text": "Start"}, {"x": 30, "y": 40, "text": "End"}],
        "style": {"color": "#f2b544", "width": 3},
    }


@pytest.fixture
def shipped(test_maps_root: Callable[[], Path]) -> Iterator[Path]:
    folder = test_maps_root().parent / "routes"
    atomic_write_json(folder / "First.json", starter("First"))
    atomic_write_json(folder / "Second.json", starter("Second"))
    yield folder
    for path in folder.glob("*.json"):
        path.unlink()


def start(dirs: DataDirs) -> Backend:
    backend = Backend(dirs)
    backend.shutdown()  # flushes state.json
    return backend


def listed(dirs: DataDirs) -> list[str]:
    return sorted(p.stem for p in dirs.routes.glob("*.json"))


def test_the_shipped_routes_are_valid_routes_on_a_bundled_map() -> None:
    files = sorted(SHIPPED.glob("*.json"))
    assert len(files) == 3
    for path in files:
        doc = read_route_file(path)
        assert doc["map"] in BUNDLED_MAP_IDS
        manifest = json.loads((REPO / "assets" / "maps" / doc["map"] / "manifest.json").read_text())
        assert doc["mapSize"] == manifest["size"]
        assert doc["markers"]
        # The bytes a save would write, so the first edit's .bak is not a reformatted copy.
        assert path.read_text(encoding="utf-8") == json.dumps(doc, ensure_ascii=False, indent=2)


def test_a_new_install_starts_with_the_starter_routes(
    qapp: QApplication, dirs: DataDirs, shipped: Path
) -> None:
    backend = start(dirs)

    assert listed(dirs) == ["First", "Second"]
    assert [r["label"] for r in json.loads(backend.getState())["routes"]] == ["First", "Second"]
    assert json.loads(dirs.state.read_text())["seeded_routes"] == ["First", "Second"]


def test_a_deleted_starter_route_does_not_come_back(
    qapp: QApplication, dirs: DataDirs, shipped: Path
) -> None:
    start(dirs)
    route_path(dirs, "First").unlink()

    start(dirs)

    assert listed(dirs) == ["Second"]


def test_a_route_already_on_the_id_is_left_alone(dirs: DataDirs, shipped: Path) -> None:
    mine = starter("Mine")
    atomic_write_json(route_path(dirs, "First"), mine)

    assert seed_bundled_routes(dirs, ()) == ["First", "Second"]
    assert read_route_file(route_path(dirs, "First"))["name"] == "Mine"


def test_a_starter_route_added_later_reaches_an_existing_install(
    dirs: DataDirs, shipped: Path
) -> None:
    assert seed_bundled_routes(dirs, ("First",)) == ["Second"]
    assert listed(dirs) == ["Second"]


def test_a_broken_starter_route_is_skipped_and_tried_again(dirs: DataDirs, shipped: Path) -> None:
    (shipped / "First.json").write_text("{", encoding="utf-8")

    assert seed_bundled_routes(dirs, ()) == ["Second"]
    assert listed(dirs) == ["Second"]
