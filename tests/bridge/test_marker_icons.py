"""A route point's quest icon, from the file to the steps plaque.

The editor lets a point be marked as a main or a side quest, a yellow or a green star beside its
number. The icon is an optional field: it has to survive a save, a share code and the trip to
the plaque, and a point without one must look to the plaque exactly as it always has.

The plaque's data is read off data_json with the window's fields and no window: a Backend here,
with its three web views, was one too many for the Qt WebEngine the session shares, and a later
test's teardown died of it.
"""

import json
from types import SimpleNamespace
from typing import Any, cast

from map_overlay.bridge.state import RouteDoc, progress_state, steps_of
from map_overlay.core.paths import DataDirs
from map_overlay.qt.steps_window import WebStepsWindow
from map_overlay.store import routes
from map_overlay.store.share import decode_share, encode_share

ROUTE = "quests"


def quest_doc() -> dict[str, Any]:
    doc = routes.new_route_doc("Quests", "altgard", [1000, 800])
    doc["markers"] = [
        {"x": 100.0, "y": 100.0, "text": "Talk to the elder", "icon": "main"},
        {"x": 200.0, "y": 100.0, "text": "Pick the herbs", "icon": "side"},
        {"x": 300.0, "y": 100.0, "text": ""},
    ]
    return routes.validate_route(doc)


def test_the_icons_survive_a_save(dirs: DataDirs) -> None:
    routes.save_route(dirs, ROUTE, quest_doc())
    markers = routes.load_route(dirs, ROUTE)["markers"]
    assert [m.get("icon") for m in markers] == ["main", "side", None]


def test_the_icons_survive_a_share_code() -> None:
    doc = quest_doc()
    assert decode_share(encode_share(doc)) == doc


def test_the_plaque_is_told_each_point_s_icon() -> None:
    steps = steps_of(cast("RouteDoc", quest_doc()))
    assert [icon for _, _, _, icon, _ in steps] == ["main", "side", ""]


def test_the_plaque_s_data_carries_an_icon_only_where_there_is_one() -> None:
    steps = plaque_steps(steps_of(cast("RouteDoc", quest_doc())))
    assert [s.get("icon") for s in steps] == ["main", "side", None]
    assert "icon" not in steps[2]


def test_the_plaque_is_told_what_each_point_sits_on_only_where_it_sits_on_something() -> None:
    steps = plaque_steps(steps_of(cast("RouteDoc", quest_doc()), ["", "teleport", ""]))
    assert [s.get("object") for s in steps] == [None, "teleport", None]
    assert "object" not in steps[0]


def plaque_steps(steps: list[tuple[int, str, str, str, str]]) -> list[dict[str, Any]]:
    window = SimpleNamespace(
        _steps=steps,
        _done=0,
        _past=0,
        _title="Quests",
        _scale=1.0,
        size_key=lambda: "m",
        _pinned=False,
        _opacity=1.0,
        GRIP=WebStepsWindow.GRIP,
    )
    return json.loads(WebStepsWindow.data_json(cast("WebStepsWindow", window)))["steps"]


def test_the_panel_s_progress_list_is_told_each_point_s_place_and_icon() -> None:
    markers = progress_state(cast("RouteDoc", quest_doc()), 0)["markers"]
    assert [(m["x"], m["y"]) for m in markers] == [(100.0, 100.0), (200.0, 100.0), (300.0, 100.0)]
    assert [m.get("icon") for m in markers] == ["main", "side", None]
    assert "icon" not in markers[2]
