"""The settings and state schema, and the one function that turns untrusted JSON into it.

Two files, not one. Settings are what the user chose and are worth keeping across machines;
state is where the windows were and which route was open, which is per-machine and disposable.
Mixing them meant a 15 Hz progress tick rewrote the whole preferences file.

Nothing here trusts the file on disk. It may have been hand-edited, written by an older
version, or half-written by a previous crash, so every value is checked against the field's
declared type and range: a number outside its range is pulled to the nearest end of it, and
anything else that does not fit is replaced by the default. A bad file must cost the user a
toast, never a start-up crash.
"""

import itertools
import logging
import math
from collections.abc import Callable
from dataclasses import MISSING, asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, TypeGuard

from map_overlay.core.fileio import backup_corrupt, read_json_or_none

log = logging.getLogger(__name__)

SETTINGS_VERSION = 1
STATE_VERSION = 1

# The plaque's size as the slider shows it (steps_scale) and the factor it is drawn at, from
# the smallest to the largest. The owner set the three: the old full size is the least there is
# now, 135% of it the default, 160% the most. Between two of them the size runs in a line.
PLAQUE_SCALE = ((0.5, 1.0), (1.0, 1.35), (1.5, 1.6))

# The plaque's three old sizes on that slider: what setStepsSize still sets, and what a file
# written before steps_scale existed carries over. S and M were both at or under the old full
# size, so both land on the least there is now; L was 1.25 of it.
STEPS_SIZE_SCALE = {"s": 0.5, "m": 0.5, "l": 0.86}


def plaque_scale(setting: float) -> float:
    """The factor the plaque is drawn at -- type and width alike -- for steps_scale."""
    lo, lo_at = PLAQUE_SCALE[0]
    if setting <= lo:
        return lo_at
    for (a, a_at), (b, b_at) in itertools.pairwise(PLAQUE_SCALE):
        if setting <= b:
            return round(a_at + (setting - a) / (b - a) * (b_at - a_at), 3)
    return PLAQUE_SCALE[-1][1]


def rng(lo: float, hi: float) -> dict[str, Any]:
    return {"range": (lo, hi)}


def choices(*xs: str) -> dict[str, Any]:
    return {"choices": xs}


class Region(TypedDict):
    """A screen rectangle in physical pixels. Crosses to JavaScript as-is."""

    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class Settings:
    """What the user chose, persisted to settings.json and worth carrying between machines.

    Each field declares its default and, in metadata, the range or choice list that coerce()
    enforces on the file at load and on every updateSettings patch. Adding a field means adding
    both; changing what an existing one means requires a migration keyed by SETTINGS_VERSION.

    The ranges are also what the panel's sliders offer: settings_schema() hands them to the UI
    in getState(), so a range is written here and nowhere else.
    """

    opacity: float = field(default=0.85, metadata=rng(0.1, 1.0))
    fps: int = field(default=60, metadata=rng(30, 240))
    detector: str = field(default="sift", metadata=choices("sift", "orb"))
    detect_scale: float = field(default=1.0, metadata=rng(0.25, 1.0))
    min_inliers: int = field(default=20, metadata=rng(8, 60))
    transform: str = field(default="similarity", metadata=choices("similarity", "homography"))
    tracking: str = field(default="flow", metadata=choices("flow", "detect"))
    smoothing: float = field(default=0.5, metadata=rng(0.0, 0.9))
    detect_interval: float = field(default=0.4, metadata=rng(0.1, 2.0))
    flow_points: int = field(default=200, metadata=rng(40, 2000))
    hold_frames: int = field(default=8, metadata=rng(0, 100))
    # How much of the route the overlay draws. "steps": the next route_ahead steps in full and
    # the last route_past passed faded, nothing further; "dim": the whole route, faded past the
    # next steps; "all": the whole route ahead in full, what was passed faded. The steps plaque
    # lists the last route_past passed too, whatever the view.
    route_view: str = field(default="steps", metadata=choices("steps", "dim", "all"))
    route_ahead: int = field(default=3, metadata=rng(1, 10))
    route_past: int = field(default=3, metadata=rng(0, 10))
    # The map's hidden cubes over the game, all of them and whatever the route's progress, each
    # in a ring cube_radius screen pixels across its middle; 0 draws the cube alone.
    show_cubes: bool = False
    # The route's points on Empyrean Traces, the feathers. Off leaves them out of the overlay, the
    # checklist and the count, as if the route had none; the progress kept is the whole route's.
    route_traces: bool = True
    cube_radius: int = field(default=20, metadata=rng(0, 100))
    # The same in the route editor, which always draws every point: "dim" fades the route away
    # from the selected point and the steps after it, "all" draws it all in full.
    editor_route_view: str = field(default="dim", metadata=choices("dim", "all"))
    editor_route_ahead: int = field(default=3, metadata=rng(1, 10))
    editor_opacity: float = field(default=1.0, metadata=rng(0.1, 1.0))
    # Kept for the settings file and getState's settings, and read by nothing: progress always
    # counts since api 16, where it used to be a switch.
    progress_enabled: bool = True
    auto_progress: bool = True
    player_anchor_x: float = field(default=0.5, metadata=rng(0.0, 1.0))
    player_anchor_y: float = field(default=0.5, metadata=rng(0.0, 1.0))
    # A fraction of the map's width. Both maps are 4096 wide, so the range is 8 to 32 map pixels
    # and the default 8; it went up to 123 once, and nobody set it past 32.
    arrive_radius: float = field(default=8 / 4096, metadata=rng(8 / 4096, 32 / 4096))
    ratio: float = field(default=0.75, metadata=rng(0.5, 0.95))
    reproj_thr: float = field(default=4.0, metadata=rng(0.5, 20.0))
    ref_features: int = field(default=100000, metadata=rng(0, 1_000_000))
    frame_features: int = field(default=2500, metadata=rng(200, 20000))
    capture_visible: bool = False
    steps_pinned: bool = True
    steps_size: str = field(default="m", metadata=choices("s", "m", "l"))
    # The plaque's size on a slider, 50% to 150%: plaque_scale says what each draws at. It took
    # over from the three steps of steps_size, which setStepsSize still sets for a caller that
    # knows only those.
    steps_scale: float = field(default=1.0, metadata=rng(0.5, 1.5))
    language: str = field(default="auto", metadata=choices("auto", "en", "ru"))
    updates_auto_check: bool = True
    updates_auto_download: bool = True
    updates_skipped_version: str = ""


@dataclass(frozen=True)
class State:
    """Where this machine left off, persisted to state.json and disposable.

    Screen regions, the open route and its progress, and the one-time hints already given. It
    is a separate file from Settings because it is rewritten as the player moves, and a
    progress tick must not rewrite the user's preferences. Fields follow the same
    default-plus-metadata contract as Settings.
    """

    region: Region | None = None
    steps_region: Region | None = None
    # On for a new install: the checklist is the part of the overlay a new player looks for.
    # state.json keeps whatever was chosen, so a player who turned it off keeps it off.
    steps_visible: bool = True
    steps_hint_shown: bool = False
    route: str | None = None
    progress: dict[str, int] = field(default_factory=dict)
    # The routes in the order the panel lists them, as the user dragged them. A route it does
    # not name -- a file dropped into the folder by hand -- is listed after these.
    route_order: list[str] = field(default_factory=list)
    # The bundled routes already copied into routes/, so that one the user deleted stays deleted.
    seeded_routes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- schema export


class FieldSchema(TypedDict):
    """One Settings field as getState()["settingsSchema"] describes it to the UI.

    `type` is one of "bool", "int", "float", "str". `min`/`max` exist only for a ranged
    field and `choices` only for a field with a fixed list; both are the metadata coerce()
    enforces, copied rather than restated, so the panel cannot offer a value the file rejects.
    """

    type: str
    default: bool | int | float | str
    min: NotRequired[float]
    max: NotRequired[float]
    choices: NotRequired[list[str]]


def _type_name(value: object) -> str:
    # bool first: it is an int subclass, and a checkbox is not a number field.
    for cls, name in ((bool, "bool"), (int, "int"), (float, "float"), (str, "str")):
        if isinstance(value, cls):
            return name
    raise TypeError(f"no schema type for {value!r}")


def settings_schema() -> dict[str, FieldSchema]:
    """Every Settings field with its type, default and declared range or choices."""
    schema: dict[str, FieldSchema] = {}
    for f in fields(Settings):
        default = f.default
        if default is MISSING:
            raise TypeError(f"Settings.{f.name} needs a plain default to be described")
        entry = FieldSchema(type=_type_name(default), default=default)
        bounds = f.metadata.get("range")
        if bounds:
            entry["min"], entry["max"] = bounds
        allowed = f.metadata.get("choices")
        if allowed is not None:
            entry["choices"] = list(allowed)
        schema[f.name] = entry
    return schema


# --------------------------------------------------------------------------- coercion

# How a stored value was repaired: replaced by the field's default, or pulled onto the nearest
# end of the field's range. None when it was kept as it was.
type Repair = Literal["default", "clamped"] | None

# Far past any desktop there is, and small enough that left + width stays a 32-bit int, which
# is what Qt keeps a window rectangle in.
_MAX_COORD = 1 << 24


def _finite(raw: object) -> TypeGuard[int | float]:
    """A JSON number usable as one. json.loads also reads NaN, Infinity and -Infinity."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return False
    return not isinstance(raw, float) or math.isfinite(raw)


def _coerce_region(value: Any) -> Region | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, int] = {}
    for key in ("left", "top", "width", "height"):
        raw = value.get(key)
        if not _finite(raw) or not -_MAX_COORD <= raw <= _MAX_COORD:
            return None
        out[key] = int(raw)
    if out["width"] <= 0 or out["height"] <= 0:
        return None
    return Region(**out)


def _coerce_progress(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    return {str(k): max(0, int(v)) for k, v in value.items() if _finite(v)}


def _coerce_ids(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return list(dict.fromkeys(v for v in value if isinstance(v, str) and v))


# State fields with a shape of their own, each checked by its coercer, which returns None for a
# value it cannot use.
_STRUCTURED: dict[str, Callable[[Any], Any]] = {
    "region": _coerce_region,
    "steps_region": _coerce_region,
    "progress": _coerce_progress,
    "route_order": _coerce_ids,
    "seeded_routes": _coerce_ids,
}


def _coerce_number(raw: Any, default: int | float, meta: Any) -> tuple[Any, Repair]:
    # _finite turns away bool too: it is an int subclass, but a checkbox value is not a number
    # the user typed. NaN and the infinities are no number a slider can show either; int() of
    # them raises, and NaN would slip through the clamp, since it compares unequal to anything.
    if not _finite(raw):
        return default, "default"
    cast = int if isinstance(default, int) else float
    bounds = meta.get("range")
    try:
        value = cast(raw)
    except OverflowError:  # an integer with more digits than a float can hold: past any range
        if not bounds:
            return default, "default"
        return cast(bounds[1] if raw > 0 else bounds[0]), "clamped"
    if bounds:
        lo, hi = bounds
        clamped = cast(min(max(value, lo), hi))
        if clamped != value:
            return clamped, "clamped"
    return value, None


def _coerce_scalar(raw: Any, default: Any, meta: Any) -> tuple[Any, Repair]:
    """The value to keep, and how it was repaired. What cannot be honoured gets the default."""
    allowed = meta.get("choices")
    if allowed is not None:
        return (raw, None) if raw in allowed else (default, "default")
    if isinstance(default, bool):
        # bool before int: bool is an int subclass, and 1 from JSON is not a checkbox.
        return (raw, None) if isinstance(raw, bool) else (default, "default")
    if isinstance(default, str):
        return (raw, None) if isinstance(raw, str) else (default, "default")
    if isinstance(default, (int, float)):
        return _coerce_number(raw, default, meta)
    return default, "default"


def coerce(raw: Any, cls: type) -> tuple[Any, list[str]]:
    """Build a Settings or State from untrusted JSON.

    Returns the object and the names of the fields whose stored value could not be kept as it
    was -- replaced by the default or pulled into range -- so that the caller can tell the user
    once instead of once per field. The log says which of the two happened to each.
    """
    data = dict(raw) if isinstance(raw, dict) else {}
    data.pop("version", None)  # written by settings_payload/state_payload, not a field
    known = {f.name: f for f in fields(cls)}
    for key in [k for k in data if k not in known]:
        log.info("%s: dropping unknown key %r", cls.__name__, key)

    values: dict[str, Any] = {}
    reset: list[str] = []  # replaced by the default
    clamped: list[str] = []  # pulled onto the nearest end of the range
    for name, f in known.items():
        default = f.default_factory() if f.default_factory is not MISSING else f.default
        if name not in data:
            values[name] = default
            continue
        given = data[name]

        if name in _STRUCTURED:
            coerced = _STRUCTURED[name](given)
            # A region may be null; a null where the default is a value is a reset.
            if coerced is None and (given is not None or default is not None):
                reset.append(name)
            values[name] = default if coerced is None else coerced
        elif name == "route":
            values[name] = given if isinstance(given, str) and given else None
        else:
            value, repair = _coerce_scalar(given, default, f.metadata)
            values[name] = value
            if repair == "clamped":
                clamped.append(name)
                log.warning("%s: %s %r pulled into range: %r", cls.__name__, name, given, value)
            elif repair == "default":
                reset.append(name)

    if reset:
        log.warning("%s: reset to defaults: %s", cls.__name__, ", ".join(sorted(reset)))
    return cls(**values), sorted(reset + clamped)


# --------------------------------------------------------------------------- migrations


def migrate_0_to_1(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split the single pre-v1 settings.json into settings and state.

    The two value fixes below were applied on every load by the old code. They are one-time
    corrections for defaults that were wrong in shipped versions, so they belong in a
    migration, not in the loading path.
    """
    old = raw.get("settings")
    settings = dict(old) if isinstance(old, dict) else {}

    # Before 2.1 the cap was 4000 keypoints for the whole reference. On a large map almost
    # none landed in the part being looked at, and the map was never found.
    ref = settings.get("ref_features")
    if isinstance(ref, (int, float)) and 0 < ref < 20000:
        settings["ref_features"] = Settings.ref_features

    # Before 3.1 the overlay redrew no more often than detection, so a 15 fps cap hurt nobody.
    # With flow tracking it became the thing holding the overlay back.
    fps = settings.get("fps")
    if isinstance(fps, (int, float)) and fps < 30:
        settings["fps"] = Settings.fps

    for key in ("capture_visible", "steps_pinned", "steps_size"):
        if key in raw:
            settings[key] = raw[key]

    state = {
        "region": raw.get("region"),
        "steps_region": raw.get("steps_region"),
        "steps_visible": raw.get("steps_visible", False),
        "route": raw.get("route"),
        "progress": raw.get("progress", {}),
    }
    return settings, state


MIGRATIONS = {0: migrate_0_to_1}


# --------------------------------------------------------------------------- loading


@dataclass(frozen=True)
class LoadResult:
    """The two objects load() built, and every repair it had to make to build them.

    reset_keys names the settings and state fields whose stored value did not survive
    validation, gathered so the caller reports them once rather than once per field.
    corrupt_backup is the .broken-* copy of a settings.json that could not be parsed at all,
    kept aside before defaults replaced it, and None when the file was readable or absent.
    migrated says a pre-v1 single file was split. Any of the three means what is in memory no
    longer matches what is on disk, so the caller should write both files back.
    """

    settings: Settings
    state: State
    reset_keys: list[str]
    corrupt_backup: Path | None
    migrated: bool


def load(settings_path: Path, state_path: Path) -> LoadResult:
    """Read both files, migrating a pre-v1 single file if that is what is there.

    Never raises for bad content: an unreadable file is moved aside and defaults are used.
    """
    raw_settings = read_json_or_none(settings_path)
    corrupt: Path | None = None
    migrated = False

    if raw_settings is None and settings_path.exists():
        corrupt = backup_corrupt(settings_path)
        raw_settings = None

    raw_state: Any = read_json_or_none(state_path)

    if isinstance(raw_settings, dict):
        version = raw_settings.get("version")
        if not isinstance(version, int):
            version = 0
        if version < SETTINGS_VERSION:
            # A pre-v1 file carries state as well, and there is no state.json yet.
            for v in range(version, SETTINGS_VERSION):
                raw_settings, raw_state = MIGRATIONS[v](raw_settings)
            migrated = True

    settings, reset_settings = coerce(
        with_arrive_radius_in_range(with_steps_scale(raw_settings)), Settings
    )
    state, reset_state = coerce(raw_state, State)
    return LoadResult(
        settings=settings,
        state=state,
        reset_keys=sorted(reset_settings + reset_state),
        corrupt_backup=corrupt,
        migrated=migrated,
    )


def with_steps_scale(raw: Any) -> Any:
    """A file from before steps_scale keeps the plaque the size it had: S, M or L as a scale.

    Not a versioned migration: no field changes what it means, one is only added, and its
    default is the right answer for every file that did not choose otherwise.
    """
    if not isinstance(raw, dict) or "steps_scale" in raw:
        return raw
    scale = STEPS_SIZE_SCALE.get(raw.get("steps_size"))  # pyright: ignore[reportArgumentType]
    return {**raw, "steps_scale": scale} if scale is not None else raw


def with_arrive_radius_in_range(raw: Any) -> Any:
    """A radius from the wider range the setting once had comes down to the new top, unannounced.

    The range was narrowed, not the value spoiled: the old default, 0.008, is past the new top,
    and most files carry it. Left to coerce() it would count as a repair and every such user
    would be warned on start that a value had been reset. A value that is not a finite number
    is still coerce()'s to report.
    """
    if not isinstance(raw, dict):
        return raw
    value = raw.get("arrive_radius")
    top = next(f for f in fields(Settings) if f.name == "arrive_radius").metadata["range"][1]
    if isinstance(value, float) and math.isfinite(value) and value > top:
        return {**raw, "arrive_radius": top}
    return raw


def settings_payload(settings: Settings) -> dict[str, Any]:
    return {"version": SETTINGS_VERSION, **asdict(settings)}


def state_payload(state: State) -> dict[str, Any]:
    return {"version": STATE_VERSION, **asdict(state)}
