"""scripts/import_cubes.py: the game's cube groups, in world coordinates, into an object set."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from map_overlay.store.objects import cube_tints, validate_objects

REPO = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ic = load_script(REPO / "scripts" / "import_cubes.py", "import_cubes")

CATEGORY = "hidden-cube-altgard"


def test_the_world_centre_is_the_middle_of_the_layer() -> None:
    assert ic.layer_px(0, 0) == (4096, 4096)


def test_the_world_edge_is_the_layer_edge() -> None:
    assert ic.layer_px(-4080, 4080) == pytest.approx((0, 8192))


def test_a_group_is_named_without_the_engine_prefix() -> None:
    assert ic.group_name("EnvObj_D1_BasfeltRuins_HiddenBox_01_A") == "BasfeltRuins_01_A"
    assert ic.group_name("EnvObj_D1_MoslanForest_UnderWater_HiddenBox_01_A") == (
        "MoslanForest_UnderWater_01_A"
    )


@pytest.mark.parametrize(
    ("height", "expected"), [(121, "up"), (120, ""), (100, ""), (80, ""), (79, "down")]
)
def test_a_spot_is_up_or_down_only_past_the_step(height: float, expected: str) -> None:
    assert ic.level(height, 100) == expected


def ground(
    height: float, at: tuple[float, float] = (4096, 4096)
) -> list[tuple[float, float, float]]:
    """Three markers at a point, all of one height: as much ground as a spot needs."""
    return [(at[0], at[1], height)] * ic.MIN_NEAR


def test_a_spot_is_measured_against_the_markers_about_it() -> None:
    groups = [{"s": "EnvObj_D1_A_HiddenBox_01", "pos": [[0, 150, 0], [0, 60, 0], [0, 100, 0]]}]

    nodes = ic.cube_nodes(groups, ground(100), CATEGORY, [0])

    assert [n.get("level") for n in nodes] == ["up", "down", None]


def test_markers_too_far_away_are_not_its_ground() -> None:
    far = ground(0, at=(4096 + ic.NEAR + 1, 4096))
    groups = [{"s": "EnvObj_D1_A_HiddenBox_01", "pos": [[0, 100, 0]] * 3}]

    assert all("level" not in n for n in ic.cube_nodes(groups, far, CATEGORY, [0]))


def test_with_no_ground_near_a_spot_its_group_is_the_ground() -> None:
    groups = [{"s": "EnvObj_D1_A_HiddenBox_01", "pos": [[0, 150, 0], [0, 100, 0], [0, 90, 0]]}]

    nodes = ic.cube_nodes(groups, [], CATEGORY, [0])

    assert [n.get("level") for n in nodes] == ["up", None, None]


def test_the_nodes_are_percent_of_the_layer_and_read_as_cubes() -> None:
    groups = [
        {"s": "EnvObj_D1_A_HiddenBox_01", "pos": [[0, 150, 0], [-4080, 130, 4080]]}
    ]  # the far one: its group, 140
    doc = {
        "mapName": "Altgard",
        "categories": [{"id": CATEGORY}],
        "nodes": ic.cube_nodes(groups, ground(100), CATEGORY, [0]),
    }

    nodes = validate_objects(doc)["nodes"]

    assert nodes == [
        {"c": CATEGORY, "x": 50.0, "y": 50.0, "t": "Hidden Cube", "d": "", "l": 1, "g": 0},
        {"c": CATEGORY, "x": 0.0, "y": 100.0, "t": "Hidden Cube", "d": "", "g": 0},
    ]


def test_the_cubes_replace_the_old_ones_where_they_stood() -> None:
    doc = {
        "nodes": [
            {"categoryId": "teleports", "id": "t1"},
            {"categoryId": CATEGORY, "id": "old1"},
            {"categoryId": CATEGORY, "id": "old2"},
            {"categoryId": "seals", "id": "s1"},
        ]
    }
    new = [{"categoryId": CATEGORY, "id": "new1"}]

    ids = [n["id"] for n in ic.merged(doc, CATEGORY, new)["nodes"]]

    assert ids == ["t1", "new1", "s1"]


def test_a_set_without_cubes_gets_them_at_the_end() -> None:
    doc = {"nodes": [{"categoryId": "teleports", "id": "t1"}]}
    new = [{"categoryId": CATEGORY, "id": "new1"}]

    assert [n["id"] for n in ic.merged(doc, CATEGORY, new)["nodes"]] == ["t1", "new1"]


def test_the_ground_leaves_the_upstream_cubes_and_markers_without_a_height_out() -> None:
    markers = [
        {"subtype": "gatheringOdyle", "x": 1, "y": 2, "z": 3},
        {"subtype": "hiddenCube", "x": 1, "y": 2, "z": 3},
        {"subtype": "teleport", "x": 1, "y": 2},
    ]

    assert ic.ground_markers(markers) == [(1.0, 2.0, 3.0)]


def test_every_spot_of_a_group_wears_the_group_s_tint() -> None:
    groups = [
        {"s": "EnvObj_L1_A_HiddenCube_01", "pos": [[0, 0, 0], [10, 0, 0]]},
        {"s": "EnvObj_L1_B_HiddenCube_01", "pos": [[2000, 0, 0]]},
    ]

    nodes = ic.cube_nodes(groups, [], CATEGORY, [3, 5])

    assert [n["tint"] for n in nodes] == [3, 3, 5]


def spots(*xs: float) -> dict[str, object]:
    """A group with a spot at each x, on the world's middle line."""
    return {"s": "EnvObj_L1_A_HiddenCube_01", "pos": [[x, 0, 0] for x in xs]}


def test_groups_with_spots_near_each_other_are_neighbours() -> None:
    near = ic.neighbours([[ic.layer_px(x, 0) for x in g] for g in ([0, 1000], [1100], [3000])])

    assert near == [{1}, {0}, set()]


def test_neighbouring_groups_get_different_tints() -> None:
    groups = [spots(0), spots(60), spots(120), spots(3000)]  # three all within NEIGHBOURS

    tint_of, same = ic.group_tints(groups, 3)

    assert same == 0
    assert len(set(tint_of[:3])) == 3


def test_with_too_few_tints_the_clash_is_counted() -> None:
    groups = [spots(0), spots(50), spots(100)]

    tint_of, same = ic.group_tints(groups, 2)

    assert sorted(tint_of) == [0, 0, 1]
    assert same == 1


def test_the_tints_file_matches_the_one_the_app_reads() -> None:
    assert ic.TINTS == REPO / "assets" / "marks" / "cubes.json"
    assert cube_tints()[0]["id"] == "coral"
