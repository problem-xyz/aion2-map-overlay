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
    SHIPPED_DIGESTS,
    backup_path,
    parse_shipped_digests,
    read_route_file,
    record_shipped_digests,
    route_path,
    save_route,
    seed_bundled_routes,
)

REPO = Path(__file__).resolve().parents[2]
SHIPPED = REPO / "assets" / "routes"


def starter(name: str, last: str = "End") -> dict:
    return {
        "format": ROUTE_FORMAT,
        "version": ROUTE_VERSION,
        "name": name,
        "map": "altgard",
        "mapSize": [512, 384],
        "markers": [{"x": 10, "y": 20, "text": "Start"}, {"x": 30, "y": 40, "text": last}],
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
    (folder / SHIPPED_DIGESTS).unlink(missing_ok=True)


def release(folder: Path) -> None:
    """What a release does to the bundled folder: record the versions it ships."""
    digests = folder / SHIPPED_DIGESTS
    text = digests.read_text(encoding="utf-8") if digests.exists() else ""
    digests.write_text(record_shipped_digests(folder, text), encoding="utf-8")


def ship_new_version(folder: Path) -> None:
    """The next release changes First, the way a fixed route would be."""
    atomic_write_json(folder / "First.json", starter("First", last="Fixed end"))


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

    assert seed_bundled_routes(dirs, ()).handled == ["First", "Second"]
    assert read_route_file(route_path(dirs, "First"))["name"] == "Mine"


def test_a_starter_route_added_later_reaches_an_existing_install(
    dirs: DataDirs, shipped: Path
) -> None:
    assert seed_bundled_routes(dirs, ("First",)).handled == ["Second"]
    assert listed(dirs) == ["Second"]


def test_a_broken_starter_route_is_skipped_and_tried_again(dirs: DataDirs, shipped: Path) -> None:
    (shipped / "First.json").write_text("{", encoding="utf-8")

    assert seed_bundled_routes(dirs, ()).handled == ["Second"]
    assert listed(dirs) == ["Second"]


def test_an_untouched_starter_route_gets_the_new_version(
    qapp: QApplication, dirs: DataDirs, shipped: Path
) -> None:
    release(shipped)
    start(dirs)
    old = route_path(dirs, "First").read_bytes()
    ship_new_version(shipped)
    release(shipped)

    backend = Backend(dirs)
    notices: list[dict] = []
    backend.notify.connect(lambda raw: notices.append(json.loads(raw)))
    backend.getState()  # the first getState drains the start-up notices
    backend.shutdown()

    assert read_route_file(route_path(dirs, "First"))["markers"][1]["text"] == "Fixed end"
    assert backup_path(dirs, "First").read_bytes() == old
    assert [n["params"] for n in notices if n["code"] == "route.starters_updated"] == [
        {"names": "First"}
    ]


def test_an_update_needs_no_release_after_the_one_the_user_has(
    dirs: DataDirs, shipped: Path
) -> None:
    """The new version itself need not be recorded yet: only the one being replaced."""
    release(shipped)
    seed_bundled_routes(dirs, ())
    ship_new_version(shipped)

    assert seed_bundled_routes(dirs, ("First", "Second")).updated == ["First"]


def test_a_starter_route_the_user_edited_is_left_alone(dirs: DataDirs, shipped: Path) -> None:
    release(shipped)
    seed_bundled_routes(dirs, ())
    save_route(dirs, "First", starter("First", last="My own end"))
    ship_new_version(shipped)
    release(shipped)

    assert seed_bundled_routes(dirs, ("First", "Second")).updated == []
    assert read_route_file(route_path(dirs, "First"))["markers"][1]["text"] == "My own end"


def test_a_route_of_the_users_own_on_the_id_is_not_replaced(dirs: DataDirs, shipped: Path) -> None:
    release(shipped)
    atomic_write_json(route_path(dirs, "First"), starter("Mine"))
    ship_new_version(shipped)

    assert seed_bundled_routes(dirs, ()).updated == []
    assert read_route_file(route_path(dirs, "First"))["name"] == "Mine"


def test_a_deleted_starter_route_stays_deleted_when_a_new_version_ships(
    dirs: DataDirs, shipped: Path
) -> None:
    release(shipped)
    seed_bundled_routes(dirs, ())
    route_path(dirs, "First").unlink()
    ship_new_version(shipped)
    release(shipped)

    result = seed_bundled_routes(dirs, ("First", "Second"))
    assert (result.handled, result.updated) == ([], [])
    assert listed(dirs) == ["Second"]


def test_a_starter_route_already_up_to_date_is_not_rewritten(dirs: DataDirs, shipped: Path) -> None:
    release(shipped)
    seed_bundled_routes(dirs, ())

    assert seed_bundled_routes(dirs, ("First", "Second")).updated == []
    assert not backup_path(dirs, "First").exists()


def test_the_shipped_digests_name_only_routes_that_ship() -> None:
    """A renamed or removed starter route would leave its digests pointing at nothing."""
    digests = parse_shipped_digests((SHIPPED / SHIPPED_DIGESTS).read_text(encoding="utf-8"))
    assert digests
    assert set(digests) <= {p.stem for p in SHIPPED.glob("*.json")}
    assert all(len(d) == 64 for ids in digests.values() for d in ids)


def test_recording_a_release_twice_adds_nothing(shipped: Path) -> None:
    release(shipped)
    text = (shipped / SHIPPED_DIGESTS).read_text(encoding="utf-8")

    assert record_shipped_digests(shipped, text) == text
    assert len(text.splitlines()) == 2
