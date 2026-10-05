"""Builds the dictionary getState() returns and stateChanged carries.

One function, not a method, so that the exact shape of the payload the UI depends on is
visible in one place rather than assembled across a facade. Adding a key here is safe; the UI
ignores what it does not know. Removing or renaming one is a contract change.
"""

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any, NotRequired, TypedDict

from map_overlay.core.settings import Region, settings_schema
from map_overlay.qt.overlay import marker_color
from map_overlay.store.routes import DEFAULT_STYLE
from map_overlay.updater.service import UpdatePayload


class Marker(TypedDict):
    """One route point, as it is stored and as it crosses to JavaScript."""

    x: float
    y: float
    text: str
    color: NotRequired[str]
    # "main" or "side": a quest icon beside the point's number (store/routes.MARKER_ICONS)
    icon: NotRequired[str]


class RouteDoc(TypedDict):
    """A whole route: the shape the editor loads and saves, and the routes/*.json file format.

    One set of keys serves both, so renaming one breaks the editor and every route already on
    a user's disk at the same time. `mapSize` records the map the marker coordinates were
    drawn against; a document is rescaled to the map's current size when it is opened or
    imported rather than stored twice.
    """

    format: str
    version: int
    name: str
    map: str
    mapSize: list[int]
    markers: list[Marker]
    style: dict[str, Any]


class TilesInfo(TypedDict):
    """Tile pyramid status on a MapInfo, read by the editor's Leaflet layer.

    Wire shape: the editor is built against these keys. `ready` is false while the pyramid is
    missing or still being cut, and the editor draws a placeholder instead of the map until it
    flips; `zMax` and `tile` are the depth and tile size Leaflet is configured with. A pyramid
    cut from a map's detail image goes deeper than zMax, down to `zNative`.
    """

    ready: bool
    zMax: int
    tile: int
    zNative: NotRequired[int]


class MapInfo(TypedDict):
    """A map as the panel and the editor see it."""

    id: str
    label: str
    size: list[int]
    faction: str | None  # "asmodian" or "elyos"; None for a map the manifest names no side for
    thumb: str
    tiles: TilesInfo
    objects: list[dict[str, Any]]
    resources: list[str]  # the gathering resources its sets have points of, in list order
    tilesUrl: NotRequired[str]


class RouteInfo(TypedDict):
    """A route in the list: enough to draw a row, without loading the document."""

    id: str
    label: str
    map: str
    mapLabel: str
    markers: int
    steps: int
    thumb: str
    faction: str | None  # the route's map's
    official: bool  # a starter route, exactly as a release shipped it


class StatsPayload(TypedDict):
    """Engine telemetry, emitted about four times a second."""

    found: bool
    anchored: bool
    fps: int
    processMs: float
    detectMs: float | None
    flowPoints: int
    matches: int
    inliers: int
    reprojError: float | None
    backend: str


class ProgressPayload(TypedDict):
    """What the panel's progress block draws, inside getState() and on progressChanged.

    Wire shape: the panel is built against these keys. `markers` repeats every point with its
    number, label and colour so the block can be drawn without the panel ever loading a route
    document, and `map` carries the map size in pixels, which is what lets the arrive radius
    be shown in map pixels instead of as a bare fraction. Since api 11 a point also carries its
    place on the map, which the panel finds the object under it by, and its quest icon if any.
    """

    done: int
    total: int
    map: list[int] | None
    markers: list[dict[str, Any]]


class StepsPayload(TypedDict):
    """The steps plaque's placement and size, for the panel's steps controls.

    Wire shape: it reaches the panel both as getState()["steps"] and on its own stepsChanged
    signal. The separate signal is the point of this type existing -- the plaque is dragged
    and resized several times a second, and answering that with the whole state would read
    every route and map each time. The plaque window itself is fed by Python, not by this.
    """

    visible: bool
    region: Region | None
    pinned: bool
    size: str


def steps_of(
    doc: RouteDoc | None, objects: Sequence[str] = ()
) -> list[tuple[int, str, str, str, str]]:
    """Route points for the steps plaque: numbers and colours as on the overlay, the quest icon
    a point was given, and the icon of the object it sits on (`objects`, in marker order), each
    or "".

    Unnamed points are included too. Without them the list gives no sense of how far it is to
    the next labelled step.
    """
    if not doc:
        return []
    markers = doc["markers"]
    base = doc["style"]["color"]
    return [
        (
            i + 1,
            m["text"].strip(),
            marker_color(m, base, i, len(markers)),
            m.get("icon", ""),
            objects[i] if i < len(objects) else "",
        )
        for i, m in enumerate(markers)
    ]


def progress_state(doc: RouteDoc | None, done: int) -> ProgressPayload:
    """For the panel: how far along, and every point with its label, colour and place."""
    markers = doc["markers"] if doc else []
    base = doc["style"]["color"] if doc else DEFAULT_STYLE["color"]
    points: list[dict[str, Any]] = []
    for i, m in enumerate(markers):
        point = {
            "n": i + 1,
            "text": m["text"],
            "color": marker_color(m, base, i, len(markers)),
            "x": m["x"],
            "y": m["y"],
        }
        icon = m.get("icon")
        if icon:
            point["icon"] = icon
        points.append(point)
    return {
        "done": done,
        "total": len(markers),
        "map": doc["mapSize"] if doc else None,  # lets the panel show the radius in map pixels
        "markers": points,
    }


def steps_state(settings, state) -> StepsPayload:
    return {
        "visible": state.steps_visible,
        "region": state.steps_region,
        "pinned": settings.steps_pinned,
        "size": settings.steps_size,
    }


# Bumped when a slot or a payload key is added, so the UI can tell what it is talking to.
# 3: isPortable.
# 4: update; checkForUpdates, downloadUpdate, installUpdate, skipUpdate; updateChanged.
# 5: settingsSchema, resetSettings, captureExclusion.
# 6: repoUrl; openUrl. addMap and deleteMap removed -- the two maps ship with the app.
# 7: "bundled" on a map's object sets -- the sets that ship with the app.
# 8: addObjects and removeObjects removed -- a map's object sets ship with it and are fixed.
# 9: a route marker may carry "icon" ("main" or "side"), and so may the plaque's steps.
# 10: a map's tiles may carry "zNative", when they are cut from an image finer than the map.
# 11: start() with no map area asks for one and then starts, where it used to refuse; a
#     progress marker carries its x and y, and its quest icon where it has one; settings has
#     steps_scale; a plaque step carries "object", the icon of what it sits on, and the
#     plaque's data its "scale" and "switch"; the plaque's action takes "prev" and "next".
# 12: settings has route_view, route_ahead and route_past.
# 13: settings has editor_route_view, editor_route_ahead and editor_opacity.
# 14: the plaque's data carries "past", how many steps already passed it lists (route_past).
# 15: resetRegion() forgets the map area.
# 16: progress always counts, and settings.progress_enabled is read by nothing; auto_progress
#     alone governs the arrival ring and the player's position. The plaque's "prev" and "next"
#     take the last point back and tick the next one off, where they went to another route, and
#     "switch" is always true.
# 17: reorderRoutes() sets the order the routes are listed in; a new route is listed last.
# 18: the plaque is sized by the user, by its right and bottom edges, and its data carries
#     "grip", how wide those strips are; setHeight is read by nothing.
# 19: links, the donation page and the Discord invite, which openUrl() opens as well; copyText.
# 20: a map carries "faction", and a route its map's faction and "official".
# 21: links has partnerDiscord, the invite to Aion 2 Global's server, which openUrl() opens.
# 22: banner, the advertising banner that ships with the app, whose url openUrl() opens.
# 23: settings has show_cubes and cube_radius: the map's hidden cubes over the game, each in a
#     ring; overlayVisible governs the route alone, and the overlay is up while either is drawn.
# 24: settings has route_traces; off, the route's feather points are left out of the overlay, the
#     plaque and the progress, whose done, total and markers count only the points shown.
# 25: settings has route_seals, which does the same for the route's points on sealed dungeons.
# 26: settings has show_resources and resources, the gathering resources drawn over the game, and
#     a map carries "resources", those its sets have; settingsSchema may describe a "list" field.
# 27: settings has route_mode, off for a map of its objects alone with no route followed, and
#     route_far_notice; the panel no longer calls setOverlayVisible, which still works.
# 28: timers, the event and world-boss timers (null when no schedule loads), with the signal
#     timersChanged and the slots setTimerEvent, setTimersWorldShown and refreshTimersData;
#     settings has the timers_* fields, and settingsSchema may describe a "map" field.
API_VERSION = 28


def build_state(
    *,
    version: str,
    settings,
    state,
    maps: list[MapInfo],
    routes: list[RouteInfo],
    running: bool,
    overlay_visible: bool,
    capture_backend: str | None,
    platform: str,
    progress: ProgressPayload,
    editor_open: bool,
    tiles_busy: list[str],
    dev: bool,
    portable: bool,
    update: UpdatePayload,
    capture_exclusion: bool,
    repo_url: str,
    links: dict[str, str],
    banner: dict[str, str] | None,
    timers: dict[str, Any] | None,
) -> dict[str, Any]:
    """The getState() payload.

    `settingsSchema` is the ranges and choices coerce() enforces, so the panel's controls
    offer exactly what the file accepts. `captureExclusion` is false on a Windows too old to
    hide a window from capture, where the overlay is always visible to recorders and the engine.
    `repoUrl` is the project's GitHub repository, the only site openUrl() opens pages of, and
    `links` the exact addresses it opens beside it: `donate`, `discord` and `partnerDiscord`.
    `banner` is the bundled advertising banner, {"image", "url", "label"} and, with a discount
    code to offer, {"code", "discount"}, or None; openUrl() opens its `url` as well.
    `timers` is timers/view.py's timers_view(), or None when no schedule loads.
    """
    return {
        "version": version,
        "api": API_VERSION,
        "running": running,
        "overlayVisible": overlay_visible,
        "captureVisible": settings.capture_visible,
        "region": state.region,
        "route": state.route,
        "routes": routes,
        "maps": maps,
        "settings": asdict(settings),
        "settingsSchema": settings_schema(),
        "captureExclusion": capture_exclusion,
        "captureBackend": capture_backend,
        "platform": platform,
        "steps": steps_state(settings, state),
        "progress": progress,
        "editorOpen": editor_open,
        "tilesBusy": tiles_busy,
        "dev": dev,
        "isPortable": portable,
        "update": update,
        "repoUrl": repo_url,
        "links": links,
        "banner": banner,
        "timers": timers,
    }
