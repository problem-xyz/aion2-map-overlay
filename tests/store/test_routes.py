"""Route documents: validation, rescaling, and the files under routes/.

validate_route is the only gate between an untrusted document -- an imported file, a share code
pasted from a chat -- and the rest of the app, so every case here asserts the dotted code the UI
would translate rather than merely that something was raised.
"""

import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from map_overlay.core.errors import RouteError
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes as routes_module
from map_overlay.store.maps import ThumbCache
from map_overlay.store.naming import unique_route_id
from map_overlay.store.routes import (
    MAX_MARKERS,
    MAX_ROUTE_FILE_BYTES,
    ROUTE_FORMAT,
    ROUTE_VERSION,
    SkippedRoutes,
    backup_path,
    delete_route,
    export_route,
    list_routes,
    load_route,
    read_route_file,
    rescale_route,
    route_path,
    save_route,
    validate_route,
)

# A known defect, pinned here until it is fixed:
# validate_route runs int(doc.get("version", 0)) before it looks at the type, so a version that
# is not a number escapes as a bare ValueError or TypeError instead of a RouteError the UI can
# turn into a toast, and a fractional version is truncated into acceptance.
VERSION_TYPE_DEFECT = (
    "validate_route coerces version with int() before checking its type: a non-numeric version "
    "raises ValueError/TypeError instead of RouteError, and 1.5 is accepted"
)


def make_route(**overrides: Any) -> dict[str, Any]:
    """A valid route document, with individual fields replaced per test."""
    doc: dict[str, Any] = {
        "format": ROUTE_FORMAT,
        "version": ROUTE_VERSION,
        "name": "Gold route",
        "map": "elysea",
        "mapSize": [4096, 4096],
        "markers": [],
        "style": {"color": "#f2b544", "width": 3},
    }
    doc.update(overrides)
    return doc


def test_a_document_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(RouteError) as caught:
        validate_route(["not", "a", "route"])
    assert caught.value.code == "route.invalid.not_object"


def test_a_foreign_format_is_refused() -> None:
    with pytest.raises(RouteError) as caught:
        validate_route(make_route(format="map-overlay-objects"))
    assert caught.value.code == "route.invalid.format"


def test_another_version_is_refused_and_reports_the_version_it_saw() -> None:
    with pytest.raises(RouteError) as caught:
        validate_route(make_route(version=2))
    assert caught.value.code == "route.invalid.version"
    assert caught.value.params == {"version": 2}


def test_a_numeric_string_version_is_accepted() -> None:
    # The documented route format allows it: 1, "1" and 1.0 all pass the int() comparison.
    assert validate_route(make_route(version="1"))["version"] == ROUTE_VERSION


@pytest.mark.xfail(reason=VERSION_TYPE_DEFECT, strict=True)
def test_a_non_numeric_version_is_a_route_error() -> None:
    with pytest.raises(RouteError) as caught:
        validate_route(make_route(version="x"))
    assert caught.value.code == "route.invalid.version"


@pytest.mark.xfail(reason=VERSION_TYPE_DEFECT, strict=True)
def test_a_null_version_is_a_route_error() -> None:
    with pytest.raises(RouteError) as caught:
        validate_route(make_route(version=None))
    assert caught.value.code == "route.invalid.version"


@pytest.mark.xfail(reason=VERSION_TYPE_DEFECT, strict=True)
def test_a_fractional_version_is_a_route_error() -> None:
    with pytest.raises(RouteError) as caught:
        validate_route(make_route(version=1.5))
    assert caught.value.code == "route.invalid.version"


def test_coordinates_are_rounded_to_two_decimals() -> None:
    doc = validate_route(make_route(markers=[{"x": 10.126, "y": -3.4449}]))
    assert doc["markers"][0]["x"] == 10.13
    assert doc["markers"][0]["y"] == -3.44


def test_a_marker_without_usable_coordinates_is_refused() -> None:
    with pytest.raises(RouteError) as caught:
        validate_route(make_route(markers=[{"x": 1.0}]))
    assert caught.value.code == "route.invalid.marker_coords"


@pytest.mark.parametrize("color", ["red", "#12345", "#f2b5442", "f2b544", "", None, 65280])
def test_a_marker_colour_that_is_not_hex_is_dropped(color: Any) -> None:
    # A marker with no colour of its own is drawn in the route colour, so dropping the field is
    # the normalisation, not an error.
    doc = validate_route(make_route(markers=[{"x": 1, "y": 2, "color": color}]))
    assert "color" not in doc["markers"][0]


@pytest.mark.parametrize("icon", ["main", "side"])
def test_a_quest_icon_is_kept(icon: str) -> None:
    doc = validate_route(make_route(markers=[{"x": 1, "y": 2, "icon": icon}]))
    assert doc["markers"][0]["icon"] == icon


@pytest.mark.parametrize("icon", ["boss", "", None, 1, "MAIN"])
def test_an_icon_that_is_not_a_quest_one_is_dropped(icon: Any) -> None:
    # like a colour that is not hex: a newer or a hand-edited file loses the field, not the route
    doc = validate_route(make_route(markers=[{"x": 1, "y": 2, "icon": icon}]))
    assert "icon" not in doc["markers"][0]


def test_a_hex_marker_colour_is_kept_as_written() -> None:
    doc = validate_route(make_route(markers=[{"x": 1, "y": 2, "color": "#A1B2C3"}]))
    assert doc["markers"][0]["color"] == "#A1B2C3"


@pytest.mark.parametrize(
    ("given", "expected"), [(-5, 1), (0, 1), (1, 1), (7, 7), (12, 12), (13, 12), (9999, 12)]
)
def test_style_width_is_clamped_to_the_documented_range(given: int, expected: int) -> None:
    # 1..12 is the range the route format documents, and the editor's slider's.
    doc = validate_route(make_route(style={"color": "#f2b544", "width": given}))
    assert doc["style"]["width"] == expected


def test_a_width_that_is_not_a_number_leaves_the_default_in_place() -> None:
    doc = validate_route(make_route(style={"color": "#f2b544", "width": "thick"}))
    assert doc["style"]["width"] == 3


def test_more_markers_than_the_cap_are_refused() -> None:
    # MAX_MARKERS is 2000, the cap the route format documents. It exists because a
    # share code arrives from the clipboard: an unbounded route would be allocated before
    # anything could reject it.
    markers = [{"x": i, "y": i} for i in range(MAX_MARKERS + 1)]
    with pytest.raises(RouteError) as caught:
        validate_route(make_route(markers=markers))
    assert caught.value.code == "route.too_many_markers"
    assert caught.value.params == {"limit": MAX_MARKERS}


def test_a_route_of_exactly_the_cap_is_accepted() -> None:
    doc = validate_route(make_route(markers=[{"x": i, "y": i} for i in range(MAX_MARKERS)]))
    assert len(doc["markers"]) == MAX_MARKERS


def test_rescale_scales_each_axis_by_its_own_ratio() -> None:
    doc = validate_route(
        make_route(mapSize=[1000, 500], markers=[{"x": 250, "y": 100}, {"x": 999.5, "y": 0}])
    )

    out = rescale_route(doc, (2000, 2000))

    assert out["mapSize"] == [2000, 2000]
    assert [(m["x"], m["y"]) for m in out["markers"]] == [(500.0, 400.0), (1999.0, 0.0)]


def test_rescale_leaves_the_document_it_was_given_alone() -> None:
    doc = validate_route(make_route(mapSize=[1000, 500], markers=[{"x": 250, "y": 100}]))

    rescale_route(doc, (2000, 2000))

    assert doc["mapSize"] == [1000, 500]
    assert doc["markers"][0]["x"] == 250.0


def test_rescale_to_the_same_size_is_a_no_op() -> None:
    doc = validate_route(make_route(mapSize=[1024, 768], markers=[{"x": 12, "y": 34}]))
    assert rescale_route(doc, (1024, 768)) is doc


def test_rescale_refuses_a_zero_dimension_instead_of_dividing_by_it() -> None:
    doc = validate_route(make_route(mapSize=[0, 0], markers=[{"x": 12, "y": 34}]))
    assert rescale_route(doc, (800, 600)) is doc


def test_a_route_survives_a_save_and_load_round_trip(dirs: DataDirs) -> None:
    doc = make_route(
        markers=[{"x": 12.345, "y": 6.7, "text": "Talk to the guard", "color": "#00ff88"}]
    )

    saved = save_route(dirs, "gold", doc)
    loaded = load_route(dirs, "gold")

    assert loaded == saved
    assert json.loads(route_path(dirs, "gold").read_text(encoding="utf-8")) == saved


def test_loading_a_route_that_was_never_saved_is_not_found(dirs: DataDirs) -> None:
    with pytest.raises(RouteError) as caught:
        load_route(dirs, "missing")
    assert caught.value.code == "route.not_found"


def test_delete_removes_a_route_that_lives_in_the_routes_directory(dirs: DataDirs) -> None:
    save_route(dirs, "gold", make_route())

    delete_route(dirs, "gold")

    assert not route_path(dirs, "gold").exists()


def test_delete_refuses_an_id_that_climbs_out_of_the_routes_directory(dirs: DataDirs) -> None:
    # Path traversal: the id reaches the store from the UI, and "../settings" would otherwise
    # resolve to a file outside the one directory this function is allowed to delete from.
    outside = dirs.root / "settings.json"
    outside.write_text("{}", encoding="utf-8")
    # The id really does aim at that file: the guard is what saves it, not a path that missed.
    assert route_path(dirs, "../settings").resolve() == outside.resolve()

    delete_route(dirs, "../settings")

    assert outside.exists()


def test_delete_refuses_an_absolute_id(tmp_path: Path, dirs: DataDirs) -> None:
    # An absolute id wins the join outright -- Path("...routes") / "D:/x.json" is "D:/x.json" --
    # so the guard, not the join, is what keeps the deletion inside routes/.
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}", encoding="utf-8")
    assert route_path(dirs, str(tmp_path / "elsewhere")).resolve() == outside.resolve()

    delete_route(dirs, str(tmp_path / "elsewhere"))

    assert outside.exists()


# list_routes runs on every state rebuild, so what it does with a bad file happens over and over:
# these call it several times and count what came out, not only what came out first.


def listed(dirs: DataDirs, skipped: SkippedRoutes) -> list[str]:
    return [r["id"] for r in list_routes(dirs, {}, ThumbCache(), skipped)]


def write_at(path: Path, text: str, mtime_ns: int) -> None:
    """Write text with a set modification time, which is how SkippedRoutes tells versions apart.

    Two writes inside one clock tick can share an mtime, so a test that relied on the real
    clock to tell an edit from the original would pass or fail by chance.
    """
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(mtime_ns, mtime_ns))


def route_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "map_overlay.store.routes"]


def test_a_route_file_that_is_not_json_is_moved_aside_and_reported_once(
    dirs: DataDirs, caplog: pytest.LogCaptureFixture
) -> None:
    save_route(dirs, "good", make_route())
    broken = route_path(dirs, "broken")
    broken.write_text('{"format": "map-overlay-route"', encoding="utf-8")
    skipped = SkippedRoutes()

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert listed(dirs, skipped) == ["good"]

    [notice] = skipped.take()
    assert notice.code == "route.file_corrupt"
    assert notice.params["file"] == "broken.json"
    backup = dirs.routes / notice.params["backup"]
    assert backup.read_text(encoding="utf-8") == '{"format": "map-overlay-route"'
    assert not broken.exists()
    assert skipped.take() == []
    assert len(route_warnings(caplog)) == 1
    assert not [r for r in caplog.records if r.exc_info], "a parse error needs no traceback"


def test_a_json_file_that_is_not_a_route_stays_and_is_reported_once_per_version(
    dirs: DataDirs, caplog: pytest.LogCaptureFixture
) -> None:
    newer = route_path(dirs, "newer")
    write_at(newer, json.dumps(make_route(version=ROUTE_VERSION + 1)), 1_000_000_000)
    skipped = SkippedRoutes()

    with caplog.at_level(logging.WARNING):
        assert listed(dirs, skipped) == []
        assert listed(dirs, skipped) == []

    [notice] = skipped.take()
    assert (notice.code, notice.params) == ("route.file_skipped", {"file": "newer.json"})
    assert newer.exists(), "not damaged: a newer build can still open it, so it stays put"
    assert len(route_warnings(caplog)) == 1

    write_at(newer, json.dumps(make_route(markers=[{"x": "?"}])), 2_000_000_000)
    assert listed(dirs, skipped) == []
    assert [n.code for n in skipped.take()] == ["route.file_skipped"]

    write_at(newer, json.dumps(make_route()), 3_000_000_000)
    assert listed(dirs, skipped) == ["newer"]
    assert skipped.take() == []


def test_a_route_entry_that_cannot_be_read_is_reported_once_and_left_alone(
    dirs: DataDirs,
) -> None:
    # A directory is the portable way to make reading fail with an OSError that is not
    # FileNotFoundError: PermissionError on Windows, IsADirectoryError elsewhere.
    unreadable = dirs.routes / "folder.json"
    unreadable.mkdir()
    skipped = SkippedRoutes()

    assert listed(dirs, skipped) == []
    assert listed(dirs, skipped) == []

    assert [n.params for n in skipped.take()] == [{"file": "folder.json"}]
    assert unreadable.is_dir()
    assert [p.name for p in dirs.routes.iterdir()] == ["folder.json"]


# --- the .bak a save leaves behind ----------------------------------------------------------


def test_a_saved_route_is_byte_for_byte_what_atomic_write_json_writes(
    dirs: DataDirs, tmp_path: Path
) -> None:
    # save_route serialises for itself now, to compare with the previous version; the file
    # format is frozen, so the bytes must not drift from every other JSON file the app writes.
    saved = save_route(dirs, "gold", make_route(markers=[{"x": 1, "y": 2, "text": "Café"}]))
    atomic_write_json(tmp_path / "reference.json", saved)

    assert route_path(dirs, "gold").read_bytes() == (tmp_path / "reference.json").read_bytes()


def test_a_first_save_writes_no_backup(dirs: DataDirs) -> None:
    save_route(dirs, "gold", make_route())

    assert not backup_path(dirs, "gold").exists()


def test_a_save_keeps_the_version_it_replaced_byte_for_byte(dirs: DataDirs) -> None:
    save_route(dirs, "gold", make_route(name="First"))
    first = route_path(dirs, "gold").read_bytes()

    save_route(dirs, "gold", make_route(name="Second"))

    assert backup_path(dirs, "gold").read_bytes() == first
    assert load_route(dirs, "gold")["name"] == "Second"


def test_there_is_only_ever_one_backup_the_previous_version(dirs: DataDirs) -> None:
    for name in ("First", "Second", "Third"):
        save_route(dirs, "gold", make_route(name=name))

    assert json.loads(backup_path(dirs, "gold").read_text(encoding="utf-8"))["name"] == "Second"
    assert sorted(p.name for p in dirs.routes.iterdir()) == ["gold.json", "gold.json.bak"]


def test_a_save_that_changes_nothing_leaves_the_backup_alone(dirs: DataDirs) -> None:
    # Save pressed twice: the second press must not replace the older version with a copy of
    # the current one, or the backup would be worth nothing exactly when it is wanted.
    save_route(dirs, "gold", make_route(name="First"))
    first = route_path(dirs, "gold").read_bytes()
    save_route(dirs, "gold", make_route(name="Second"))

    save_route(dirs, "gold", make_route(name="Second"))

    assert backup_path(dirs, "gold").read_bytes() == first


def test_the_backup_is_in_place_before_the_route_is_replaced(
    dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_route(dirs, "gold", make_route(name="First"))
    first = route_path(dirs, "gold").read_bytes()
    real_write = routes_module.atomic_write_bytes
    written: list[str] = []

    def write_then_fail_on_the_route(path: Path, data: bytes) -> None:
        written.append(Path(path).name)
        if Path(path) == route_path(dirs, "gold"):
            raise OSError("disk full")
        real_write(path, data)

    monkeypatch.setattr(routes_module, "atomic_write_bytes", write_then_fail_on_the_route)

    with pytest.raises(OSError):
        save_route(dirs, "gold", make_route(name="Second"))

    assert written == ["gold.json.bak", "gold.json"]
    assert backup_path(dirs, "gold").read_bytes() == first
    assert route_path(dirs, "gold").read_bytes() == first


def test_a_backup_that_cannot_be_written_fails_the_save_and_keeps_the_route(
    dirs: DataDirs,
) -> None:
    save_route(dirs, "gold", make_route(name="First"))
    first = route_path(dirs, "gold").read_bytes()
    backup_path(dirs, "gold").mkdir()  # nothing can be renamed over a directory

    with pytest.raises(OSError):
        save_route(dirs, "gold", make_route(name="Second"))

    assert route_path(dirs, "gold").read_bytes() == first


def test_deleting_a_route_deletes_its_backup(dirs: DataDirs) -> None:
    save_route(dirs, "gold", make_route(name="First"))
    save_route(dirs, "gold", make_route(name="Second"))

    delete_route(dirs, "gold")

    assert list(dirs.routes.iterdir()) == []


def test_a_route_saved_on_a_deleted_id_does_not_inherit_the_old_backup(dirs: DataDirs) -> None:
    save_route(dirs, "gold", make_route(name="Deleted"))
    save_route(dirs, "gold", make_route(name="Deleted, edited"))
    delete_route(dirs, "gold")

    save_route(dirs, "gold", make_route(name="New"))

    assert not backup_path(dirs, "gold").exists()


def test_delete_refuses_a_backup_outside_the_routes_directory(dirs: DataDirs) -> None:
    outside = dirs.root / "settings.json.bak"
    outside.write_text("{}", encoding="utf-8")

    delete_route(dirs, "../settings")

    assert outside.exists()


def test_a_new_route_does_not_take_the_id_of_an_orphaned_backup(dirs: DataDirs) -> None:
    # A .bak with no route beside it is the last copy of a route deleted by hand. A new route
    # on that id would overwrite it on its second save.
    backup_path(dirs, "gold").write_text(json.dumps(make_route()), encoding="utf-8")

    assert unique_route_id(dirs, "gold") == "gold_2"


# --- a route file the user picked -----------------------------------------------------------


def _route_file_of(path: Path, size: int) -> Path:
    """A valid route padded with trailing whitespace, which JSON allows, to exactly `size`."""
    body = json.dumps(make_route()).encode("utf-8")
    path.write_bytes(body + b" " * (size - len(body)))
    assert path.stat().st_size == size
    return path


def test_the_route_file_limit_is_five_megabytes() -> None:
    assert MAX_ROUTE_FILE_BYTES == 5 * 1024 * 1024


def test_a_route_file_of_exactly_the_limit_is_read(tmp_path: Path) -> None:
    path = _route_file_of(tmp_path / "edge.json", MAX_ROUTE_FILE_BYTES)

    assert read_route_file(path)["name"] == "Gold route"


def test_a_route_file_one_byte_over_the_limit_is_refused(tmp_path: Path) -> None:
    path = _route_file_of(tmp_path / "over.json", MAX_ROUTE_FILE_BYTES + 1)

    with pytest.raises(RouteError) as caught:
        read_route_file(path)

    assert caught.value.code == "route.file_too_large"
    assert caught.value.params == {"limit": 5}


def forbid_opening(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    """Fail the test if `path` is opened: its size alone is meant to refuse it."""
    real_open = Path.open

    def guarded_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == path:
            raise AssertionError(f"{path.name} was opened; its size alone should have refused it")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)


def test_a_route_file_over_the_limit_is_refused_without_being_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _route_file_of(tmp_path / "over.json", MAX_ROUTE_FILE_BYTES + 1)
    forbid_opening(monkeypatch, path)

    with pytest.raises(RouteError) as caught:
        read_route_file(path)
    assert caught.value.code == "route.file_too_large"


class CountedReads:
    """A file that records how many bytes each read() returned."""

    def __init__(self, f: Any, reads: list[int]) -> None:
        self._f = f
        self._reads = reads

    def __enter__(self) -> CountedReads:
        return self

    def __exit__(self, *exc: object) -> None:
        self._f.close()

    def read(self, size: int = -1) -> bytes:
        data = self._f.read(size)
        self._reads.append(len(data))
        return data


def test_a_route_file_that_holds_more_than_its_size_says_is_never_read_in_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The file grew between the stat and the read, or reports a size it does not have. The
    # read itself is bounded, so the file is refused having been read one byte past the cap,
    # not loaded whole and measured afterwards.
    path = _route_file_of(tmp_path / "grew.json", 2 * MAX_ROUTE_FILE_BYTES)
    real_stat, real_open = Path.stat, Path.open
    reads: list[int] = []

    def small_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == path:
            return SimpleNamespace(st_size=10)
        return real_stat(self, *args, **kwargs)

    def counted_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        f = real_open(self, *args, **kwargs)
        return CountedReads(f, reads) if self == path else f

    monkeypatch.setattr(Path, "stat", small_stat)
    monkeypatch.setattr(Path, "open", counted_open)

    with pytest.raises(RouteError) as caught:
        read_route_file(path)
    assert caught.value.code == "route.file_too_large"
    assert sum(reads) == MAX_ROUTE_FILE_BYTES + 1


def test_a_route_file_that_is_not_json_is_refused_with_the_parsers_reason(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(b"{not json")

    with pytest.raises(RouteError) as caught:
        read_route_file(path)
    assert caught.value.code == "route.file_invalid"
    assert "Expecting property name" in caught.value.params["reason"]


# Each of these used to get a bare exception out of the reader -- TypeError, KeyError,
# OverflowError, RecursionError -- past the handlers of the import slot, and in routes/ past
# the route list, which took the whole panel state down with it.
CRAFTED_ROUTE_FILES = [
    pytest.param(json.dumps(make_route(version=[1])), id="version-list"),
    pytest.param(json.dumps(make_route(version=None)), id="version-null"),
    pytest.param(json.dumps(make_route(mapSize={"w": 1})), id="map-size-object"),
    pytest.param(json.dumps(make_route(markers=5)), id="markers-number"),
    pytest.param(json.dumps(make_route(markers=[{"x": 10**400, "y": 1}])), id="x-past-float"),
    pytest.param(json.dumps(make_route(style={"width": 1e400})), id="width-infinite"),
    pytest.param("[" * 100_000 + "]" * 100_000, id="nested-too-deep"),
]


@pytest.mark.parametrize("text", CRAFTED_ROUTE_FILES)
def test_a_crafted_route_file_is_refused_as_not_a_route(tmp_path: Path, text: str) -> None:
    path = tmp_path / "crafted.json"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RouteError) as caught:
        read_route_file(path)
    assert caught.value.code == "route.file_invalid"
    assert caught.value.params["reason"]


def test_a_route_file_is_validated_like_any_other_route(tmp_path: Path) -> None:
    path = tmp_path / "foreign.json"
    path.write_text(json.dumps(make_route(format="map-overlay-objects")), encoding="utf-8")

    with pytest.raises(RouteError) as caught:
        read_route_file(path)
    assert caught.value.code == "route.invalid.format"


# --- the same limit on the files in routes/ -------------------------------------------------
# A file lands there by hand as well: the panel's "Open routes folder" invites it, and so does
# putting a .bak back in place of its route.


def test_a_saved_route_over_the_limit_is_refused_without_being_opened(
    dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    huge = _route_file_of(route_path(dirs, "huge"), MAX_ROUTE_FILE_BYTES + 1)
    forbid_opening(monkeypatch, huge)

    with pytest.raises(RouteError) as caught:
        load_route(dirs, "huge")
    assert (caught.value.code, caught.value.params) == ("route.file_too_large", {"limit": 5})


def test_a_route_file_over_the_limit_stays_out_of_the_list_unread_and_reported_once(
    dirs: DataDirs, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    save_route(dirs, "good", make_route())
    huge = _route_file_of(route_path(dirs, "huge"), MAX_ROUTE_FILE_BYTES + 1)
    forbid_opening(monkeypatch, huge)
    skipped = SkippedRoutes()

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert listed(dirs, skipped) == ["good"]

    [notice] = skipped.take()
    assert (notice.code, notice.params) == (
        "route.file_skipped_too_large",
        {"file": "huge.json", "limit": 5},
    )
    assert huge.stat().st_size == MAX_ROUTE_FILE_BYTES + 1, "left where it is, untouched"
    assert len(route_warnings(caplog)) == 1


def test_a_route_file_of_exactly_the_limit_is_listed(dirs: DataDirs) -> None:
    _route_file_of(route_path(dirs, "edge"), MAX_ROUTE_FILE_BYTES)
    skipped = SkippedRoutes()

    assert listed(dirs, skipped) == ["edge"]
    assert skipped.take() == []


@pytest.mark.parametrize("text", CRAFTED_ROUTE_FILES)
def test_a_crafted_route_file_in_routes_is_left_out_instead_of_failing_the_list(
    dirs: DataDirs, text: str
) -> None:
    save_route(dirs, "good", make_route())
    route_path(dirs, "crafted").write_text(text, encoding="utf-8")
    skipped = SkippedRoutes()

    assert listed(dirs, skipped) == ["good"]
    [notice] = skipped.take()
    assert notice.code in {"route.file_skipped", "route.file_corrupt"}
    assert notice.params["file"] == "crafted.json"


# --- nothing the app writes is a file it would refuse --------------------------------------
# Captions have no length limit, so a route drawn in the app can reach the file limit.


def file_size(doc: dict[str, Any]) -> int:
    """How many bytes save_route would write for doc, measured without the limit."""
    return len(json.dumps(validate_route(doc), ensure_ascii=False, indent=2).encode("utf-8"))


def route_of_size(size: int) -> dict[str, Any]:
    """A route whose file, as a save writes it, is exactly `size` bytes."""
    doc = make_route(markers=[{"x": 1, "y": 2, "text": ""}])
    doc["markers"][0]["text"] = "a" * (size - file_size(doc))
    assert file_size(doc) == size
    return doc


def test_a_route_of_exactly_the_limit_is_saved_and_reads_back(dirs: DataDirs) -> None:
    save_route(dirs, "edge", route_of_size(MAX_ROUTE_FILE_BYTES))

    assert route_path(dirs, "edge").stat().st_size == MAX_ROUTE_FILE_BYTES
    assert read_route_file(route_path(dirs, "edge")) == load_route(dirs, "edge")


def test_a_route_past_the_limit_is_not_saved_and_the_saved_one_is_kept(dirs: DataDirs) -> None:
    save_route(dirs, "gold", make_route(name="First"))
    first = route_path(dirs, "gold").read_bytes()

    with pytest.raises(RouteError) as caught:
        save_route(dirs, "gold", route_of_size(MAX_ROUTE_FILE_BYTES + 1))

    assert (caught.value.code, caught.value.params) == ("route.too_large", {"limit": 5})
    assert route_path(dirs, "gold").read_bytes() == first
    assert not backup_path(dirs, "gold").exists()


def test_a_route_past_the_limit_is_not_exported(tmp_path: Path) -> None:
    target = tmp_path / "exported.json"

    with pytest.raises(RouteError) as caught:
        export_route(validate_route(route_of_size(MAX_ROUTE_FILE_BYTES + 1)), target)

    assert caught.value.code == "route.too_large"
    assert not target.exists()


def test_an_exported_route_is_the_file_a_save_writes(dirs: DataDirs, tmp_path: Path) -> None:
    doc = save_route(dirs, "gold", make_route(markers=[{"x": 1, "y": 2, "text": "Café"}]))

    export_route(doc, tmp_path / "exported.json")

    assert (tmp_path / "exported.json").read_bytes() == route_path(dirs, "gold").read_bytes()


def test_in_order_puts_the_named_routes_first_and_keeps_the_rest_as_listed() -> None:
    listed = [{"id": i} for i in ("a", "b", "c", "d")]

    ordered = routes_module.in_order(listed, ["c", "gone", "a"])

    assert [r["id"] for r in ordered] == ["c", "a", "b", "d"]


def test_a_tile_frames_its_route_between_the_name_and_the_buttons() -> None:
    pts = np.array([[700.0, 400.0], [760.0, 430.0], [820.0, 380.0]])
    left, top, scale = routes_module.thumb_frame(pts, (1536, 1536))
    w, h = routes_module.THUMB_SIZE
    lo, hi = routes_module.THUMB_ROUTE_SPAN
    xs = (pts[:, 0] - left) * scale
    ys = (pts[:, 1] - top) * scale

    assert xs.min() > w * lo
    assert xs.max() < w * hi
    assert ys.min() > 0
    assert ys.max() < h


def test_a_tile_of_one_point_is_not_blown_up_past_the_least_span() -> None:
    _, _, scale = routes_module.thumb_frame(np.array([[500.0, 500.0]]), (1536, 1536))
    assert scale == routes_module.THUMB_SIZE[1] / routes_module.THUMB_MIN_SPAN


@pytest.mark.parametrize(
    "pts",
    [
        [[2.0, 2.0], [30.0, 6.0]],  # in a corner
        [[1500.0, 700.0], [1530.0, 760.0]],  # on the right edge
        [[10.0, 10.0], [1520.0, 1500.0]],  # across the whole map
    ],
)
def test_a_tile_never_shows_past_the_edge_of_the_map(pts: list[list[float]]) -> None:
    """Past the edge there is nothing to show: it used to be the edge's pixels smeared sideways."""
    left, top, scale = routes_module.thumb_frame(np.array(pts), (1536, 1536))
    w, h = routes_module.THUMB_SIZE

    assert left >= 0
    assert top >= 0
    assert left + w / scale <= 1536 + 1e-6
    assert top + h / scale <= 1536 + 1e-6
