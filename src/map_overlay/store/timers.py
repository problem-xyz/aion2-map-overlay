"""The timers' data: the event schedule and the world bosses, read and checked, no Qt.

Both ship under assets/timers/ and a newer copy may be fetched later, so everything here takes a
parsed document from anywhere and either returns frozen values or raises TimersError: a bad
file is never half-used. Unknown fields are ignored, so a file can grow without breaking an
older app; an unknown version is refused, because its fields may mean something else.

Times in a rule are wall-clock times in a time zone: the rule's own, or else its region's. A
rule is looked up by the region's id first and then by its group, so "global" covers every
Global region and one region can still differ.
"""

import functools
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from map_overlay.core.errors import AppError
from map_overlay.core.fileio import read_json_or_none
from map_overlay.core.paths import resource_path

log = logging.getLogger(__name__)

SCHEDULE_FORMAT = "map-overlay-timers"
BOSSES_FORMAT = "map-overlay-world-bosses"
VERSION = 1

Kind = Literal["event", "boss", "reset"]
Realm = Literal["abyss", "world"]
RuleType = Literal["hourly", "daily", "weekly", "once"]

KINDS: tuple[Kind, ...] = ("event", "boss", "reset")
REALMS: tuple[Realm, ...] = ("abyss", "world")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # index = datetime.weekday()

_CLOCK = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")
# The game writes "1h 2min 26s"; the files also use "1h 30m". "min" is tried before "m".
_DURATION_PART = re.compile(r"(\d+)\s*(h|min|m|s)")
_UNIT_SECONDS = {"h": 3600, "min": 60, "m": 60, "s": 1}


class TimersError(AppError):
    """A timers file the app will not use, under timers.*; field names what was wrong."""


@dataclass(frozen=True)
class Region:
    id: str
    group: str
    label: str
    time_zone: str


@dataclass(frozen=True)
class Rule:
    """When an event happens. times are (hour, minute); days are weekday() numbers."""

    type: RuleType
    times: tuple[tuple[int, int], ...] = ()
    minute: int = 0
    days: tuple[int, ...] = ()
    at: datetime | None = None
    time_zone: str | None = None
    groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimedEvent:
    id: str
    name: str
    kind: Kind
    realm: Realm | None
    icon: str
    duration_min: int
    entry_min: int
    rules: tuple[tuple[str, Rule], ...]

    def rule_for(self, region: Region) -> Rule | None:
        """The region's own rule, or its group's, or None where the event does not run."""
        rules = dict(self.rules)
        return rules.get(region.id) or rules.get(region.group)


@dataclass(frozen=True)
class Schedule:
    updated_at: str
    regions: tuple[Region, ...]
    events: tuple[TimedEvent, ...]

    def region(self, region_id: str) -> Region | None:
        return next((r for r in self.regions if r.id == region_id), None)


@dataclass(frozen=True)
class WorldBoss:
    id: str
    name: str
    area: str
    level: int
    respawn_s: int
    spawns_at: datetime  # UTC


@dataclass(frozen=True)
class WorldBosses:
    read_at: datetime  # UTC
    region: str
    map: str
    faction: str
    bosses: tuple[WorldBoss, ...]


def parse_duration(text: Any, field: str) -> int:
    """Seconds in "1h 2min 26s", "30m", "13s"; anything else in the string is an error."""
    s = str(text).strip().lower() if isinstance(text, str) else ""
    parts = _DURATION_PART.findall(s)
    if not parts or _DURATION_PART.sub("", s).strip():
        raise TimersError("timers.invalid", field=field)
    return sum(int(n) * _UNIT_SECONDS[unit] for n, unit in parts)


def parse_schedule(doc: Any) -> Schedule:
    """A schedule document, checked through; raises TimersError on the first problem."""
    _check_header(doc, SCHEDULE_FORMAT)
    regions = tuple(_region(r, i) for i, r in enumerate(_list(doc, "regions")))
    if not regions:
        raise TimersError("timers.invalid", field="regions")
    _unique([r.id for r in regions], "regions")
    events = tuple(_event(e, i) for i, e in enumerate(_list(doc, "events")))
    if not events:
        raise TimersError("timers.invalid", field="events")
    _unique([e.id for e in events], "events")
    return Schedule(updated_at=_str(doc, "updatedAt", "updatedAt"), regions=regions, events=events)


def parse_world_bosses(doc: Any) -> WorldBosses:
    """A world-bosses document; each boss's timeLeft (or spawnsAt) becomes a UTC moment."""
    _check_header(doc, BOSSES_FORMAT)
    read_at = _instant(doc.get("readAt"), "readAt")
    bosses = []
    for i, b in enumerate(_list(doc, "bosses")):
        where = f"bosses[{i}]"
        if not isinstance(b, dict):
            raise TimersError("timers.invalid", field=where)
        if b.get("spawnsAt") is not None:
            spawns_at = _instant(b["spawnsAt"], f"{where}.spawnsAt")
        else:
            left = parse_duration(b.get("timeLeft"), f"{where}.timeLeft")
            spawns_at = read_at + timedelta(seconds=left)
        level = b.get("level", 0)
        if not isinstance(level, int) or isinstance(level, bool) or level < 0:
            raise TimersError("timers.invalid", field=f"{where}.level")
        bosses.append(
            WorldBoss(
                id=_str(b, "id", f"{where}.id"),
                name=_str(b, "name", f"{where}.name"),
                area=str(b.get("area") or ""),
                level=level,
                respawn_s=parse_duration(b.get("respawn"), f"{where}.respawn"),
                spawns_at=spawns_at,
            )
        )
    _unique([b.id for b in bosses], "bosses")
    return WorldBosses(
        read_at=read_at,
        region=_str(doc, "region", "region"),
        map=str(doc.get("map") or ""),
        faction=str(doc.get("faction") or ""),
        bosses=tuple(bosses),
    )


@functools.cache
def bundled_schedule() -> Schedule | None:
    """The schedule that ships with the app; None (and a log line) if it does not load."""
    return _load_bundled("assets/timers/schedule.json", parse_schedule)


@functools.cache
def bundled_world_bosses() -> WorldBosses | None:
    """The world bosses that ship with the app; None (and a log line) if they do not load."""
    return _load_bundled("assets/timers/world-bosses.json", parse_world_bosses)


def _load_bundled[T](rel: str, parse: Callable[[Any], T]) -> T | None:
    path = resource_path(rel)
    try:
        return parse(read_json_or_none(path))
    except TimersError as e:
        log.warning("bundled timers file %s is not usable: %s", path, e)
        return None


def _check_header(doc: Any, fmt: str) -> None:
    if not isinstance(doc, dict) or doc.get("format") != fmt:
        raise TimersError("timers.invalid", field="format")
    if doc.get("version") != VERSION:
        raise TimersError("timers.version", version=str(doc.get("version")))


def _region(r: Any, i: int) -> Region:
    where = f"regions[{i}]"
    if not isinstance(r, dict):
        raise TimersError("timers.invalid", field=where)
    return Region(
        id=_str(r, "id", f"{where}.id"),
        group=_str(r, "group", f"{where}.group"),
        label=_str(r, "label", f"{where}.label"),
        time_zone=_zone(r.get("timeZone"), f"{where}.timeZone"),
    )


def _event(e: Any, i: int) -> TimedEvent:
    where = f"events[{i}]"
    if not isinstance(e, dict):
        raise TimersError("timers.invalid", field=where)
    kind = e.get("kind")
    if kind not in KINDS:
        raise TimersError("timers.invalid", field=f"{where}.kind")
    realm = e.get("realm")
    if realm is not None and realm not in REALMS:
        raise TimersError("timers.invalid", field=f"{where}.realm")
    schedules = e.get("schedules")
    if not isinstance(schedules, dict) or not schedules:
        raise TimersError("timers.invalid", field=f"{where}.schedules")
    rules = tuple(
        (str(key), _rule(rule, f"{where}.schedules.{key}")) for key, rule in schedules.items()
    )
    return TimedEvent(
        id=_str(e, "id", f"{where}.id"),
        name=_str(e, "name", f"{where}.name"),
        kind=kind,
        realm=realm,
        icon=_str(e, "icon", f"{where}.icon"),
        duration_min=_minutes(e.get("durationMinutes", 0), f"{where}.durationMinutes"),
        entry_min=_minutes(e.get("entryMinutes", 0), f"{where}.entryMinutes"),
        rules=rules,
    )


def _rule(r: Any, where: str) -> Rule:
    if not isinstance(r, dict):
        raise TimersError("timers.invalid", field=where)
    zone = _zone(r["timeZone"], f"{where}.timeZone") if r.get("timeZone") is not None else None
    kind = r.get("type")
    if kind == "hourly":
        minute = r.get("minute", 0)
        if not isinstance(minute, int) or isinstance(minute, bool) or not 0 <= minute <= 59:
            raise TimersError("timers.invalid", field=f"{where}.minute")
        return Rule(type="hourly", minute=minute, time_zone=zone)
    if kind == "once":
        return Rule(type="once", at=_instant(r.get("at"), f"{where}.at"), time_zone=zone)
    if kind not in ("daily", "weekly"):
        raise TimersError("timers.invalid", field=f"{where}.type")
    times = tuple(_clock(t, f"{where}.times") for t in _list(r, "times", where))
    if not times:
        raise TimersError("timers.invalid", field=f"{where}.times")
    groups = tuple(str(g) for g in r.get("groups") or ())
    if groups and len(groups) != len(times):
        raise TimersError("timers.invalid", field=f"{where}.groups")
    days: tuple[int, ...] = ()
    if kind == "weekly":
        names = _list(r, "days", where)
        if not names or any(d not in DAYS for d in names):
            raise TimersError("timers.invalid", field=f"{where}.days")
        days = tuple(sorted({DAYS.index(d) for d in names}))
    return Rule(type=kind, times=times, days=days, time_zone=zone, groups=groups)


def _clock(value: Any, field: str) -> tuple[int, int]:
    m = _CLOCK.fullmatch(value) if isinstance(value, str) else None
    if not m:
        raise TimersError("timers.invalid", field=field)
    return int(m[1]), int(m[2])


def _zone(name: Any, field: str) -> str:
    if not isinstance(name, str) or not name:
        raise TimersError("timers.invalid", field=field)
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise TimersError("timers.invalid", field=field) from e
    return name


def _instant(value: Any, field: str) -> datetime:
    """An ISO moment with its offset ("Z" or "+02:00"), as UTC."""
    try:
        moment = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        moment = None
    if moment is None or moment.tzinfo is None:
        raise TimersError("timers.invalid", field=field)
    return moment.astimezone(UTC)


def _minutes(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TimersError("timers.invalid", field=field)
    return value


def _str(d: dict[str, Any], key: str, field: str) -> str:
    value = d.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TimersError("timers.invalid", field=field)
    return value


def _list(d: Any, key: str, where: str = "") -> list[Any]:
    value = d.get(key) if isinstance(d, dict) else None
    if not isinstance(value, list):
        raise TimersError("timers.invalid", field=f"{where}.{key}" if where else key)
    return value


def _unique(ids: list[str], field: str) -> None:
    if len(ids) != len(set(ids)):
        raise TimersError("timers.invalid", field=field)
