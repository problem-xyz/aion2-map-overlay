"""Atomic write guarantees."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest

from map_overlay.core.fileio import (
    atomic_write_json,
    atomic_write_text,
    backup_corrupt,
    read_json_or_none,
)

# backup_corrupt stamps the copy to the second and then Path.replace()s onto that name, which
# overwrites silently. Two backups of the same file inside one second therefore leave one copy,
# not two. Only settings.load() calls it today, once per process, so nothing hits this yet.
SAME_SECOND_COLLISION_DEFECT = (
    "backup_corrupt names the copy with a one-second timestamp and replaces onto it, so a second "
    "backup of the same file within the same second silently overwrites the first"
)


def test_a_successful_write_leaves_no_temporary_file(tmp_path: Path) -> None:
    """The .tmp is an implementation detail; finding one later would look like a crashed save."""
    path = tmp_path / "route.json"
    atomic_write_json(path, {"name": "original"})
    atomic_write_json(path, {"name": "replacement"})  # overwriting must not leave one either

    assert sorted(p.name for p in tmp_path.iterdir()) == ["route.json"]
    assert json.loads(path.read_text(encoding="utf-8")) == {"name": "replacement"}


def test_the_new_bytes_reach_the_target_only_through_a_rename(tmp_path: Path) -> None:
    """Truncate-then-write would be indistinguishable from this until the process died mid-save.

    So watch the swap itself: at the moment of the rename the target must still hold the whole
    old document and the new one must be complete in the temporary file beside it.
    """
    path = tmp_path / "route.json"
    atomic_write_json(path, {"name": "original"})

    swaps: list[tuple[str, str]] = []
    real_replace = Path.replace

    def record(src: Path, dst: Path) -> Path:
        swaps.append((src.read_text(encoding="utf-8"), Path(dst).read_text(encoding="utf-8")))
        return real_replace(src, dst)

    with mock.patch.object(Path, "replace", record):
        atomic_write_json(path, {"name": "replacement"})

    assert len(swaps) == 1
    written, target_at_swap = swaps[0]
    assert json.loads(written) == {"name": "replacement"}
    assert json.loads(target_at_swap) == {"name": "original"}


def test_interrupted_write_leaves_the_old_file_intact(tmp_path: Path) -> None:
    """The reason this module exists: a crash mid-save must not cost the user their route."""
    path = tmp_path / "route.json"
    atomic_write_json(path, {"name": "original"})

    with (
        mock.patch.object(Path, "replace", side_effect=OSError("crash")),
        pytest.raises(OSError),
    ):
        atomic_write_json(path, {"name": "replacement"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"name": "original"}
    assert not (tmp_path / "route.json.tmp").exists()


def test_write_creates_missing_parents(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "c.json"
    atomic_write_json(path, [1, 2])
    assert json.loads(path.read_text(encoding="utf-8")) == [1, 2]


def test_non_ascii_survives_the_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "route.json"
    # allow-cyrillic: the point of this test is that non-ASCII survives the write
    atomic_write_json(path, {"name": "Маршрут"})  # allow-cyrillic
    assert read_json_or_none(path) == {"name": "Маршрут"}  # allow-cyrillic


def test_read_json_or_none_on_missing_and_corrupt(tmp_path: Path) -> None:
    assert read_json_or_none(tmp_path / "nope.json") is None

    broken = tmp_path / "broken.json"
    atomic_write_text(broken, '{"half wr')
    assert read_json_or_none(broken) is None


def test_backup_corrupt_moves_rather_than_deletes(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    atomic_write_text(broken, "not json")

    target = backup_corrupt(broken)

    assert not broken.exists()
    assert target.read_text(encoding="utf-8") == "not json"
    assert target.name.startswith("broken.json.broken-")


def test_backup_corrupt_stamps_the_copy_with_the_time(tmp_path: Path) -> None:
    """backend.py shows this name in the settings.corrupt toast, so it has to say when."""
    broken = tmp_path / "settings.json"
    atomic_write_text(broken, "not json")

    target = backup_corrupt(broken)

    stamp = target.name.removeprefix("settings.json.broken-")
    assert re.fullmatch(r"\d{8}-\d{6}", stamp)  # %Y%m%d-%H%M%S, as fileio spells it
    assert abs(datetime.strptime(stamp, "%Y%m%d-%H%M%S") - datetime.now()) < timedelta(minutes=1)


def test_backups_of_different_files_keep_their_own_names(tmp_path: Path) -> None:
    """settings.json and state.json can both be unreadable after the same crash."""
    settings = tmp_path / "settings.json"
    state = tmp_path / "state.json"
    atomic_write_text(settings, "not json")
    atomic_write_text(state, "also not json")

    first = backup_corrupt(settings)
    second = backup_corrupt(state)

    assert first != second
    assert first.read_text(encoding="utf-8") == "not json"
    assert second.read_text(encoding="utf-8") == "also not json"


@pytest.mark.xfail(reason=SAME_SECOND_COLLISION_DEFECT, strict=True)
def test_two_backups_of_one_file_do_not_overwrite_each_other(tmp_path: Path) -> None:
    """The clock is frozen so the collision is the subject of the test rather than a race."""
    broken = tmp_path / "settings.json"

    with mock.patch("map_overlay.core.fileio.datetime") as clock:
        clock.now.return_value = datetime(2026, 1, 2, 3, 4, 5)
        atomic_write_text(broken, "first")
        first = backup_corrupt(broken)
        atomic_write_text(broken, "second")
        second = backup_corrupt(broken)

    assert first != second
    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"
