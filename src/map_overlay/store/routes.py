"""Route documents: numbered points on a map, one JSON file per route."""

import contextlib
import hashlib
import json
import logging
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from map_overlay.core.errors import AppError, RouteError
from map_overlay.core.fileio import atomic_write_bytes, backup_corrupt
from map_overlay.core.paths import DataDirs, resource_path
from map_overlay.store.images import _bgr, data_url, hex_color
from map_overlay.store.maps import ThumbCache, map_backdrop, map_dir
from map_overlay.store.naming import unique_route_id  # noqa: F401 -- part of the store API

log = logging.getLogger(__name__)

ROUTE_FORMAT = "map-overlay-route"
ROUTE_VERSION = 1
DEFAULT_STYLE = {"color": "#f2b544", "width": 3}

# Untrusted input: a share code or an imported file must not be able to make the app
# allocate an unbounded route.
MAX_MARKERS = 2000
# The icon a point may be given beside its number: a main quest or a side quest, a yellow star
# and a green one. Optional; anything else is dropped rather than refused, as an unknown colour is.
MARKER_ICONS = ("main", "side")

# The largest route file the app reads, from an import or from routes/ alike. Captions have no
# length limit, so the marker cap does not keep a route under it; save_route does, by refusing
# to write a larger one, and nothing the app writes is then a file it would refuse to read. For
# scale: the marker cap with a 200-character Cyrillic caption on every point saves to 0.95 MiB.
# MB here means MiB, as in Explorer.
MAX_ROUTE_FILE_MB = 5
MAX_ROUTE_FILE_BYTES = MAX_ROUTE_FILE_MB * 1024 * 1024

# Not user-facing: only the fallback stored in a document whose name is empty.
DEFAULT_ROUTE_NAME = "Route"


def new_route_doc(name: str, map_id: str, map_size: Any) -> dict[str, Any]:
    return {
        "format": ROUTE_FORMAT,
        "version": ROUTE_VERSION,
        "name": name,
        "map": map_id or "",
        "mapSize": [int(map_size[0]), int(map_size[1])] if map_size else [0, 0],
        "markers": [],
        "style": dict(DEFAULT_STYLE),
    }


def _validate_marker(m: Any) -> dict[str, Any]:
    """One route point, normalised: its keys in the file's order, what it may leave out left out."""
    if not isinstance(m, dict):
        raise RouteError("route.invalid.marker_not_object")
    try:
        x, y = float(m["x"]), float(m["y"])
    except (KeyError, TypeError, ValueError) as e:
        raise RouteError("route.invalid.marker_coords") from e
    if not (math.isfinite(x) and math.isfinite(y)):
        raise RouteError("route.invalid.marker_not_finite")
    point: dict[str, Any] = {"x": round(x, 2), "y": round(y, 2), "text": str(m.get("text") or "")}
    color = hex_color(m.get("color"))
    if color:  # no colour of its own: the marker is drawn in the route colour
        point["color"] = color
    icon = m.get("icon")
    if icon in MARKER_ICONS:
        point["icon"] = icon
    return point


def validate_route(doc: Any) -> dict[str, Any]:
    """Normalise a route document, or raise RouteError carrying a code the UI can translate.

    The result is rebuilt field by field, so unknown keys never survive into a saved file.
    """
    if not isinstance(doc, dict):
        raise RouteError("route.invalid.not_object")
    if doc.get("format") != ROUTE_FORMAT:
        raise RouteError("route.invalid.format")
    if int(doc.get("version", 0)) != ROUTE_VERSION:
        raise RouteError("route.invalid.version", version=doc.get("version"))

    name = str(doc.get("name") or DEFAULT_ROUTE_NAME).strip() or DEFAULT_ROUTE_NAME
    size = doc.get("mapSize") or [0, 0]
    try:
        map_size = [int(size[0]), int(size[1])]
    except (TypeError, ValueError, IndexError) as e:
        raise RouteError("route.invalid.map_size") from e

    incoming = doc.get("markers") or []
    if len(incoming) > MAX_MARKERS:
        raise RouteError("route.too_many_markers", limit=MAX_MARKERS)

    markers = [_validate_marker(m) for m in incoming]

    style = dict(DEFAULT_STYLE)
    src_style = doc.get("style")
    if isinstance(src_style, dict):
        color = hex_color(src_style.get("color"))
        if color:
            style["color"] = color
        with contextlib.suppress(TypeError, ValueError):
            style["width"] = max(1, min(12, int(src_style.get("width", style["width"]))))

    return {
        "format": ROUTE_FORMAT,
        "version": ROUTE_VERSION,
        "name": name,
        "map": str(doc.get("map") or ""),
        "mapSize": map_size,
        "markers": markers,
        "style": style,
    }


def rescale_route(doc: dict[str, Any], size: Any) -> dict[str, Any]:
    """Re-scale a route for a map of a different size: marker x/y are map pixels, not fractions."""
    w, h = int(size[0]), int(size[1])
    ow, oh = doc["mapSize"]
    if min(w, h, ow, oh) <= 0 or (ow, oh) == (w, h):
        return doc
    kx, ky = w / ow, h / oh
    out = dict(doc)
    out["mapSize"] = [w, h]
    out["markers"] = [
        {**m, "x": round(m["x"] * kx, 2), "y": round(m["y"] * ky, 2)} for m in doc["markers"]
    ]
    return out


def route_path(dirs: DataDirs, route_id: str) -> Path:
    return dirs.routes / f"{route_id}.json"


def backup_path(dirs: DataDirs, route_id: str) -> Path:
    """The version a save replaced. Its suffix keeps it out of every *.json listing."""
    return dirs.routes / f"{route_id}.json.bak"


def route_bytes(doc: dict[str, Any]) -> bytes:
    """A validated route as the bytes of its file: what atomic_write_json would write.

    Save and export both write these, and both are refused with route.too_large past the file
    limit, so that no route file the app writes is one it would refuse to read back.
    """
    data = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    if len(data) > MAX_ROUTE_FILE_BYTES:
        raise RouteError("route.too_large", limit=MAX_ROUTE_FILE_MB)
    return data


def _read_capped(path: Path) -> bytes:
    """A route file's bytes, or route.file_too_large for a file past MAX_ROUTE_FILE_BYTES.

    The size is checked before the file is opened, and the read stops one byte past the cap,
    so a file that grew after the stat, or holds more than it reports, is refused as well and
    never read in full. OSError is left to the caller.
    """
    if path.stat().st_size > MAX_ROUTE_FILE_BYTES:
        raise RouteError("route.file_too_large", limit=MAX_ROUTE_FILE_MB)
    with path.open("rb") as f:
        data = f.read(MAX_ROUTE_FILE_BYTES + 1)
    if len(data) > MAX_ROUTE_FILE_BYTES:
        raise RouteError("route.file_too_large", limit=MAX_ROUTE_FILE_MB)
    return data


def _decode(data: bytes) -> Any:
    """JSON from a route file's bytes, or ValueError for bytes that are not UTF-8 JSON.

    JSON nested deeper than the parser can descend raises RecursionError, which is no
    ValueError, and some tens of kilobytes of brackets are enough to reach it.
    """
    try:
        return json.loads(data.decode("utf-8"))
    except RecursionError as e:
        raise ValueError(str(e)) from e


def _validated(raw: Any) -> dict[str, Any]:
    """validate_route for a document read from a file, refusing only with RouteError.

    A crafted document still gets bare exceptions out of validate_route: int() of a list as
    the version, a dict as mapSize, an integer too large for a float. A reader must not let
    them through; in the route list one would take the whole panel state down with it. The
    version case is the defect filed separately (VERSION_TYPE_DEFECT in the tests).
    """
    try:
        return validate_route(raw)
    except (TypeError, ValueError, KeyError, OverflowError) as e:
        raise RouteError("route.file_invalid", reason=str(e)) from e


def read_route_file(path: Path | str) -> dict[str, Any]:
    """A route from a file the user picked, refused on its size before any of it is read.

    Raises RouteError for a file that is too large or is not a route -- not UTF-8, not JSON,
    or a document validate_route refuses -- and lets OSError through for the caller to word.
    """
    data = _read_capped(Path(path))
    try:
        raw = _decode(data)
    except ValueError as e:
        raise RouteError("route.file_invalid", reason=str(e)) from e
    return _validated(raw)


def load_route(dirs: DataDirs, route_id: str) -> dict[str, Any]:
    """The route saved under route_id, read under the same size limit as an import."""
    path = route_path(dirs, route_id)
    if not path.exists():
        raise RouteError("route.not_found", id=route_id)
    try:
        raw = _decode(_read_capped(path))
    except (OSError, ValueError) as e:
        # The file is there but unreadable -- a different problem from a missing route.
        # TODO: give the two separate codes.
        log.warning("cannot read %s", path, exc_info=True)
        raise RouteError("route.file_invalid", reason=str(path)) from e
    return _validated(raw)


def save_route(dirs: DataDirs, route_id: str, doc: Any) -> dict[str, Any]:
    """Write a route, keeping the version it replaces as <id>.json.bak.

    One backup, never a chain: each save overwrites the last. It is written before the new
    version replaces the file, so no moment has neither copy whole, and a backup that cannot
    be written fails the save. A first save has nothing to keep and writes none. A save that
    changes nothing leaves the backup alone, or pressing Save twice would replace the only
    older version with a copy of the current one. A route too large to read back is refused
    with route.too_large before anything is written.
    """
    doc = validate_route(doc)
    path = route_path(dirs, route_id)
    data = route_bytes(doc)  # serialised here to be compared with the old bytes
    try:
        previous = path.read_bytes()
    except FileNotFoundError:
        previous = None
    if previous is not None and previous != data:
        atomic_write_bytes(backup_path(dirs, route_id), previous)
    atomic_write_bytes(path, data)
    return doc


def export_route(doc: dict[str, Any], path: Path | str) -> None:
    """Write a route to a file the user chose, in the bytes a save would write."""
    atomic_write_bytes(path, route_bytes(doc))


def delete_route(dirs: DataDirs, route_id: str) -> None:
    """Delete a route and its backup, so the next route to take the id does not inherit it."""
    routes_dir = dirs.routes.resolve()
    for path in (route_path(dirs, route_id), backup_path(dirs, route_id)):
        if path.is_file() and path.resolve().parent == routes_dir:
            path.unlink()


# A route tile's picture, in pixels: wide, as the tile is, and about twice the tile's height on
# a 100% screen, so that it stays sharp at 150-200%.
THUMB_SIZE = (720, 120)
# Where across the picture the route is framed: right of the name, which sits over a dark fade
# on the left, and left of the edit and delete buttons on the right.
THUMB_ROUTE_SPAN = (0.40, 0.84)
# How much of the route's own height a tile keeps. It is fitted to the part of the tile between
# the name and the buttons by its width; a route taller than that is cut at the top and bottom
# rather than drawn so small that it takes in the whole width of the map.
THUMB_KEEP_HEIGHT = 0.8
# The least of the map a tile shows, as a height in backdrop pixels: a route of one point, or of
# a few close together, would otherwise be blown up into a blur.
THUMB_MIN_SPAN = 90.0


def thumb_frame(
    pts: np.ndarray, image_size: tuple[int, int], out_size: tuple[int, int] = THUMB_SIZE
) -> tuple[float, float, float]:
    """(left, top, scale): the part of an image a route tile shows, and how much it is enlarged.

    `pts` are the route's points in the image's pixels. The frame has the picture's proportions
    and takes the route's width in, with a margin, across THUMB_ROUTE_SPAN. It never leaves the
    image: past the edge there is nothing to show, so near one the frame is moved back onto it,
    which moves the route off the middle.
    """
    out_w, out_h = out_size
    aspect = out_w / out_h
    lo, hi = THUMB_ROUTE_SPAN
    img_w, img_h = image_size
    (x0, y0), (x1, y1) = pts.min(axis=0), pts.max(axis=0)
    pad = max(x1 - x0, y1 - y0) * 0.12 + 8.0
    span_w, span_h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    h = max(span_w / ((hi - lo) * aspect), span_h * THUMB_KEEP_HEIGHT, THUMB_MIN_SPAN)
    h = min(h, img_h, img_w / aspect)
    w = h * aspect
    left = (x0 + x1) / 2 - w * (lo + hi) / 2
    top = (y0 + y1) / 2 - h / 2
    left = min(max(left, 0.0), img_w - w)
    top = min(max(top, 0.0), img_h - h)
    return float(left), float(top), out_h / h


def _crop(
    img: np.ndarray, left: float, top: float, scale: float, out_size: tuple[int, int]
) -> np.ndarray:
    """The frame thumb_frame chose, at out_size. It lies on the image: no edge is made up."""
    out_w, out_h = out_size
    ih, iw = img.shape[:2]
    x0, y0 = max(0, math.floor(left)), max(0, math.floor(top))
    x1 = min(iw, math.ceil(left + out_w / scale))
    y1 = min(ih, math.ceil(top + out_h / scale))
    part = img[y0:y1, x0:x1]
    shrink = scale < 1.0
    return cv2.resize(part, out_size, interpolation=cv2.INTER_AREA if shrink else cv2.INTER_CUBIC)


def bundled_routes_root() -> Path:
    """The starter routes that ship with the app. Tests point this elsewhere."""
    return resource_path("assets/routes")


# Beside the starter routes: the digest of every version of them a release has shipped, one
# "<sha256>  <file name>" line each, in sha256sum's format. A route in routes/ whose bytes are one
# of these is a starter the user never changed, and a newer version may replace it.
SHIPPED_DIGESTS = "shipped.sha256"


def route_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def starter_bytes(src: Path) -> bytes:
    """A bundled route as the bytes it is copied into routes/ with, and so as a digest takes it."""
    return route_bytes(read_route_file(src))


def parse_shipped_digests(text: str) -> dict[str, set[str]]:
    """The digests in a SHIPPED_DIGESTS text, by route id. A line starting with # is a comment."""
    out: dict[str, set[str]] = {}
    for line in text.splitlines():
        digest, _, name = line.strip().partition("  ")
        if digest and name and not digest.startswith("#"):
            out.setdefault(Path(name).stem, set()).add(digest.lower())
    return out


def read_shipped_digests(root: Path) -> dict[str, set[str]]:
    try:
        return parse_shipped_digests((root / SHIPPED_DIGESTS).read_text(encoding="utf-8"))
    except OSError:
        return {}


def starter_digests(root: Path | None = None) -> dict[str, set[str]]:
    """Every version of each starter route, by id: those a release shipped and the one bundled now.

    A route in routes/ with one of these is a starter as it came, and the panel marks it official.
    """
    base = bundled_routes_root() if root is None else Path(root)
    out = read_shipped_digests(base)
    for src in base.glob("*.json"):
        try:
            out.setdefault(src.stem, set()).add(route_digest(starter_bytes(src)))
        except (AppError, OSError) as e:
            log.warning("bundled route %s is not read: %s", src.name, e)
    return out


def _is_official(path: Path, starters: Mapping[str, Collection[str]]) -> bool:
    digests = starters.get(path.stem)
    if not digests:
        return False
    try:
        return route_digest(path.read_bytes()) in digests
    except OSError:
        return False


def record_shipped_digests(root: Path, text: str) -> str:
    """`text`, a SHIPPED_DIGESTS file, with a line added for each route under `root` it lacks.

    Every release runs this, so the file holds each version a user may have been given.
    """
    known = parse_shipped_digests(text)
    lines = [text.rstrip("\n")] if text.strip() else []
    for src in sorted(root.glob("*.json"), key=lambda p: p.name.lower()):
        digest = route_digest(starter_bytes(src))
        if digest not in known.get(src.stem, set()):
            lines.append(f"{digest}  {src.name}")
    return "\n".join(lines) + "\n" if lines else ""


@dataclass(frozen=True)
class Seeded:
    """What seed_bundled_routes did: the ids to record as handled, and the routes it updated."""

    handled: list[str]
    updated: list[str]  # the route names, for the notice


def seed_bundled_routes(
    dirs: DataDirs, seeded: Collection[str], root: Path | None = None
) -> Seeded:
    """Copy each bundled route not in `seeded` into routes/, and update each one left untouched.

    A route is offered once per id, and the caller records the ids handled so that a route the
    user deleted does not come back on the next start. An id already taken in routes/ -- by the
    route itself, a share code of it, or its .bak -- counts as handled.

    A route in routes/ whose bytes are a version a release shipped (SHIPPED_DIGESTS) is a starter
    nobody changed, and it is replaced by the version bundled now, the old one kept as its .bak.
    One the user edited, or a route of their own on the id, never matches and is left alone.

    A bundled file that does not read, or a copy that cannot be written, is only logged and
    tried again on the next start.
    """
    base = bundled_routes_root() if root is None else Path(root)
    if not base.is_dir():
        return Seeded([], [])
    shipped = read_shipped_digests(base)
    handled: list[str] = []
    updated: list[str] = []
    for src in sorted(base.glob("*.json"), key=lambda p: p.name.lower()):
        route_id = src.stem
        path = route_path(dirs, route_id)
        if path.exists():
            name = _update_untouched(dirs, src, shipped.get(route_id, set()))
            if name:
                updated.append(name)
            if route_id not in seeded:
                handled.append(route_id)
            continue
        if route_id in seeded:
            continue
        if backup_path(dirs, route_id).exists():
            handled.append(route_id)
            continue
        try:
            atomic_write_bytes(path, starter_bytes(src))
        except (AppError, OSError) as e:
            log.warning("bundled route %s is not copied: %s", src.name, e)
            continue
        log.info("bundled route %s copied into routes/", route_id)
        handled.append(route_id)
    return Seeded(handled, updated)


def _update_untouched(dirs: DataDirs, src: Path, shipped: set[str]) -> str | None:
    """Replace routes/<id>.json with `src` if it is an older shipped version; the route's name."""
    route_id = src.stem
    try:
        current = route_path(dirs, route_id).read_bytes()
        if route_digest(current) not in shipped:
            return None  # edited by the user, or not a starter at all
        doc = read_route_file(src)
        if route_bytes(doc) == current:
            return None
        save_route(dirs, route_id, doc)  # keeps the replaced version as the .bak
    except (AppError, OSError) as e:
        log.warning("bundled route %s is not updated: %s", src.name, e)
        return None
    log.info("bundled route %s updated in routes/", route_id)
    return doc["name"]


def route_thumb(
    dirs: DataDirs,
    route_id: str,
    doc: dict[str, Any],
    maps_by_id: dict[str, Any],
    cache: ThumbCache,
) -> str:
    """Route tile picture: the part of the map the route crosses, with the route drawn on it.

    A tile used to show the whole map, shrunk to the tile and mostly cut off: every route on a
    map had the same picture, and none of them showed its route.
    """
    path = route_path(dirs, route_id)
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        key = (str(path), 0)

    def build() -> str:
        meta = maps_by_id.get(doc["map"])
        base = map_backdrop(map_dir(dirs, doc["map"]), cache) if meta else None
        if base is None:
            return ""
        mw, mh = meta["size"]  # pyright: ignore[reportOptionalSubscript] -- base implies meta
        if mw <= 0 or mh <= 0:
            return ""
        ih, iw = base.shape[:2]
        markers = doc["markers"]
        if markers:
            pts = np.array([[m["x"] * iw / mw, m["y"] * ih / mh] for m in markers], float)
        else:
            pts = np.array([[iw / 2, ih / 2]], float)
        left, top, scale = thumb_frame(pts, (iw, ih))
        img = _crop(base, left, top, scale, THUMB_SIZE)
        if markers:
            _draw_route(img, (pts - (left, top)) * scale, doc)
        return data_url(img, quality=80)

    return cache.route_url(key, build)


_SUBPIXEL = 4  # fractional bits OpenCV draws with, so a point is not snapped to a pixel


def _dot_radius(pts: np.ndarray) -> float:
    """A point's radius on the picture, in pixels: smaller the closer the points lie, so that a
    long route drawn small is still a line with dots on it and not a heap of dots."""
    if len(pts) < 2:
        return 4.0
    steps = np.hypot(*np.diff(pts, axis=0).T)
    return float(np.clip(np.median(steps) * 0.3, 1.75, 4.0))


def _draw_route(img: np.ndarray, pts: np.ndarray, doc: dict[str, Any]) -> None:
    """The line in a dark casing, as the overlay draws it, and a dot at each point; the first
    one larger, where the route starts."""
    at = np.round(pts * (1 << _SUBPIXEL)).astype(np.int32)
    color = doc["style"]["color"]
    casing = (16, 14, 12)
    if len(at) > 1:
        cv2.polylines(img, [at], False, casing, 4, cv2.LINE_AA, _SUBPIXEL)
        cv2.polylines(img, [at], False, _bgr(color), 2, cv2.LINE_AA, _SUBPIXEL)
    r = _dot_radius(pts)
    for i, (p, m) in enumerate(zip(at, doc["markers"], strict=False)):
        size = r * 1.5 if i == 0 else r
        centre = (int(p[0]), int(p[1]))
        fill = _bgr(m.get("color") or color)
        ring = round((size + 1.25) * (1 << _SUBPIXEL))
        cv2.circle(img, centre, ring, casing, -1, cv2.LINE_AA, _SUBPIXEL)
        cv2.circle(img, centre, round(size * (1 << _SUBPIXEL)), fill, -1, cv2.LINE_AA, _SUBPIXEL)


class SkippedRoutes:
    """The files list_routes had to leave out, each reported once per version of the file.

    list_routes runs on every state rebuild -- start, stop, each engine phase, every setting --
    so a file it cannot use would otherwise be logged, and put in front of the user, each time.
    A version is the file's modification time: a file fixed or replaced by hand is judged
    afresh, and reported again if it is still no good.
    """

    def __init__(self) -> None:
        self._reported: set[tuple[Path, int]] = set()
        self._new: list[RouteError] = []

    def report(self, path: Path, mtime_ns: int, notice: RouteError, detail: object) -> None:
        if (path, mtime_ns) in self._reported:
            return
        self._reported.add((path, mtime_ns))
        log.warning("routes/%s is left out of the list: %s", path.name, detail)
        self._new.append(notice)

    def take(self) -> list[RouteError]:
        """The notices found since the last call, for the caller to show once."""
        new, self._new = self._new, []
        return new


def _mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _read_listed(path: Path, skipped: SkippedRoutes) -> dict[str, Any] | None:
    """The route in path, or None once skipped has been told why it is left out."""
    mtime = _mtime_ns(path)
    unusable = RouteError("route.file_skipped", file=path.name)
    notice: RouteError
    detail: object
    try:
        raw = _decode(_read_capped(path))
    except FileNotFoundError:
        return None  # deleted between the listing and the read
    except RouteError as e:
        # Too large to read. It stays where it is, as a route this version cannot use does:
        # nothing but its size is known to be wrong with it.
        notice = RouteError("route.file_skipped_too_large", file=path.name, limit=MAX_ROUTE_FILE_MB)
        detail = e
    except OSError as e:
        notice, detail = unusable, e
    except ValueError as e:
        try:
            backup = backup_corrupt(path)
        except OSError as move_error:
            notice, detail = unusable, f"{e}; not moved aside: {move_error}"
        else:
            notice = RouteError("route.file_corrupt", file=path.name, backup=backup.name)
            detail = e
    else:
        try:
            return _validated(raw)
        except AppError as e:
            notice, detail = unusable, e
    skipped.report(path, mtime, notice, detail)
    return None


def list_routes(
    dirs: DataDirs,
    maps_by_id: dict[str, Any],
    cache: ThumbCache,
    skipped: SkippedRoutes,
    order: Sequence[str] = (),
    *,
    starters: Mapping[str, Collection[str]] | None = None,
) -> list[dict[str, Any]]:
    """Every route, in `order`. A file that is not one is left out, so that it cannot hide the rest.

    A route `order` does not name comes after those it does, by file name. One whose bytes are
    a version of the starter route on its id (`starters`, from starter_digests) is official.

    A file that is not even JSON is moved aside, as a damaged settings.json is: it is no use
    where it is, and the copy keeps it recoverable. One that is JSON but not a route this
    version accepts -- a newer format, a hand edit gone wrong -- stays where it is, because it
    is not damaged, and a fix or a newer build can still use it. So does one larger than
    MAX_ROUTE_FILE_BYTES, which is never opened.
    """
    out = []
    if not dirs.routes.exists():
        return out
    for path in sorted(dirs.routes.glob("*.json"), key=lambda p: p.name.lower()):
        route_id = path.stem
        doc = _read_listed(path, skipped)
        if doc is None:
            continue
        meta = maps_by_id.get(doc["map"])
        out.append(
            {
                "id": route_id,
                "label": doc["name"],
                "map": doc["map"],
                "mapLabel": meta["label"] if meta else "",
                "markers": len(doc["markers"]),
                "steps": sum(1 for m in doc["markers"] if m["text"].strip()),
                "thumb": route_thumb(dirs, route_id, doc, maps_by_id, cache),
                "faction": meta.get("faction") if meta else None,
                "official": _is_official(path, starters or {}),
            }
        )
    return in_order(out, order)


def in_order[T: Mapping[str, Any]](listed: list[T], order: Sequence[str]) -> list[T]:
    """`listed` with the ids `order` names first, in its order; the rest after, as they were."""
    rank = {route_id: i for i, route_id in enumerate(order)}
    return sorted(listed, key=lambda r: rank.get(r["id"], len(rank)))
