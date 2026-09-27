"""validate_objects: the one format a third party is invited to write a converter for.

The format's documented description is what that promise rests on, and every rule asserted here
is stated there. The numbers that appear in both places -- the 0..100 percentage range, three
decimal places, the neutral grey -- are marked, so that changing one without the other is a test
failure rather than a silent lie in the documentation.
"""

import logging
from typing import Any

import pytest

from map_overlay.core.errors import ObjectsError
from map_overlay.store.objects import validate_objects

OBJECTS_LOGGER = "map_overlay.store.objects"

# The documented format's "Complete minimal example": a root category, a child, a category with no
# colour of its own, and nodes with and without a description.
MINIMAL_EXAMPLE: dict[str, Any] = {
    "mapName": "Altgard",
    "categories": [
        {"id": "locations", "name": "Locations", "color": "#22c55e"},
        {"id": "teleports", "name": "Teleports", "parentId": "locations", "color": "#16a34a"},
        {"id": "collectibles", "name": "Collectibles"},
    ],
    "nodes": [
        {
            "categoryId": "teleports",
            "x": 39.03,
            "y": 34.8,
            "title": "Teleport",
            "description": "Altgard Ice Lake",
        },
        {
            "categoryId": "teleports",
            "x": 52.117,
            "y": 48.9,
            "title": "Teleport",
            "description": "Black Claw Outpost",
        },
        {
            "categoryId": "collectibles",
            "x": 41.2,
            "y": 36.55,
            "title": "Empyrean Trace",
            "description": "SafeHaven",
        },
    ],
}


def _doc(**overrides: Any) -> dict[str, Any]:
    """A minimal valid set, so a test can vary exactly one thing about it."""
    base: dict[str, Any] = {
        "mapName": "Altgard",
        "categories": [{"id": "teleports", "name": "Teleports", "color": "#16a34a"}],
        "nodes": [{"categoryId": "teleports", "x": 39.03, "y": 34.8, "title": "Teleport"}],
    }
    base.update(overrides)
    return base


def test_the_documented_minimal_example_validates() -> None:
    """The format calls this example "checked against validate_objects"; this is the check."""
    doc = validate_objects(MINIMAL_EXAMPLE)

    assert doc["mapName"] == "Altgard"
    assert [c["id"] for c in doc["categories"]] == ["locations", "teleports", "collectibles"]
    assert len(doc["nodes"]) == 3
    assert doc["nodes"][0] == {
        "c": "teleports",
        "x": 39.03,
        "y": 34.8,
        "t": "Teleport",
        "d": "Altgard Ice Lake",
    }


# --- the two node spellings -------------------------------------------------------------------


def test_the_long_spelling_is_accepted() -> None:
    """categoryId/title/description is the spelling the sets in assets/object-sets use."""
    doc = validate_objects(
        _doc(
            nodes=[
                {
                    "categoryId": "teleports",
                    "x": 10.0,
                    "y": 20.0,
                    "title": "Teleport",
                    "description": "Altgard Ice Lake",
                }
            ]
        )
    )

    assert doc["nodes"] == [
        {"c": "teleports", "x": 10.0, "y": 20.0, "t": "Teleport", "d": "Altgard Ice Lake"}
    ]


def test_the_short_stored_spelling_is_accepted() -> None:
    """c/t/d is what the app writes back, so a set saved once must still read."""
    doc = validate_objects(
        _doc(
            nodes=[
                {"c": "teleports", "x": 10.0, "y": 20.0, "t": "Teleport", "d": "Altgard Ice Lake"}
            ]
        )
    )

    assert doc["nodes"] == [
        {"c": "teleports", "x": 10.0, "y": 20.0, "t": "Teleport", "d": "Altgard Ice Lake"}
    ]


def test_the_long_spelling_wins_when_a_node_carries_both() -> None:
    """The rule is `categoryId or c`, so a truthy long spelling decides. Never emit both."""
    doc = validate_objects(
        _doc(
            categories=[{"id": "teleports"}, {"id": "collectibles"}],
            nodes=[
                {
                    "categoryId": "teleports",
                    "c": "collectibles",
                    "title": "long",
                    "t": "short",
                    "description": "long description",
                    "d": "short description",
                    "x": 1.0,
                    "y": 2.0,
                }
            ],
        )
    )

    assert doc["nodes"][0]["c"] == "teleports"
    assert doc["nodes"][0]["t"] == "long"
    assert doc["nodes"][0]["d"] == "long description"


def test_an_empty_long_spelling_falls_through_to_the_short_one() -> None:
    """`or` reads falsy as absent, so an empty string is not a way to blank a field."""
    doc = validate_objects(
        _doc(
            nodes=[
                {
                    "categoryId": "",
                    "c": "teleports",
                    "title": "",
                    "t": "short",
                    "description": "",
                    "d": "short description",
                    "x": 1.0,
                    "y": 2.0,
                }
            ]
        )
    )

    assert doc["nodes"][0]["c"] == "teleports"
    assert doc["nodes"][0]["t"] == "short"
    assert doc["nodes"][0]["d"] == "short description"


def test_a_node_with_neither_title_nor_description_gets_empty_strings() -> None:
    doc = validate_objects(_doc(nodes=[{"c": "teleports", "x": 1.0, "y": 2.0}]))

    assert doc["nodes"] == [{"c": "teleports", "x": 1.0, "y": 2.0, "t": "", "d": ""}]


# --- categories -------------------------------------------------------------------------------


def test_a_category_without_an_id_is_dropped_and_its_siblings_survive() -> None:
    """One malformed entry must not cost the converter author the rest of the file."""
    doc = validate_objects(
        _doc(
            categories=[
                {"name": "No id at all"},
                {"id": "", "name": "Empty id"},
                {"id": None, "name": "Null id"},
                "not a mapping",
                {"id": "teleports", "name": "Teleports"},
            ]
        )
    )

    assert [c["id"] for c in doc["categories"]] == ["teleports"]


def test_category_fields_default_to_the_id_the_neutral_grey_and_no_parent() -> None:
    """#8f99ad is the documented neutral default; the editor treats it as "inherit"."""
    doc = validate_objects(_doc(categories=[{"id": "teleports"}]))

    assert doc["categories"] == [
        {"id": "teleports", "name": "teleports", "parentId": None, "color": "#8f99ad"}
    ]


def test_a_falsy_parent_id_becomes_none_rather_than_an_empty_string() -> None:
    doc = validate_objects(_doc(categories=[{"id": "teleports", "parentId": ""}]))

    assert doc["categories"][0]["parentId"] is None


def test_a_parent_id_is_stored_without_being_checked_against_the_other_categories() -> None:
    """Documented as deliberate: an unknown parent leaves the category a root in the panel."""
    doc = validate_objects(_doc(categories=[{"id": "teleports", "parentId": "nowhere"}]))

    assert doc["categories"][0]["parentId"] == "nowhere"


def test_a_duplicate_category_id_keeps_the_last_entry() -> None:
    doc = validate_objects(
        _doc(
            categories=[
                {"id": "teleports", "name": "first"},
                {"id": "teleports", "name": "second"},
            ]
        )
    )

    assert doc["categories"] == [
        {"id": "teleports", "name": "second", "parentId": None, "color": "#8f99ad"}
    ]


def test_a_non_string_category_id_is_stringified_on_both_sides() -> None:
    """A JSON number as an id still has to join up with the nodes that name it."""
    doc = validate_objects(_doc(categories=[{"id": 7}], nodes=[{"c": 7, "x": 1.0, "y": 2.0}]))

    assert doc["categories"][0]["id"] == "7"
    assert doc["nodes"][0]["c"] == "7"


# --- the percentage filter --------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 0.0, 50.0, 100, 100.0])
def test_a_coordinate_on_or_inside_the_percentage_bounds_is_kept(value: float) -> None:
    """The documented range is 0 <= v <= 100, inclusive at both ends."""
    doc = validate_objects(_doc(nodes=[{"c": "teleports", "x": value, "y": value}]))

    assert doc["nodes"][0]["x"] == float(value)


@pytest.mark.parametrize("value", [-0.001, -0.1, -1.0, 100.001, 100.1, 101.0, float("nan")])
def test_a_coordinate_outside_the_percentage_bounds_is_dropped(value: float) -> None:
    """The usual symptom of a converter that emitted pixels instead of percentages.

    NaN is here because it fails every comparison, so it is dropped by the same guard.
    """
    doc = validate_objects(
        _doc(
            nodes=[
                {"c": "teleports", "x": value, "y": 50.0},
                {"c": "teleports", "x": 50.0, "y": value},
                {"c": "teleports", "x": 50.0, "y": 50.0},
            ]
        )
    )

    assert doc["nodes"] == [{"c": "teleports", "x": 50.0, "y": 50.0, "t": "", "d": ""}]


@pytest.mark.parametrize(
    "node",
    [
        {"c": "teleports", "y": 50.0},
        {"c": "teleports", "x": 50.0},
        {"c": "teleports", "x": None, "y": 50.0},
        {"c": "teleports", "x": "not a number", "y": 50.0},
        {"c": "teleports", "x": [50.0], "y": 50.0},
        {"c": "teleports", "x": {"v": 50.0}, "y": 50.0},
    ],
)
def test_a_coordinate_that_cannot_be_read_as_a_number_drops_the_node(node: dict[str, Any]) -> None:
    doc = validate_objects(_doc(nodes=[node, {"c": "teleports", "x": 50.0, "y": 50.0}]))

    assert doc["nodes"] == [{"c": "teleports", "x": 50.0, "y": 50.0, "t": "", "d": ""}]


def test_a_numeric_string_coordinate_is_accepted() -> None:
    """Tolerated so a naive CSV converter works, though real numbers are what to emit."""
    doc = validate_objects(_doc(nodes=[{"c": "teleports", "x": "39.03", "y": "34.8"}]))

    assert doc["nodes"][0]["x"] == 39.03
    assert doc["nodes"][0]["y"] == 34.8


def test_coordinates_are_rounded_to_three_decimals() -> None:
    """Three places is 0.08 px on an 8192 px map, well under the vision matcher's accuracy."""
    doc = validate_objects(_doc(nodes=[{"c": "teleports", "x": 39.0306789, "y": 34.7994321}]))

    assert doc["nodes"][0]["x"] == 39.031
    assert doc["nodes"][0]["y"] == 34.799


def test_a_node_that_is_not_a_mapping_is_skipped() -> None:
    doc = validate_objects(
        _doc(nodes=["a string", 42, None, [1, 2], {"c": "teleports", "x": 1.0, "y": 2.0}])
    )

    assert doc["nodes"] == [{"c": "teleports", "x": 1.0, "y": 2.0, "t": "", "d": ""}]


# --- unknown categories -----------------------------------------------------------------------


def test_a_node_naming_an_unknown_category_is_dropped_without_a_word(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Documented as silent: no error and no log line, which is the trap for a converter."""
    with caplog.at_level(logging.DEBUG, logger=OBJECTS_LOGGER):
        doc = validate_objects(
            _doc(
                nodes=[
                    {"c": "ghost", "x": 1.0, "y": 2.0},
                    {"c": "teleports", "x": 3.0, "y": 4.0},
                ]
            )
        )

    assert doc["nodes"] == [{"c": "teleports", "x": 3.0, "y": 4.0, "t": "", "d": ""}]
    assert [r for r in caplog.records if r.name == OBJECTS_LOGGER] == []


def test_a_node_whose_category_was_dropped_for_having_no_id_goes_with_it() -> None:
    """The two filters compose: losing a category silently loses every node under it."""
    doc = validate_objects(
        _doc(
            categories=[{"name": "Teleports"}, {"id": "keep"}],
            nodes=[{"c": "", "x": 1.0, "y": 2.0}, {"c": "keep", "x": 3.0, "y": 4.0}],
        )
    )

    assert doc["nodes"] == [{"c": "keep", "x": 3.0, "y": 4.0, "t": "", "d": ""}]


def test_a_set_emptied_by_the_category_filter_is_rejected_outright() -> None:
    with pytest.raises(ObjectsError) as excinfo:
        validate_objects(_doc(nodes=[{"c": "ghost", "x": 1.0, "y": 2.0}]))

    assert excinfo.value.code == "objects.invalid.empty"


# --- whole-file failures ----------------------------------------------------------------------


@pytest.mark.parametrize("nodes", [[], None])
def test_a_set_with_no_nodes_is_rejected(nodes: list[Any] | None) -> None:
    with pytest.raises(ObjectsError) as excinfo:
        validate_objects(_doc(nodes=nodes))

    assert excinfo.value.code == "objects.invalid.empty"


def test_a_set_with_no_categories_is_rejected_because_every_node_loses_its_category() -> None:
    with pytest.raises(ObjectsError) as excinfo:
        validate_objects(_doc(categories=None))

    assert excinfo.value.code == "objects.invalid.empty"


@pytest.mark.parametrize("doc", [None, [], ["a"], "a string", 42, True])
def test_a_document_that_is_not_a_json_object_is_rejected(doc: Any) -> None:
    """read_json_or_none returns None for an unparseable file, so a BOM lands here too."""
    with pytest.raises(ObjectsError) as excinfo:
        validate_objects(doc)

    assert excinfo.value.code == "objects.invalid.not_object"


# --- normalisation ----------------------------------------------------------------------------


def test_unknown_keys_are_ignored_at_every_level() -> None:
    """The bundled sets carry backgroundImage and per-node ids; neither may cause a failure."""
    doc = validate_objects(
        {
            "mapName": "Altgard",
            "backgroundImage": "missing.png",
            "categories": [{"id": "teleports", "icon": "pin", "visible": True}],
            "nodes": [
                {"id": "oss-fafa4dee", "c": "teleports", "x": 1.0, "y": 2.0, "level": 25},
            ],
        }
    )

    assert doc["categories"] == [
        {"id": "teleports", "name": "teleports", "parentId": None, "color": "#8f99ad"}
    ]
    assert doc["nodes"] == [{"c": "teleports", "x": 1.0, "y": 2.0, "t": "", "d": ""}]


def test_a_missing_map_name_becomes_an_empty_string() -> None:
    """It seeds the stored file name, so import falls back to the source stem instead."""
    doc = validate_objects({"categories": [{"id": "a"}], "nodes": [{"c": "a", "x": 1.0, "y": 2.0}]})

    assert doc["mapName"] == ""


def test_the_normalised_output_carries_exactly_the_documented_keys() -> None:
    doc = validate_objects(MINIMAL_EXAMPLE)

    assert set(doc) == {"mapName", "categories", "nodes"}
    assert all(set(c) == {"id", "name", "parentId", "color"} for c in doc["categories"])
    assert all(set(n) == {"c", "x", "y", "t", "d"} for n in doc["nodes"])


def test_validating_a_stored_set_again_changes_nothing() -> None:
    """The format tells converter authors the app rewrites sets into the short form.

    That claim only holds if the short form is itself valid input, so a set that has been saved
    once reads back unchanged.
    """
    once = validate_objects(MINIMAL_EXAMPLE)

    assert validate_objects(once) == once
