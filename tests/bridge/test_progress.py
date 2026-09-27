"""ProgressTracker: when a point ticks itself off, and how the count is read and written.

The arrival test is pure arithmetic over a route document, so it is pinned exactly: the radius
is `arrive_radius` scaled by the map width, and only the next point counts -- never one past
it, and never one behind, which is the whole of what keeps the count from walking backwards
when the player does, or jumping ahead when they run past a later point.

Progress always counts; `auto_progress` alone says whether an arrival ticks a point off.

The store is the real SettingsStore on a throwaway user-data tree: a stub of it would be free to
drift from the field names and the clamping the tracker actually reads.
"""

from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.progress import ProgressTracker
from map_overlay.bridge.settings_store import SettingsStore
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Settings

ROUTE = "gold"
OTHER_ROUTE = "silver"

# Neither square nor the same size as the reference: a dropped or inverted reference-pixel
# conversion in on_player then puts the player somewhere else entirely instead of nowhere.
MAP_SIZE = [1000, 800]
REF_SIZE = (500, 400)

# arrive_radius is a fraction of the map *width*, so the shipped 8 / 4096 over MAP_SIZE[0] is
# a little under 2 route units. Offsets below are written as this minus or plus one.
RADIUS_UNITS = Settings.arrive_radius * MAP_SIZE[0]

Marker = dict[str, float]

MARKERS: list[Marker] = [
    {"x": 100.0, "y": 100.0},
    {"x": 300.0, "y": 200.0},
    {"x": 500.0, "y": 300.0},
]


def make_doc(markers: list[Marker] | None = None) -> dict[str, Any]:
    """The two fields the tracker reads. The rest of a route document is not its business."""
    return {"mapSize": list(MAP_SIZE), "markers": list(MARKERS if markers is None else markers)}


def player_at(marker: Marker, dx: float = 0.0, dy: float = 0.0) -> tuple[float, float]:
    """Reference pixels for a player standing `dx`/`dy` route units away from `marker`."""
    x, y = marker["x"] + dx, marker["y"] + dy
    return x * REF_SIZE[0] / MAP_SIZE[0], y * REF_SIZE[1] / MAP_SIZE[1]


def arrange(store: SettingsStore, *, auto: bool = True, done: int = 0) -> None:
    """The whole of what the tracker reads: the flag, the open route, the stored count."""
    store.update_settings({"auto_progress": auto})
    store.set_state(route=ROUTE, progress={ROUTE: done})


@pytest.fixture
def store(qapp: QApplication, dirs: DataDirs) -> SettingsStore:
    """A real store over an empty user-data tree, left at the shipped defaults."""
    return SettingsStore(dirs)


@pytest.fixture
def tracker(store: SettingsStore) -> ProgressTracker:
    return ProgressTracker(store)


# --------------------------------------------------------------------------- arriving


def test_a_hit_inside_the_arrival_radius_closes_the_next_point(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store)
    doc = make_doc()

    assert tracker.on_player(*player_at(MARKERS[0], dx=RADIUS_UNITS - 1), doc, REF_SIZE) == 1


def test_a_point_beyond_the_arrival_radius_is_not_reached(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store)
    doc = make_doc()

    assert tracker.on_player(*player_at(MARKERS[0], dy=RADIUS_UNITS + 1), doc, REF_SIZE) is None


def test_the_arrival_radius_is_the_setting_scaled_by_the_map_width(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """Widening the setting reaches a point that the shipped radius does not.

    The scale is the map width for both axes, which is why the offset here is on y: an
    implementation that scaled y by the map height would give a smaller radius and miss.
    """
    arrange(store)
    doc = make_doc()
    outside = player_at(MARKERS[0], dy=RADIUS_UNITS + 1)

    assert tracker.on_player(*outside, doc, REF_SIZE) is None

    store.update_settings({"arrive_radius": 32 / 4096})  # the top: four times the shipped radius

    assert tracker.on_player(*outside, doc, REF_SIZE) == 1


@pytest.mark.parametrize("view", ["steps", "dim", "all"])
def test_a_point_past_the_next_one_is_never_reached_however_the_route_is_drawn(
    store: SettingsStore, tracker: ProgressTracker, view: str
) -> None:
    """In order and only in order: running past point 2 or 3 closes nothing.

    A lookahead of two used to close points 1 to 3 at a run past point 3 -- with one step ahead
    shown, by a point that was not even on screen.
    """
    arrange(store)
    store.update_settings({"route_view": view, "route_ahead": 10})
    doc = make_doc()

    assert tracker.on_player(*player_at(MARKERS[1]), doc, REF_SIZE) is None
    assert tracker.on_player(*player_at(MARKERS[2]), doc, REF_SIZE) is None
    assert tracker.on_player(*player_at(MARKERS[0]), doc, REF_SIZE) == 1


def test_standing_on_a_point_already_behind_the_player_reports_nothing(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store, done=2)
    doc = make_doc()

    assert tracker.on_player(*player_at(MARKERS[0]), doc, REF_SIZE) is None
    assert tracker.on_player(*player_at(MARKERS[1]), doc, REF_SIZE) is None
    assert tracker.on_player(*player_at(MARKERS[2]), doc, REF_SIZE) == 3


def test_walking_the_route_backwards_never_lowers_the_count(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """The backend's own loop: every arrival is written back, then the player turns around.

    This is the monotonicity claim end to end rather than one call at a time -- the scan window
    opening at the stored count is what makes a walk back over closed points a no-op.
    """
    arrange(store)
    doc = make_doc()
    counts: list[int] = []

    for index in (0, 1, 2, 1, 0, 2):
        reached = tracker.on_player(*player_at(MARKERS[index]), doc, REF_SIZE)
        if reached is not None:
            tracker.set_done(reached, doc)
        counts.append(tracker.done_count(doc))

    assert counts == [1, 2, 3, 3, 3, 3]


def test_a_return_visit_ahead_waits_while_the_player_stands_where_it_last_ticked(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """A teleport taken twice: points 1 and 3 on one spot, point 2 somewhere between.

    Standing on the teleport with point 1 just ticked off, point 3 on the same spot must wait
    for point 2: a lookahead once closed both, and nobody had walked to point 2 yet.
    """
    teleport = MARKERS[0]
    doc = make_doc([teleport, MARKERS[1], dict(teleport), MARKERS[2]])
    arrange(store, done=1)

    assert tracker.on_player(*player_at(teleport), doc, REF_SIZE) is None
    assert tracker.on_player(*player_at(MARKERS[1]), doc, REF_SIZE) == 2

    arrange(store, done=2)

    assert tracker.on_player(*player_at(teleport), doc, REF_SIZE) == 3


def test_two_points_in_a_row_on_one_spot_are_ticked_off_one_after_the_other(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """The next point is never held back, even on the spot the last one was ticked off."""
    doc = make_doc([MARKERS[0], dict(MARKERS[0]), MARKERS[1]])
    arrange(store, done=1)

    assert tracker.on_player(*player_at(MARKERS[0]), doc, REF_SIZE) == 2


def test_a_finished_route_has_nothing_left_to_arrive_at(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store, done=len(MARKERS))
    doc = make_doc()

    assert tracker.on_player(*player_at(MARKERS[2]), doc, REF_SIZE) is None


# --------------------------------------------------------------------------- the guards


def test_nothing_is_reached_while_auto_progress_is_off(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """The manual mode: the user ticks points off themselves and the player must not."""
    arrange(store, auto=False)
    doc = make_doc()

    assert tracker.on_player(*player_at(MARKERS[0]), doc, REF_SIZE) is None


def test_a_player_position_without_an_open_route_is_ignored(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store)
    store.set_state(route=None)

    assert tracker.on_player(*player_at(MARKERS[0]), make_doc(), REF_SIZE) is None


@pytest.mark.parametrize("doc", [None, make_doc([])])
def test_a_player_position_with_no_route_document_to_check_against_is_ignored(
    store: SettingsStore, tracker: ProgressTracker, doc: dict[str, Any] | None
) -> None:
    """Player ticks arrive at 15 Hz and keep arriving for a moment after the route is closed."""
    arrange(store)

    assert tracker.on_player(*player_at(MARKERS[0]), doc, REF_SIZE) is None


@pytest.mark.parametrize("ref_size", [None, (0, 400), (500, 0)])
def test_a_reference_size_with_no_area_is_refused_rather_than_divided_by(
    store: SettingsStore, tracker: ProgressTracker, ref_size: tuple[int, int] | None
) -> None:
    """The size comes from map metadata that may be missing or half-written."""
    arrange(store)

    assert tracker.on_player(*player_at(MARKERS[0]), make_doc(), ref_size) is None


# --------------------------------------------------------------------------- reading


def test_a_count_left_over_from_a_longer_route_reads_as_the_route_length(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """The route was shortened in the editor between two runs; the count may not point past it."""
    arrange(store, done=5)
    doc = make_doc()

    assert tracker.done_count(doc) == 3
    assert tracker.done_count() == 5  # nothing to clamp against without a document


def test_a_negative_stored_count_reads_as_zero(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """A floor, not a repair path: loading coerces the file, so only a caller can get one in."""
    arrange(store, done=-2)
    doc = make_doc()

    assert tracker.done_count(doc) == 0
    assert tracker.on_player(*player_at(MARKERS[0]), doc, REF_SIZE) == 1


# --------------------------------------------------------------------------- writing


def test_setting_the_count_stores_it_and_announces_it(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store)
    doc = make_doc()
    seen: list[tuple[int, int]] = []
    tracker.changed.connect(lambda done, total: seen.append((done, total)))

    assert tracker.set_done(2, doc) is True
    assert seen == [(2, 3)]
    assert store.state.progress == {ROUTE: 2}


def test_setting_the_count_it_already_has_changes_nothing_and_says_nothing(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    """The player tick arrives 15 times a second: a redundant write would be 15 state writes."""
    arrange(store, done=2)
    seen: list[tuple[int, int]] = []
    tracker.changed.connect(lambda done, total: seen.append((done, total)))

    assert tracker.set_done(2, make_doc()) is False
    assert seen == []


@pytest.mark.parametrize(("given", "expected"), [(-5, 0), (0, 0), (2, 2), (3, 3), (9, 3)])
def test_a_count_being_set_is_held_between_zero_and_the_route_length(
    store: SettingsStore, tracker: ProgressTracker, given: int, expected: int
) -> None:
    arrange(store, done=1)

    tracker.set_done(given, make_doc())

    assert store.state.progress[ROUTE] == expected


def test_setting_a_count_without_an_open_route_stores_nothing(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store, done=2)
    store.set_state(route=None)

    assert tracker.set_done(1, make_doc()) is False
    assert store.state.progress == {ROUTE: 2}


def test_clamping_lowers_a_count_that_points_past_the_new_end(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store, done=5)

    tracker.clamp_to(ROUTE, 3)

    assert store.state.progress[ROUTE] == 3


def test_clamping_leaves_a_count_that_still_fits(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store, done=2)

    tracker.clamp_to(ROUTE, 3)

    assert store.state.progress[ROUTE] == 2


def test_forgetting_a_route_leaves_every_other_route_on_record(
    store: SettingsStore, tracker: ProgressTracker
) -> None:
    arrange(store)
    store.set_state(progress={ROUTE: 2, OTHER_ROUTE: 1})

    tracker.forget(ROUTE)

    assert store.state.progress == {OTHER_ROUTE: 1}
