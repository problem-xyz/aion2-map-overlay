"""What SettingsStore promises the disk, and when.

The store's whole reason to exist is that memory runs ahead of the disk: a slider being dragged
must not cost one write per frame, and a progress tick must not rewrite the user's preferences.
Those are timing and file-routing promises, not schema ones -- coercion itself is already pinned
by tests/core/test_settings.py, and is only touched here where update_settings puts a UI patch
through it.

Writes are counted rather than inferred. atomic_write_json is wrapped where settings_store
imported it, so every test sees the exact number of writes, their target paths and their
payloads, while the real files are still produced. File mtimes would not do: their granularity
on Windows is coarser than the 400 ms debounce this file is about.

The debounce is a real single-shot QTimer, so nothing fires unless an event loop is running.
That is why the coalescing test spins the loop with QTest.qWait between its edits -- without
that it would pass just as happily against a store that did not debounce at all.
"""

import json
import logging
import math
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge import settings_store
from map_overlay.bridge.settings_store import WRITE_DELAY_MS, SettingsStore
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Settings, State, settings_payload, state_payload

# Long enough that a timer armed at the start of the call has certainly fired, short enough that
# a handful of these do not dominate the suite.
SETTLE_MS = WRITE_DELAY_MS + 200


@pytest.fixture
def writes(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, Any]]:
    """Every write the store makes, in order, with the real file still written."""
    recorded: list[tuple[Path, Any]] = []
    real = settings_store.atomic_write_json

    def record(path: Path | str, obj: Any, indent: int | None = 2, **kwargs: Any) -> None:
        recorded.append((Path(path), obj))
        real(path, obj, indent, **kwargs)

    monkeypatch.setattr(settings_store, "atomic_write_json", record)
    return recorded


@pytest.fixture
def make_store(
    dirs: DataDirs,
    qapp: QApplication,
    writes: list[tuple[Path, Any]],
) -> Iterator[Callable[[], SettingsStore]]:
    """Builds stores and disarms them afterwards.

    Every SettingsStore in this file is built through here, which is what guarantees the
    QApplication exists: without one the debounce timer has no event loop to fire on.

    A store left with an armed timer would fire inside a later test's qWait, by which point the
    recorder is gone and tmp_path may be too -- a write into a deleted directory, raised inside a
    Qt slot, where it cannot fail the test that caused it.
    """
    made: list[SettingsStore] = []

    def build() -> SettingsStore:
        store = SettingsStore(dirs)
        made.append(store)
        return store

    yield build

    for store in made:
        for timer in store.findChildren(QTimer):
            timer.stop()


@pytest.fixture
def store(make_store: Callable[[], SettingsStore]) -> SettingsStore:
    return make_store()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def paths_written(writes: list[tuple[Path, Any]]) -> list[Path]:
    return [path for path, _ in writes]


def test_three_edits_in_quick_succession_reach_the_disk_as_one_write(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    """The event loop runs between the edits, so the debounce is really tested.

    Each edit restarts the timer, which is what turns a dragged slider into one write instead of
    one per frame -- and what makes the deadline count from the last edit, not the first.
    """
    store.update_settings({"opacity": 0.1})
    QTest.qWait(50)
    store.update_settings({"opacity": 0.2})
    QTest.qWait(50)
    store.update_settings({"opacity": 0.3})

    assert writes == []  # 100 ms of edits, still nothing on disk

    QTest.qWait(SETTLE_MS)

    assert paths_written(writes) == [dirs.settings]
    assert writes[0][1]["opacity"] == 0.3  # the last value, not the first
    assert read(dirs.settings)["opacity"] == 0.3


def test_flush_writes_both_pending_changes_without_waiting_for_the_timer(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    """Shutdown calls this, and a debounced write that never happens is a lost setting."""
    store.update_settings({"fps": 90})
    store.set_state(route="Test_1")

    store.flush()

    assert sorted(paths_written(writes)) == sorted([dirs.settings, dirs.state])
    assert read(dirs.settings) == settings_payload(store.settings)
    assert read(dirs.state) == state_payload(store.state)


def test_flush_writes_nothing_when_no_change_is_pending(
    store: SettingsStore,
    writes: list[tuple[Path, Any]],
) -> None:
    """flush() is called on every shutdown path, so it has to be idle when nothing is dirty."""
    store.flush()
    assert writes == []

    store.update_settings({"fps": 90})
    store.flush()
    assert len(writes) == 1

    store.flush()
    assert len(writes) == 1  # the first flush cleared the pending mark


def test_flush_disarms_the_timers_so_no_second_write_follows_it(
    store: SettingsStore,
    writes: list[tuple[Path, Any]],
) -> None:
    """A timer left armed would fire into a half-torn-down app, and _write_* does not re-check
    the pending mark before writing -- it would simply write the file again."""
    store.update_settings({"fps": 90})
    store.set_state(route="Test_1")

    store.flush()

    assert not any(timer.isActive() for timer in store.findChildren(QTimer))
    QTest.qWait(SETTLE_MS)
    assert len(writes) == 2


def test_one_edit_produces_exactly_one_write_and_the_timer_then_falls_silent(
    store: SettingsStore,
    writes: list[tuple[Path, Any]],
) -> None:
    """The wait deliberately spans two intervals.

    A timer that repeated instead of firing once would be the disease this module exists to cure
    -- settings.json rewritten every 400 ms for as long as the app is open -- and a wait of one
    interval could not tell the two apart.
    """
    store.update_settings({"fps": 90})

    QTest.qWait(2 * WRITE_DELAY_MS + 200)
    assert len(writes) == 1

    store.flush()

    assert len(writes) == 1  # the write cleared the pending mark, so shutdown adds nothing


def test_an_update_that_changes_nothing_arms_no_timer_and_writes_nothing(
    store: SettingsStore,
    writes: list[tuple[Path, Any]],
) -> None:
    """The UI re-sends the whole settings object on every panel render."""
    before = store.settings

    returned = store.update_settings({"opacity": before.opacity, "detector": before.detector})

    assert returned == before
    assert not any(timer.isActive() for timer in store.findChildren(QTimer))
    store.flush()
    assert writes == []


def test_a_state_change_alone_does_not_rewrite_the_settings_file(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    """The reason the two files and the two timers are separate: progress ticks at 15 Hz."""
    store.set_state(route="Test_1", progress={"Test_1": 3})

    store.flush()

    assert paths_written(writes) == [dirs.state]
    assert not dirs.settings.exists()


def test_a_settings_change_alone_does_not_rewrite_the_state_file(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    store.update_settings({"fps": 90})

    store.flush()

    assert paths_written(writes) == [dirs.settings]
    assert not dirs.state.exists()


def test_update_settings_clamps_a_value_outside_its_range_before_it_reaches_the_disk(
    store: SettingsStore,
    dirs: DataDirs,
) -> None:
    """The store is the gate: no caller, the UI least of all, gets to store a rejected value."""
    returned = store.update_settings({"opacity": 5.0, "detector": "bogus"})

    assert returned.opacity == 1.0
    assert returned.detector == Settings.detector
    assert store.settings is returned

    store.flush()
    assert read(dirs.settings)["opacity"] == 1.0


def test_update_settings_refuses_a_key_the_schema_does_not_know(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    store.update_settings({"bogus": 1})
    store.flush()
    assert writes == []  # an unknown key changes nothing, so there is nothing to write

    store.update_settings({"bogus": 1, "fps": 90})
    store.flush()

    assert store.settings.fps == 90
    assert not hasattr(store.settings, "bogus")
    assert "bogus" not in read(dirs.settings)


def test_a_patch_leaves_the_fields_it_does_not_mention_alone(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    """The UI sends the one control that moved, not the whole object."""
    store.update_settings({"opacity": 0.5})
    store.update_settings({"fps": 90})

    store.flush()

    assert (store.settings.opacity, store.settings.fps) == (0.5, 90)
    assert len(writes) == 1  # both edits coalesced into the one flush
    written = read(dirs.settings)
    assert (written["opacity"], written["fps"]) == (0.5, 90)
    assert written["detector"] == Settings.detector


def test_set_state_keeps_the_fields_it_was_not_given(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    store.set_state(route="Test_1")
    store.set_state(progress={"Test_1": 3})

    store.flush()

    assert len(writes) == 1
    written = read(dirs.state)
    assert (written["route"], written["progress"]) == ("Test_1", {"Test_1": 3})


def test_set_state_that_changes_nothing_writes_nothing(
    store: SettingsStore,
    writes: list[tuple[Path, Any]],
) -> None:
    store.set_state(route=store.state.route, steps_visible=store.state.steps_visible)

    assert not any(timer.isActive() for timer in store.findChildren(QTimer))
    store.flush()
    assert writes == []


def test_set_state_puts_a_patch_through_the_same_coercion_as_the_file(
    store: SettingsStore,
    dirs: DataDirs,
) -> None:
    """A NaN in a region would be written as a bare NaN and sent in getState, and JSON.parse in
    the panel rejects the whole state for it."""
    good = {"left": 0, "top": 0, "width": 800, "height": 600}
    store.set_state(region=good, progress={"Test_1": 3})

    store.set_state(region={**good, "left": math.nan}, steps_region={**good, "width": math.inf})
    store.set_state(progress={"Test_1": math.inf, "Test_2": 2})

    assert (store.state.region, store.state.steps_region) == (None, None)
    assert store.state.progress == {"Test_2": 2}
    store.flush()
    json.dumps(read(dirs.state), allow_nan=False)
    with pytest.raises(TypeError):
        store.set_state(bogus=1)


def test_a_value_that_got_past_coercion_is_not_written_as_nan(
    store: SettingsStore,
    dirs: DataDirs,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The writer's own check, for a regression that bypasses coercion: the old file stays,
    and the log says why, rather than a settings.json the panel cannot parse."""
    store.update_settings({"fps": 90})
    store.flush()
    # what a bug would have to do: update_settings itself would repair the NaN
    store.settings = replace(store.settings, fps=60, opacity=math.nan)
    store._settings_dirty = True

    with caplog.at_level(logging.ERROR, logger="map_overlay.bridge.settings_store"):
        store.flush()

    assert "NaN" not in dirs.settings.read_text(encoding="utf-8")
    assert read(dirs.settings)["fps"] == 90
    assert any("not writing settings.json" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    ("case", "content"),
    [
        ("corrupt", '{"opacity": 0.5, "fps"'),
        ("pre_v1", json.dumps({"settings": {"opacity": 0.5}, "route": "Test_1"})),
        ("rejected_value", json.dumps({"version": 1, "fps": "60"})),
    ],
)
def test_a_repaired_file_is_written_back_at_construction(
    case: str,
    content: str,
    dirs: DataDirs,
    make_store: Callable[[], SettingsStore],
    writes: list[tuple[Path, Any]],
) -> None:
    """Not debounced, on purpose.

    A migration lost to a crash before the first edit would have to run again, and leaving
    rejected values on disk would show the user the same "values were reset" toast on every
    launch. So this write happens during __init__, with no event loop involved.
    """
    dirs.settings.write_text(content, encoding="utf-8")

    built = make_store()

    assert sorted(paths_written(writes)) == sorted([dirs.settings, dirs.state])
    assert read(dirs.settings) == settings_payload(built.settings)
    assert read(dirs.state) == state_payload(built.state)


def test_a_current_pair_of_files_is_not_rewritten_at_construction(
    dirs: DataDirs,
    make_store: Callable[[], SettingsStore],
    writes: list[tuple[Path, Any]],
) -> None:
    """Starting the app must not touch files it has nothing to repair."""
    dirs.settings.write_text(
        json.dumps(settings_payload(Settings(fps=90, language="ru"))), encoding="utf-8"
    )
    dirs.state.write_text(
        json.dumps(state_payload(State(route="Test_1", progress={"Test_1": 3}))), encoding="utf-8"
    )

    built = make_store()

    assert writes == []
    assert built.settings.fps == 90
    assert built.state.route == "Test_1"
    assert built.reset_keys == []
    assert built.corrupt_backup is None


def test_reset_settings_brings_every_preference_back_through_the_debounced_write(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    store.update_settings({"fps": 90, "opacity": 0.4, "detector": "orb", "language": "ru"})
    store.flush()
    writes.clear()

    returned = store.reset_settings()

    assert returned == Settings()
    assert store.settings is returned
    assert writes == []  # the same debounce as any edit, not a write of its own
    QTest.qWait(SETTLE_MS)
    assert paths_written(writes) == [dirs.settings]
    assert read(dirs.settings) == settings_payload(Settings())


def test_reset_settings_keeps_the_updater_fields_and_leaves_state_alone(
    store: SettingsStore,
    dirs: DataDirs,
    writes: list[tuple[Path, Any]],
) -> None:
    """A dismissed update prompt is an answer, not a preference: reset must not bring it back.
    Nor may it turn update checks, and with them network access, back on.

    State is a separate file for a reason -- the map area and the progress are not settings.
    """
    kept = Settings(
        updates_auto_check=False, updates_auto_download=False, updates_skipped_version="1.2.0"
    )
    store.update_settings({"fps": 90, "updates_auto_check": False})
    store.update_settings({"updates_auto_download": False, "updates_skipped_version": "1.2.0"})
    store.set_state(route="Test_1", progress={"Test_1": 3})
    store.flush()
    writes.clear()

    store.reset_settings()
    store.flush()

    assert store.settings == kept
    assert paths_written(writes) == [dirs.settings]
    assert (store.state.route, store.state.progress) == ("Test_1", {"Test_1": 3})


def test_reset_settings_on_defaults_writes_nothing(
    store: SettingsStore,
    writes: list[tuple[Path, Any]],
) -> None:
    store.reset_settings()
    store.flush()
    assert writes == []
