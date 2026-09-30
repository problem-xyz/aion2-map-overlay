"""Maps, routes, object sets and share codes, on top of store/.

Everything here is about documents on disk. It holds no widgets and shows no dialogs: when a
choice is needed the caller passes one in. That is what lets the same code be exercised without
a screen.

The active document is cached because the overlay redraws at the frame rate and must not read
a route file fifteen times a second.
"""

import logging
from pathlib import Path
from typing import Any

from map_overlay.core.errors import AppError, MapError, RouteError
from map_overlay.i18n.catalog import t
from map_overlay.qt.webview import local_file_url
from map_overlay.store import maps as maps_store
from map_overlay.store import naming, objects, routes, share
from map_overlay.store.maps import MapSpec, ThumbCache, load_bundled_maps

log = logging.getLogger(__name__)


class RouteService:
    """Every read and write of maps, routes and object sets, in one object.

    It shows no dialog and touches no widget, which is what lets it run without a screen:
    where a choice is needed the caller passes a callable in. It raises no toast either --
    a failure leaves as an AppError or as the error slot of a returned tuple, and the facade
    decides what the user is told.

    The maps are the bundled registry, loaded once here; `maps` is a parameter so that a test
    can hand in small ones instead of cutting the shipped 8192 px images into tiles.

    `active_doc` is the cache the overlay redraws from at frame rate. Whoever changes the
    active route is responsible for replacing it; nothing here keeps it in step.
    """

    def __init__(self, dirs, dev=False, maps: tuple[MapSpec, ...] | None = None) -> None:
        self.dirs = dirs
        self.dev = bool(dev)
        self.registry: tuple[MapSpec, ...] = load_bundled_maps() if maps is None else tuple(maps)
        self.thumbs = ThumbCache()
        self.skipped = routes.SkippedRoutes()
        self.active_doc = None

    # ------------------------------------------------------------------ maps
    def maps(self):
        out = maps_store.list_maps(self.dirs, self.registry, self.thumbs)
        for m in out:
            m["tilesUrl"] = self.tiles_url(m["id"])
        return out

    def spec_for(self, map_id) -> MapSpec | None:
        return next((spec for spec in self.registry if spec.id == map_id), None)

    def tiles_url(self, map_id):
        """Tile base address. In dev the page is on localhost and Vite serves the files."""
        return local_file_url(maps_store.map_dir(self.dirs, map_id) / "tiles", self.dev)

    def map_meta(self, map_id):
        """{"label", "size"} of a bundled map, or None for an id the registry does not have."""
        spec = self.spec_for(map_id)
        return {"label": spec.label, "size": list(spec.size)} if spec else None

    # ------------------------------------------------------------------ routes
    def list_routes(self, maps_by_id, order=()):
        """Every route, in the order `order` gives; one it does not name comes last."""
        return routes.list_routes(self.dirs, maps_by_id, self.thumbs, self.skipped, order)

    def take_skipped(self):
        """RouteErrors for the files list_routes left out since the last call, each once."""
        return self.skipped.take()

    def route_doc(self, route_id):
        """Raises OSError or ValueError; the caller decides whether that is worth a toast."""
        return routes.load_route(self.dirs, route_id)

    def seed_bundled(self, seeded):
        """Copy the starter routes not in `seeded` into routes/ and update the untouched ones."""
        return routes.seed_bundled_routes(self.dirs, seeded)

    def route_exists(self, route_id):
        return routes.route_path(self.dirs, route_id).exists()

    def save_route(self, route_id, doc):
        return routes.save_route(self.dirs, route_id, doc)

    def delete_route(self, route_id) -> None:
        routes.delete_route(self.dirs, route_id)

    def new_route_id(self, name):
        return naming.unique_route_id(self.dirs, name)

    def reference_for(self, doc):
        return self.reference_for_map(doc["map"])

    def reference_for_map(self, map_id) -> Path | None:
        """The reference image of a bundled map, or None for an id the registry does not have."""
        spec = self.spec_for(map_id)
        return spec.reference if spec else None

    def tiles_source_for_map(self, map_id) -> Path | None:
        """The image a map's tiles are cut from, or None for an id the registry does not have."""
        spec = self.spec_for(map_id)
        return spec.tiles_source if spec else None

    # ------------------------------------------------------------------ objects
    def load_objects(self, map_id):
        """The sets that ship with the map: a map has those and no others."""
        spec = self.spec_for(map_id)
        return [
            doc
            for b in (spec.objects if spec else ())
            if (doc := objects.load_bundled_set(b.path, b.file)) is not None
        ]

    # ------------------------------------------------------------------ document operations
    def prepare_import(self, doc, pick_map):
        """Fit an incoming route onto a map this installation actually has.

        Returns (doc, note) or (None, reason); note is "rescaled" whenever the points had to be
        moved to fit, whether the map is the route's own or one picked in place of it. pick_map
        is called only when the route names a map this version does not have, and may return
        None if the user cancels -- which is why it is passed in rather than imported: this
        class shows no dialogs.
        """
        maps = self.maps()
        target = next((m for m in maps if m["id"] == doc["map"]), None)
        if target is None:
            target = pick_map(maps)
            if target is None:
                return None, "cancelled"
            doc = dict(doc, map=target["id"])

        if doc["mapSize"] != target["size"]:
            return self.rescale_route(doc, target["size"]), "rescaled"
        return doc, None

    def store_new(self, doc):
        """Save a route under a fresh id and return it. Raises what save_route raises."""
        route_id = self.new_route_id(doc["name"])
        self.save_route(route_id, doc)
        return route_id

    def editor_doc(self, route_id):
        """The document to open in the editor. Empty route_id means a new route.

        Returns (doc, error). A saved route is rescaled to its map's current size, because it
        may have been drawn against a different reference.
        """
        if not route_id:
            maps = self.maps()
            first = maps[0] if maps else None
            return self.new_route_doc(
                t("editor.defaultName"),
                first["id"] if first else "",
                first["size"] if first else [0, 0],
            ), None
        try:
            doc = self.route_doc(route_id)
        except AppError as e:
            return None, e
        except OSError as e:
            return None, RouteError("route.not_found", id=route_id or str(e))
        meta = self.map_meta(doc["map"])
        return (self.rescale_route(doc, meta["size"]) if meta else doc), None

    def runnable_route(self, route_id):
        """(doc, reference_path, error) for starting the engine."""
        if not route_id:
            return None, None, RouteError("route.required")
        try:
            doc = self.route_doc(route_id)
        except AppError, OSError:
            return None, None, RouteError("route.required")
        ref = self.reference_for_map(doc["map"])
        if ref is None:
            return None, None, MapError("map.unknown", id=doc["map"])
        if not ref.exists():
            return None, None, MapError("map.reference_missing", path=str(ref))
        return doc, ref, None

    def parse_save_payload(self, payload):
        """(route_id, doc, error) for the editor's save call."""
        import json  # noqa: PLC0415 -- only the payload boundary needs it

        try:
            data = json.loads(payload)
            doc = self.validate_route(data.get("doc"))
        except AppError as e:
            return None, None, e
        except (ValueError, TypeError) as e:
            return None, None, RouteError("route.file_invalid", reason=str(e))
        if not doc["map"]:
            return None, None, RouteError("route.map_required")
        return data.get("id") or self.new_route_id(doc["name"]), doc, None

    # ------------------------------------------------------------------ sharing
    @staticmethod
    def encode_share(doc):
        return share.encode_share(doc)

    @staticmethod
    def decode_share(text):
        return share.decode_share(text)

    @staticmethod
    def validate_route(doc):
        return routes.validate_route(doc)

    @staticmethod
    def read_route_file(path: Path | str) -> dict[str, Any]:
        """Raises RouteError for a file that is too large or not a route, or OSError."""
        return routes.read_route_file(path)

    @staticmethod
    def export_route(doc: dict[str, Any], path: Path | str) -> None:
        """Raises RouteError for a route too large to read back, or OSError."""
        routes.export_route(doc, path)

    @staticmethod
    def rescale_route(doc, size):
        return routes.rescale_route(doc, size)

    @staticmethod
    def new_route_doc(name, map_id, map_size):
        return routes.new_route_doc(name, map_id, map_size)
