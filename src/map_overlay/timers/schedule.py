"""When things happen: the timers' rules and boss readings turned into moments, no Qt.

Everything here takes `now` and returns UTC datetimes, so the answers can be tested against
fixed clocks and the page only has to count down to them. A rule's times are wall-clock times on
its own zone or else its region's, so a UTC event and a region's reset move apart by an hour
when the region changes to or from summer time, and that is what the game does too.

World bosses have no schedule. Each reading gives one spawn; a boss lives a minute or two, so
the next spawn is that one plus KILL plus its respawn cycle, and so on. Those later spawns are
marked estimated: the next reading of the game's list puts them right again.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from map_overlay.store.timers import Region, Rule, TimedEvent, WorldBoss, WorldBosses

# A world boss is killed this long after it spawns, and counts as up for UP after spawning.
KILL = timedelta(seconds=90)
UP = timedelta(minutes=3)


@dataclass(frozen=True)
class Occurrence:
    start: datetime  # UTC
    end: datetime  # UTC; equal to start for an event with no duration
    group: str | None = None  # the server group, where the rule names them


@dataclass(frozen=True)
class EventState:
    """An event at one moment: what is running, whether entry is open, and what comes next."""

    live: Occurrence | None
    entry_closes: datetime | None  # while entry is still open, when it closes
    next: Occurrence | None


@dataclass(frozen=True)
class BossState:
    spawn: datetime  # the current spawn while up, else the next one (UTC)
    up: bool
    estimated: bool  # past the reading: spawn + KILL + respawn, cycle after cycle


def occurrences(
    event: TimedEvent,
    region: Region,
    start: datetime,
    end: datetime,
    server_group: str | None = None,
) -> list[Occurrence]:
    """Every occurrence that overlaps [start, end), in time order.

    An event without a duration overlaps when it starts inside the window. server_group keeps
    only that group's times where a rule names groups; without it every group's time is kept.
    """
    rule = event.rule_for(region)
    if rule is None:
        return []
    span = timedelta(minutes=event.duration_min)
    out = []
    for begin, group in _starts(rule, region, start - span - timedelta(days=1), end):
        if server_group is not None and group is not None and group != server_group:
            continue
        finish = begin + span
        if begin < end and (finish > start if span else begin >= start):
            out.append(Occurrence(begin, finish, group))
    out.sort(key=lambda o: o.start)
    return out


def event_state(
    event: TimedEvent, region: Region, now: datetime, server_group: str | None = None
) -> EventState:
    """What the event is doing at now; next is None only for a once-event that has passed."""
    window = occurrences(event, region, now, now + timedelta(days=8), server_group)
    live = next((o for o in window if o.start <= now < o.end), None)
    upcoming = next((o for o in window if o.start > now), None)
    entry_closes = None
    if live and event.entry_min:
        closes = live.start + timedelta(minutes=event.entry_min)
        entry_closes = closes if now < closes else None
    return EventState(live=live, entry_closes=entry_closes, next=upcoming)


def boss_state(boss: WorldBoss, now: datetime) -> BossState:
    """Where the boss is at now: up since its spawn, or the spawn to wait for."""
    spawn = boss.spawns_at
    estimated = False
    if boss.respawn_s > 0:
        cycle = KILL + timedelta(seconds=boss.respawn_s)
        if spawn + UP <= now:
            # whole cycles past the reading, without stepping through each one
            skipped = (now - UP - spawn) // cycle + 1
            spawn += cycle * skipped
            estimated = True
    return BossState(spawn=spawn, up=spawn <= now < spawn + UP, estimated=estimated)


def boss_spawns(boss: WorldBoss, start: datetime, end: datetime) -> list[datetime]:
    """Every spawn in [start, end), the read one and the estimated ones after it."""
    out = []
    spawn = boss.spawns_at
    cycle = KILL + timedelta(seconds=boss.respawn_s) if boss.respawn_s > 0 else None
    if cycle is not None and spawn + UP <= start:
        spawn += cycle * ((start - UP - spawn) // cycle + 1)
    while spawn < end:
        if spawn + UP > start:
            out.append(spawn)
        if cycle is None:
            break
        spawn += cycle
    return out


def bosses_with_wrong_cycle(reading: WorldBosses) -> list[str]:
    """Bosses whose time left in the reading is longer than their cycle: the cycle is wrong."""
    return [
        b.id
        for b in reading.bosses
        if b.respawn_s > 0 and (b.spawns_at - reading.read_at).total_seconds() > b.respawn_s
    ]


def _starts(
    rule: Rule, region: Region, start: datetime, end: datetime
) -> Iterator[tuple[datetime, str | None]]:
    """Rule start moments from about start until end, in UTC; the caller trims the edges."""
    if rule.type == "once":
        if rule.at is not None:
            yield rule.at, None
        return
    zone = ZoneInfo(rule.time_zone or region.time_zone)
    first = start.astimezone(zone).date() - timedelta(days=1)
    last = end.astimezone(zone).date() + timedelta(days=1)
    day = first
    while day <= last:
        yield from _starts_on(rule, zone, day)
        day += timedelta(days=1)


def _starts_on(rule: Rule, zone: ZoneInfo, day: date) -> Iterator[tuple[datetime, str | None]]:
    if rule.type == "hourly":
        for hour in range(24):
            yield _utc(day, hour, rule.minute, zone), None
        return
    if rule.type == "weekly" and day.weekday() not in rule.days:
        return
    for i, (hour, minute) in enumerate(rule.times):
        group = rule.groups[i] if rule.groups else None
        yield _utc(day, hour, minute, zone), group


def _utc(day: date, hour: int, minute: int, zone: ZoneInfo) -> datetime:
    """A wall-clock time on day in zone, as UTC. A time skipped by a clock change lands an
    hour later, as the game's server would run it; a repeated one takes the first."""
    return datetime.combine(day, time(hour, minute), tzinfo=zone).astimezone(UTC)
