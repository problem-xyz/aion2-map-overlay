"""Where a saved screen rectangle stands against the monitors that are there now.

A region is saved in physical desktop pixels, and the desktop it was saved on may be gone: a
monitor unplugged, a laptop undocked, a resolution changed. These functions answer "is it still
on a screen" and "where should it go instead" from plain rectangles, so they can be tested
without Qt; qt/screens.py is what reads the real monitors.

A screen is `(left, top, width, height)` in the same virtual-desktop coordinates a Region uses.
A monitor left of or above the primary one has negative coordinates, which is normal.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from map_overlay.core.settings import Region

type Rect = tuple[int, int, int, int]


def _usable(screens: Sequence[Rect]) -> list[Rect]:
    # Deduplicated: a mirrored display can be reported as two screens with one geometry, and
    # counting its pixels twice would call a half-visible rectangle fully visible.
    return list(dict.fromkeys(s for s in screens if s[2] > 0 and s[3] > 0))


def overlap_area(region: Region, screen: Rect) -> int:
    """How many pixels of the region lie on this screen."""
    left, top, width, height = screen
    dx = min(region["left"] + region["width"], left + width) - max(region["left"], left)
    dy = min(region["top"] + region["height"], top + height) - max(region["top"], top)
    return max(0, dx) * max(0, dy)


def on_any_screen(region: Region, screens: Sequence[Rect]) -> bool:
    """False only when not one pixel of the region lies on any screen there is.

    A list with no usable screen answers True. Qt can report none, or a zero-sized
    placeholder, for a moment while Windows rebuilds the display layout -- and clearing the
    user's region on that would throw away a choice that is about to be valid again.
    """
    usable = _usable(screens)
    if not usable:
        return True
    return any(overlap_area(region, s) > 0 for s in usable)


def _fully_visible(region: Region, usable: Sequence[Rect]) -> bool:
    # Windows never overlaps two monitors in the virtual desktop, so the overlaps add up to
    # the visible area even for a rectangle that straddles the seam between two of them.
    area = region["width"] * region["height"]
    return sum(overlap_area(region, s) for s in usable) >= area


def clamp_to_screens(region: Region, screens: Sequence[Rect], primary: Rect | None) -> Region:
    """Move the region, unchanged in size where it fits, fully onto one screen.

    A region that is already wholly visible, on one screen or across the seam of two, comes
    back as it was. Otherwise it goes to the screen that holds most of it; when none holds any
    of it, to the primary, or failing that the first usable screen. A region larger than that
    screen is shrunk to it, since no position would make it visible otherwise. With no usable
    screen the region comes back as it was.
    """
    usable = _usable(screens)
    if not usable or _fully_visible(region, usable):
        return region
    best = max(usable, key=lambda s: overlap_area(region, s))
    if overlap_area(region, best) == 0 and primary in usable:
        best = primary
    left, top, width, height = best
    w = min(region["width"], width)
    h = min(region["height"], height)
    return Region(
        left=min(max(region["left"], left), left + width - w),
        top=min(max(region["top"], top), top + height - h),
        width=w,
        height=h,
    )


@dataclass(frozen=True)
class ScreenCheck:
    """The two saved rectangles, checked against the monitors there are now.

    `region` is the map area to keep, None when it had to go. It is never moved: a rectangle
    shifted onto another monitor would no longer frame the game's map, so a lost area is
    cleared and the user picks it again. `steps_region` is the plaque's rectangle, moved back
    onto a screen if it had drifted off one.
    """

    region: Region | None
    steps_region: Region | None
    region_lost: bool
    steps_moved: bool


def check_regions(
    region: Region | None,
    steps_region: Region | None,
    screens: Sequence[Rect],
    primary: Rect | None,
) -> ScreenCheck:
    lost = region is not None and not on_any_screen(region, screens)
    steps = clamp_to_screens(steps_region, screens, primary) if steps_region else steps_region
    return ScreenCheck(
        region=None if lost else region,
        steps_region=steps,
        region_lost=lost,
        steps_moved=steps != steps_region,
    )
