"""A saved rectangle against the monitors that are there now: pure geometry, no Qt.

The layouts are the ones a user actually has. A 1920x1080 primary at the origin; a second
1920x1080 monitor to its right; and one to its left, which Windows places at negative x because
the primary always owns (0, 0).
"""

from map_overlay.core.geometry import (
    Rect,
    check_regions,
    clamp_to_screens,
    on_any_screen,
    overlap_area,
)
from map_overlay.core.settings import Region

PRIMARY: Rect = (0, 0, 1920, 1080)
RIGHT: Rect = (1920, 0, 1920, 1080)
LEFT: Rect = (-1920, 0, 1920, 1080)


def region(left: int, top: int, width: int = 400, height: int = 300) -> Region:
    return Region(left=left, top=top, width=width, height=height)


# --------------------------------------------------------------------------- on_any_screen


def test_a_region_inside_the_primary_is_on_screen() -> None:
    assert on_any_screen(region(100, 100), [PRIMARY])


def test_a_region_partly_outside_is_still_on_screen() -> None:
    """Only a region with no pixel left on any monitor is lost; a clipped one still captures."""
    assert on_any_screen(region(1800, 900), [PRIMARY])
    assert overlap_area(region(1800, 900), PRIMARY) == 120 * 180


def test_a_region_far_off_every_screen_is_not_on_screen() -> None:
    assert not on_any_screen(region(6000, 100), [PRIMARY, RIGHT])


def test_a_region_touching_the_edge_but_not_crossing_it_is_off_screen() -> None:
    """Right-open rectangles: x = 1920 is the first pixel of the next monitor, not the last."""
    assert not on_any_screen(region(1920, 0), [PRIMARY])


def test_a_region_on_a_second_monitor_is_lost_when_that_monitor_goes() -> None:
    saved = region(2500, 300)
    assert on_any_screen(saved, [PRIMARY, RIGHT])
    assert not on_any_screen(saved, [PRIMARY])


def test_a_monitor_left_of_the_primary_has_negative_coordinates_and_counts() -> None:
    saved = region(-1500, 200)
    assert on_any_screen(saved, [PRIMARY, LEFT])
    assert not on_any_screen(saved, [PRIMARY])


def test_no_screens_at_all_is_not_taken_as_proof_the_region_is_gone() -> None:
    """Qt can report none for a moment while Windows rebuilds the layout."""
    assert on_any_screen(region(6000, 100), [])
    assert on_any_screen(region(6000, 100), [(0, 0, 0, 0)])


# --------------------------------------------------------------------------- clamp_to_screens


def test_a_fully_visible_region_is_left_exactly_where_it_is() -> None:
    saved = region(100, 100)
    assert clamp_to_screens(saved, [PRIMARY], PRIMARY) == saved


def test_a_region_across_the_seam_of_two_monitors_is_visible_and_not_moved() -> None:
    saved = region(1800, 100)
    assert clamp_to_screens(saved, [PRIMARY, RIGHT], PRIMARY) == saved


def test_a_region_hanging_off_an_edge_is_pulled_back_in_without_resizing() -> None:
    assert clamp_to_screens(region(1800, 900), [PRIMARY], PRIMARY) == region(1520, 780)


def test_a_region_off_every_screen_goes_to_the_primary() -> None:
    assert clamp_to_screens(region(6000, 100), [RIGHT, PRIMARY], PRIMARY) == region(1520, 100)


def test_without_a_primary_it_goes_to_the_first_screen() -> None:
    assert clamp_to_screens(region(6000, 100), [RIGHT], None) == region(3440, 100)


def test_a_region_goes_to_the_screen_that_holds_most_of_it() -> None:
    """Mostly on the left monitor and hanging off its top edge: it stays on the left one."""
    moved = clamp_to_screens(region(-1000, -100), [PRIMARY, LEFT], PRIMARY)
    assert moved == region(-1000, 0)


def test_a_region_bigger_than_the_screen_is_shrunk_to_it() -> None:
    moved = clamp_to_screens(region(-50, -50, 4000, 3000), [PRIMARY], PRIMARY)
    assert moved == region(0, 0, 1920, 1080)


def test_with_no_usable_screen_the_region_is_returned_unchanged() -> None:
    saved = region(6000, 100)
    assert clamp_to_screens(saved, [], None) == saved


def test_a_mirrored_screen_is_not_counted_twice() -> None:
    """Half on a mirrored pair would otherwise add up to "fully visible" and never move."""
    moved = clamp_to_screens(region(1720, 100), [PRIMARY, PRIMARY], PRIMARY)
    assert moved == region(1520, 100)


# --------------------------------------------------------------------------- check_regions


def test_nothing_changes_when_both_rectangles_are_on_screen() -> None:
    check = check_regions(region(100, 100), region(60, 140), [PRIMARY], PRIMARY)
    assert (check.region_lost, check.steps_moved) == (False, False)
    assert check.region == region(100, 100)
    assert check.steps_region == region(60, 140)


def test_a_lost_map_area_is_cleared_and_not_moved() -> None:
    """Moved onto another monitor it would frame something other than the game map."""
    check = check_regions(region(2500, 300), None, [PRIMARY], PRIMARY)
    assert check.region_lost
    assert check.region is None
    assert (check.steps_region, check.steps_moved) == (None, False)


def test_a_plaque_left_on_an_unplugged_monitor_comes_back_to_the_primary() -> None:
    check = check_regions(None, region(2500, 300, 430, 160), [PRIMARY], PRIMARY)
    assert not check.region_lost
    assert check.steps_moved
    assert check.steps_region == region(1490, 300, 430, 160)


def test_no_saved_rectangles_means_nothing_to_do() -> None:
    check = check_regions(None, None, [PRIMARY], PRIMARY)
    assert check == check_regions(None, None, [], None)
    assert (check.region, check.steps_region, check.region_lost, check.steps_moved) == (
        None,
        None,
        False,
        False,
    )
