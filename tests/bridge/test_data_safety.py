"""Damaged data and oversized input, through the real Backend rather than the store alone.

The start-up half is the one that matters most: a user whose old data is damaged in some way
nobody anticipated must still get a working app, told what happened, instead of a process that
exits before any window appears. So the layouts below are broken the ways a disk actually
breaks -- a file where a directory should be, a file another program holds open, JSON that is
not JSON -- and each test asserts that Backend comes up and answers getState().
"""

import json
import logging
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import legacy
from map_overlay.store.images import imwrite
from map_overlay.store.routes import (
    MAX_MARKERS,
    MAX_ROUTE_FILE_BYTES,
    backup_path,
    new_route_doc,
    route_path,
    validate_route,
)

Notices = list[dict[str, Any]]
Start = Callable[[], tuple[Backend, Notices]]


@pytest.fixture
def start(qapp: QApplication, dirs: DataDirs) -> Iterator[Start]:
    """Build a Backend on `dirs` and collect its notices, the queued start-up ones included."""
    made: list[Backend] = []

    def build() -> tuple[Backend, Notices]:
        backend = Backend(dirs)
        made.append(backend)
        notices: Notices = []
        backend.notify.connect(lambda raw: notices.append(json.loads(raw)))
        state = json.loads(backend.getState())  # the first getState drains start-up notices
        assert "routes" in state
        return backend, notices

    yield build
    for backend in made:
        backend.shutdown()


def _v2_route(dirs: DataDirs, gradient: Callable[..., np.ndarray], name: str = "old") -> Path:
    """A version 2 route: a folder holding the map screenshot and a PNG with arrows on it."""
    folder = dirs.routes / name
    imwrite(folder / "reference.png", gradient(64, 48))
    (folder / "overlay.png").write_bytes(b"arrows painted on a screenshot")
    return folder


def _codes(notices: Notices) -> list[str]:
    return [n["code"] for n in notices]


def _migration_failed(notices: Notices, left_in: Path) -> None:
    """Exactly one failure notice, naming the folder that still holds what was not moved."""
    failed = [n for n in notices if n["code"] == "data.migration_failed"]
    assert failed == [
        {
            "level": "warning",
            "code": "data.migration_failed",
            "params": {"path": str(left_in)},
            "text": failed[0]["text"],
        }
    ]
    # No "restart and it is moved": the pre-userdata move is never tried again, and only some
    # of the version 2 failures are.
    assert failed[0]["text"] == (
        f"Some of your data could not be moved and is still in {left_in}. "
        "The log names the file that stopped it."
    )


def _traceback_logged(
    caplog: pytest.LogCaptureFixture, what: str = "migrating the version 2 layout"
) -> None:
    logged = [r for r in caplog.records if r.levelno >= logging.ERROR and r.exc_info]
    assert [r.getMessage() for r in logged] == [f"{what} failed"]


# --- start-up over a damaged legacy layout -------------------------------------------------


def test_legacy_routes_being_a_file_does_not_stop_start_up(
    start: Start,
    dirs: DataDirs,
    gradient: Callable[..., np.ndarray],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _v2_route(dirs, gradient)
    dirs.legacy.rmdir()
    dirs.legacy.write_text("a file where legacy_routes/ should be", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        _, notices = start()

    _migration_failed(notices, dirs.routes)
    _traceback_logged(caplog)
    assert "legacy.routes_moved" not in _codes(notices)


def test_a_file_in_the_way_inside_legacy_routes_does_not_stop_start_up(
    start: Start,
    dirs: DataDirs,
    gradient: Callable[..., np.ndarray],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _v2_route(dirs, gradient)
    (dirs.legacy / "old").write_text("a file where legacy_routes/old/ should go", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        _, notices = start()

    _migration_failed(notices, dirs.routes)
    _traceback_logged(caplog)
    assert (dirs.legacy / "old").is_file()  # what was in the way is not deleted to make room


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows refuses to move an open file")
def test_a_screenshot_held_open_by_another_program_does_not_stop_start_up(
    start: Start,
    dirs: DataDirs,
    gradient: Callable[..., np.ndarray],
    caplog: pytest.LogCaptureFixture,
) -> None:
    reference = _v2_route(dirs, gradient) / "reference.png"

    with reference.open("rb"), caplog.at_level(logging.ERROR):
        _, notices = start()

    _migration_failed(notices, dirs.routes)
    _traceback_logged(caplog)
    assert reference.is_file()


def _named_v2_route(dirs: DataDirs, gradient: Callable[..., np.ndarray]) -> Path:
    """A version 2 route named "Old route" by its route.json, unlike the folder it is in."""
    folder = _v2_route(dirs, gradient)
    (folder / "route.json").write_text('{"label": "Old route"}', encoding="utf-8")
    return folder


def _moved_once(dirs: DataDirs, notices: Notices, folder: Path) -> None:
    """The whole folder went to legacy_routes/ in one piece, and the user was told once."""
    moved = [n["params"] for n in notices if n["code"] == "legacy.routes_moved"]
    assert moved == [{"names": "Old route"}]
    assert (dirs.legacy / "old" / "overlay.png").is_file()
    assert (dirs.legacy / "old" / "reference.png").is_file()  # kept: a user's screenshot
    assert not folder.exists()
    assert not (dirs.maps / "old").exists(), "a screenshot is no longer turned into a map"


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows refuses to move an open file")
def test_a_screenshot_held_open_is_moved_on_the_next_start(
    start: Start, dirs: DataDirs, gradient: Callable[..., np.ndarray]
) -> None:
    # Windows copies the folder and then refuses to delete the open original. The copy left
    # in legacy_routes/ is replaced, not kept beside a second one, when the next start moves
    # the original for real.
    folder = _named_v2_route(dirs, gradient)
    with (folder / "reference.png").open("rb"):
        start()
        assert (folder / "reference.png").is_file()

    _, notices = start()

    _moved_once(dirs, notices, folder)


def test_a_folder_stopped_by_a_file_named_legacy_routes_moves_once_that_file_is_gone(
    start: Start, dirs: DataDirs, gradient: Callable[..., np.ndarray]
) -> None:
    folder = _named_v2_route(dirs, gradient)
    dirs.legacy.rmdir()
    dirs.legacy.write_text("a file where legacy_routes/ should be", encoding="utf-8")
    start()
    assert (folder / "reference.png").is_file()
    dirs.legacy.unlink()

    _, notices = start()

    _moved_once(dirs, notices, folder)


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(lambda p: p.write_bytes(b"\x00{this is not json"), id="corrupt-json"),
        pytest.param(lambda p: p.write_text('{"label": 42}', encoding="utf-8"), id="label-number"),
        pytest.param(lambda p: p.write_text('{"label": null}', encoding="utf-8"), id="label-null"),
        pytest.param(lambda p: p.mkdir(), id="unreadable"),  # opening a directory fails
    ],
)
def test_a_damaged_route_json_still_migrates_under_the_folder_name(
    start: Start,
    dirs: DataDirs,
    gradient: Callable[..., np.ndarray],
    damage: Callable[[Path], None],
) -> None:
    """route.json only ever supplied the label, so losing it costs the name and nothing else.

    A label that was a number used to reach the start-up notice as one, where joining the
    names raised TypeError out of Backend() itself.
    """
    damage(_v2_route(dirs, gradient) / "route.json")

    _, notices = start()

    moved = [n for n in notices if n["code"] == "legacy.routes_moved"]
    assert [n["params"] for n in moved] == [{"names": "old"}]
    assert "data.migration_failed" not in _codes(notices)
    assert (dirs.legacy / "old" / "overlay.png").is_file()


def test_the_loose_map_reference_of_the_oldest_layout_is_left_where_it_is(
    start: Start, dirs: DataDirs, gradient: Callable[..., np.ndarray]
) -> None:
    # It used to become the map "default". The maps ship with the app now, so the file is
    # neither a map nor in the way -- and not ours to delete.
    imwrite(dirs.root / "map_reference.png", gradient(64, 48))

    backend, notices = start()

    assert (dirs.root / "map_reference.png").is_file()
    assert [m["id"] for m in backend._routes.maps()] == ["altgard", "verteron"]
    assert not (dirs.maps / "default").exists()
    assert not [n for n in notices if n["code"].startswith(("legacy.", "data."))]


def test_a_migration_that_raises_names_the_routes_folder(
    start: Start, dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    def held_open(_dirs: DataDirs) -> list[str]:
        raise PermissionError("the file is held open by another program")

    monkeypatch.setattr(legacy, "migrate_v2_layout", held_open)

    _, notices = start()

    _migration_failed(notices, dirs.routes)


def test_a_failure_app_py_queues_arrives_as_a_warning(start: Start, dirs: DataDirs) -> None:
    # app.py reports the dev-layout migration through queue_notice, before any page connects;
    # the level it passes must survive the queue, or the failure would read as news.
    backend, notices = start()
    backend.queue_notice("data.migration_failed", "warning", path=str(dirs.root))

    backend.getState()

    assert [(n["level"], n["code"], n["params"]) for n in notices] == [
        ("warning", "data.migration_failed", {"path": str(dirs.root)})
    ]


# --- the import limits, as the user meets them ---------------------------------------------


def test_importing_an_oversized_route_file_says_so(
    start: Start, dirs: DataDirs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "huge.json"
    path.write_bytes(b" " * (MAX_ROUTE_FILE_BYTES + 1))
    backend, notices = start()
    monkeypatch.setattr(backend._dialogs, "open_json", lambda caption: str(path))

    backend.importRouteFile()

    assert notices[-1]["level"] == "error"
    assert notices[-1]["code"] == "route.file_too_large"
    assert notices[-1]["params"] == {"limit": 5}
    assert notices[-1]["text"] == "That file is too large to be a route (limit 5 MB)."
    assert list(dirs.routes.glob("*.json")) == []


@pytest.mark.parametrize(
    "text",
    [
        pytest.param('{"format": "map-overlay-route", "version": [1]}', id="version-list"),
        pytest.param("[" * 100_000 + "]" * 100_000, id="nested-too-deep"),
    ],
)
def test_importing_a_crafted_route_file_says_it_is_not_a_route(
    start: Start, dirs: DataDirs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    # TypeError and RecursionError used to leave the slot past both of its handlers.
    path = tmp_path / "crafted.json"
    path.write_text(text, encoding="utf-8")
    backend, notices = start()
    monkeypatch.setattr(backend._dialogs, "open_json", lambda caption: str(path))

    backend.importRouteFile()

    assert (notices[-1]["level"], notices[-1]["code"]) == ("error", "route.file_invalid")
    assert list(dirs.routes.glob("*.json")) == []


# --- the same limit on routes/, where files also arrive by hand ----------------------------


def _padded_route(path: Path, size: int) -> None:
    """A valid route padded with trailing whitespace, which JSON allows, to exactly `size`."""
    body = json.dumps(new_route_doc("Huge", "altgard", [512, 384])).encode("utf-8")
    path.write_bytes(body + b" " * (size - len(body)))


def test_a_route_file_over_the_limit_in_routes_is_not_listed_and_is_reported_once(
    start: Start, dirs: DataDirs
) -> None:
    _padded_route(route_path(dirs, "huge"), 6 * 1024 * 1024)
    backend, notices = start()

    state = json.loads(backend.getState())

    assert state["routes"] == []
    skipped = [n for n in notices if n["code"] == "route.file_skipped_too_large"]
    assert [(n["level"], n["params"]) for n in skipped] == [
        ("warning", {"file": "huge.json", "limit": 5})
    ]
    assert skipped[0]["text"] == (
        "The route file huge.json is larger than 5 MB, so it is not in the list."
    )
    assert route_path(dirs, "huge").is_file(), "left where it is"


def test_a_crafted_route_file_in_routes_does_not_take_the_state_down(
    start: Start, dirs: DataDirs
) -> None:
    route_path(dirs, "crafted").write_text(
        '{"format": "map-overlay-route", "version": null}', encoding="utf-8"
    )
    backend, notices = start()  # start() itself asserts getState() answers

    assert json.loads(backend.getState())["routes"] == []
    assert [n["params"] for n in notices if n["code"] == "route.file_skipped"] == [
        {"file": "crafted.json"}
    ]


# --- nothing the app writes is a file it would refuse --------------------------------------


def _file_bytes(doc: dict[str, Any], *, indented: bool = True) -> bytes:
    """The file of doc: as the app writes it, or with no whitespace, as another tool might."""
    doc = validate_route(doc)
    if indented:
        return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _route_with_captions(
    map_id: str, size: list[int], file_bytes: int, *, indented: bool = True
) -> dict[str, Any]:
    """A route at the marker cap whose captions bring its file to just under `file_bytes`."""
    doc = new_route_doc("Long captions", map_id, size)
    doc["markers"] = [{"x": i % 64, "y": i % 48, "text": ""} for i in range(MAX_MARKERS)]
    bare = len(_file_bytes(doc, indented=indented))
    caption = "a" * ((file_bytes - bare) // MAX_MARKERS)
    for marker in doc["markers"]:
        marker["text"] = caption
    return doc


def test_the_editor_cannot_save_a_route_larger_than_the_app_reads(
    start: Start, dirs: DataDirs
) -> None:
    backend, notices = start()
    doc = _route_with_captions("altgard", [512, 384], MAX_ROUTE_FILE_BYTES + 64 * 1024)

    reply = json.loads(backend.saveRoute(json.dumps({"id": None, "doc": doc})))

    assert (reply["ok"], reply["code"], reply["params"]) == (False, "route.too_large", {"limit": 5})
    assert (notices[-1]["level"], notices[-1]["code"]) == ("error", "route.too_large")
    assert list(dirs.routes.iterdir()) == []


def test_a_route_saved_near_the_limit_exports_and_imports_again(
    start: Start, dirs: DataDirs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, notices = start()
    # On the map's own size: a rescale notice would otherwise land among the three below.
    doc = _route_with_captions("altgard", [512, 384], MAX_ROUTE_FILE_BYTES - 64 * 1024)
    exported = tmp_path / "exported.json"
    monkeypatch.setattr(backend._dialogs, "save_json", lambda caption, suggested: str(exported))
    monkeypatch.setattr(backend._dialogs, "open_json", lambda caption: str(exported))

    reply = json.loads(backend.saveRoute(json.dumps({"id": None, "doc": doc})))
    backend.exportRoute(reply["id"])
    backend.importRouteFile()

    codes = _codes(notices)
    assert codes[-3:] == ["route.saved", "route.exported", "route.imported.file"]
    assert route_path(dirs, reply["id"]).stat().st_size <= MAX_ROUTE_FILE_BYTES
    assert exported.read_bytes() == route_path(dirs, reply["id"]).read_bytes()
    assert len(json.loads(backend.getState())["routes"]) == 2


def _compact_route_that_indents_past_the_limit(map_id: str) -> bytes:
    """A route written without whitespace, under the limit, that the app would write past it.

    The app writes routes indented, which adds some fifty bytes a point: a file made
    elsewhere can pass every read check and still come out too large when the app saves it.
    """
    doc = _route_with_captions(map_id, [512, 384], MAX_ROUTE_FILE_BYTES, indented=False)
    compact = _file_bytes(doc, indented=False)
    assert len(compact) <= MAX_ROUTE_FILE_BYTES < len(_file_bytes(doc))
    return compact


def test_importing_a_file_the_app_would_save_past_the_limit_says_so(
    start: Start, dirs: DataDirs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "compact.json"
    path.write_bytes(_compact_route_that_indents_past_the_limit("altgard"))
    backend, notices = start()
    monkeypatch.setattr(backend._dialogs, "open_json", lambda caption: str(path))

    backend.importRouteFile()

    assert (notices[-1]["level"], notices[-1]["code"]) == ("error", "route.too_large")
    # A cause, not an instruction: this route never got into the app, so there is nothing in
    # the editor to shorten.
    assert notices[-1]["text"] == (
        "That route is too large: its file would be over 5 MB, and the app cannot open a file "
        "that size. Its points carry too much text."
    )
    assert list(dirs.routes.glob("*.json")) == []


def test_exporting_a_route_the_app_would_write_past_the_limit_says_so(
    start: Start, dirs: DataDirs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A compact file put in routes/ by hand reads fine, and is written indented on export.
    route_path(dirs, "compact").write_bytes(_compact_route_that_indents_past_the_limit("altgard"))
    exported = tmp_path / "exported.json"
    backend, notices = start()
    monkeypatch.setattr(backend._dialogs, "save_json", lambda caption, suggested: str(exported))

    backend.exportRoute("compact")

    assert (notices[-1]["level"], notices[-1]["code"]) == ("error", "route.too_large")
    assert not exported.exists()


# --- the backup a save leaves behind, as the panel sees it ---------------------------------


def test_a_backup_never_reaches_the_route_list(
    start: Start, dirs: DataDirs, caplog: pytest.LogCaptureFixture
) -> None:
    backend, notices = start()
    for name in ("First", "Second"):
        backend._routes.save_route("gold", new_route_doc(name, "altgard", [512, 384]))
    orphan = new_route_doc("Orphan", "altgard", [512, 384])
    backup_path(dirs, "orphan").write_text(json.dumps(orphan), encoding="utf-8")
    assert backup_path(dirs, "gold").is_file()
    shown = len(notices)

    with caplog.at_level(logging.WARNING):
        state = json.loads(backend.getState())

    assert [(r["id"], r["label"]) for r in state["routes"]] == [("gold", "Second")]
    # Not even read: a .bak taken for a route would be reported as a broken one every time the
    # panel's state is sent.
    assert not [r for r in caplog.records if ".bak" in r.getMessage()]
    assert notices[shown:] == []
