"""The icon of the object under a route point, for the steps plaque.

The editor and the panel find it in TypeScript (ui/src/shared/ui/objectMarks.ts); the plaque's
list comes from Python, so the same rule lives here too, and the two must agree: a point
snapped onto an object -- within a map pixel -- takes that object's icon, a point anywhere else
takes none, and a category the game draws as a plain dot brings none either.
"""

from map_overlay.store.objects import icon_for, icons_under

SIZE = (1000, 500)


def objects(map_name: str, nodes: list[tuple[str, float, float]]) -> dict:
    return {
        "mapName": map_name,
        "categories": [
            {"id": c} for c in ("teleports", "seals", "hidden-cube-altgard", "gathering")
        ],
        "nodes": [{"c": c, "x": x, "y": y} for c, x, y in nodes],
    }


def test_the_categories_the_game_draws_an_icon_for() -> None:
    assert icon_for("empyrean-trace-altgard") == "trace"
    assert icon_for("hidden-cube-verteron") == "cube"
    assert icon_for("seals") == "seal"
    assert icon_for("teleports", "Altgard") == "teleport"
    assert icon_for("teleports", "Verteron") == "teleportElyos"
    assert icon_for("gathering") == ""
    assert icon_for("gathering-odyle") == "gathering-odyle"


def test_a_point_on_an_object_takes_its_icon_and_one_off_it_none() -> None:
    sets = [objects("Altgard", [("teleports", 10, 20), ("seals", 50, 50), ("gathering", 80, 80)])]
    points = [(100.0, 100.0), (500.4, 250.6), (103.0, 100.0), (800.0, 400.0), (0.0, 0.0)]
    assert icons_under(sets, SIZE, points) == ["teleport", "seal", "", "", ""]


def test_a_point_across_a_pixel_edge_from_its_object_still_finds_it() -> None:
    sets = [objects("Altgard", [("hidden-cube-altgard", 10.0995, 20)])]  # x = 100.995
    assert icons_under(sets, SIZE, [(101.2, 100.0)]) == ["cube"]
