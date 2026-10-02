"""The gathering resources: the catalog the overlay and the lists both draw them by.

assets/marks/resources.json is read by the UI as well (ui/src/shared/ui/markIcons.ts), so what
is pinned here is that every resource there can be drawn and that a set's categories map onto
the resources as both sides expect: gathering-<id>.
"""

import json

from PySide6.QtCore import QByteArray
from PySide6.QtSvg import QSvgRenderer

from map_overlay.core.paths import resource_path
from map_overlay.store.resources import (
    catalog,
    resource_ids,
    resource_of,
    resource_points,
    resource_svg,
    resources_in,
)


def test_every_resource_has_a_shape_and_the_colours_the_shape_asks_for() -> None:
    doc = catalog()
    assert resource_ids()
    for res in doc["resources"]:
        layers = doc["shapes"][res["shape"]]
        roles = {
            layer[key]
            for layer in layers
            for key in ("fill", "stroke")
            if key in layer and not layer[key].startswith("#")
        }
        assert roles <= set(res["colors"]), res["id"]


def test_every_resource_renders_as_svg() -> None:
    for rid in resource_ids():
        svg = resource_svg(rid)
        assert svg is not None
        assert QSvgRenderer(QByteArray(svg.encode())).isValid(), rid
    assert resource_svg("no-such-resource") is None


def test_a_category_is_a_resource_by_its_prefix() -> None:
    assert resource_of("gathering-odyle") == "odyle"
    assert resource_of("gathering") is None
    assert resource_of("gathering-") is None
    assert resource_of("hidden-cube-altgard") is None


def test_points_and_presence_are_read_off_the_nodes() -> None:
    sets = [
        {
            "nodes": [
                {"c": "gathering-ruby", "x": 50.0, "y": 25.0},
                {"c": "gathering-odyle", "x": 10.0, "y": 10.0},
                {"c": "teleports", "x": 1.0, "y": 1.0},
            ]
        }
    ]

    assert resource_points(sets, (1000, 2000)) == {
        "ruby": [(500.0, 500.0)],
        "odyle": [(100.0, 200.0)],
    }
    assert resources_in(sets) == ["odyle", "ruby"]  # the catalog's order, not the set's


def test_the_bundled_sets_hold_only_resources_the_catalog_draws() -> None:
    known = set(resource_ids())
    for name in ("verteron", "altgard"):
        doc = json.loads(resource_path(f"assets/object-sets/{name}.json").read_text("utf-8"))
        ids = {resource_of(c["id"]) for c in doc["categories"]} - {None}
        assert ids, name
        assert ids <= known, name
