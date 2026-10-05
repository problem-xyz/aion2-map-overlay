"""What the timers' pages are sent: getState()["timers"], built from the data, the settings and a
clock. No Qt.

Every moment is UTC milliseconds since the epoch, which is what a page's Date takes, so the page
only has to count down to them and format them in the player's own time. The occurrences cover
WINDOW_BEFORE to WINDOW_AFTER around now: what the list's next times, the day strip and the
timeline window draw from, without asking again.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from map_overlay.core.settings import Settings, timer_defaults
from map_overlay.store.timers import Region, Schedule, TimedEvent, WorldBoss
from map_overlay.timers.data import TimersData
from map_overlay.timers.schedule import (
    boss_spawns,
    boss_state,
    bosses_with_wrong_cycle,
    event_state,
    occurrences,
)

WINDOW_BEFORE = timedelta(hours=2)
WINDOW_AFTER = timedelta(hours=48)

# The server region a clock's offset from UTC most likely plays on, when the user has not said.
# Whole hours, summer time included: Europe runs at -1 to +3, Brazil at -3, the east and middle
# of North America at -4 to -6, its west at -7 and beyond.
_REGION_BY_OFFSET = (
    (range(-1, 4), "global-eu"),
    (range(-3, -1), "global-sa"),
    (range(-6, -3), "global-nae"),
    (range(-12, -6), "global-naw"),
    (range(4, 15), "global-as"),
)


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def guess_region(schedule: Schedule, utc_offset: timedelta) -> Region:
    """The region a player whose clock is utc_offset from UTC most likely plays on."""
    hours = round(utc_offset.total_seconds() / 3600)
    for span, region_id in _REGION_BY_OFFSET:
        region = schedule.region(region_id)
        if hours in span and region is not None:
            return region
    return schedule.regions[0]


def resolve_region(schedule: Schedule, setting: str, utc_offset: timedelta) -> tuple[Region, bool]:
    """The region in use, and whether it was guessed rather than chosen."""
    chosen = schedule.region(setting) if setting else None
    if chosen is not None:
        return chosen, False
    return guess_region(schedule, utc_offset), True


def server_groups(schedule: Schedule, region: Region) -> list[str]:
    """The server groups the region's rules name, in their first order; none for most."""
    seen: dict[str, None] = {}
    for event in schedule.events:
        rule = event.rule_for(region)
        if rule is not None:
            seen.update(dict.fromkeys(rule.groups))
    return list(seen)


def choice(settings: Settings, event: TimedEvent) -> dict[str, Any]:
    """The event's choices: the user's over the defaults for its kind."""
    return {**timer_defaults(event.kind), **settings.timers_events.get(event.id, {})}


def _event(
    event: TimedEvent, region: Region, now: datetime, group: str | None, settings: Settings
) -> dict[str, Any] | None:
    if event.rule_for(region) is None:
        return None
    state = event_state(event, region, now, group)
    window = occurrences(event, region, now - WINDOW_BEFORE, now + WINDOW_AFTER, group)
    rule = event.rule_for(region)
    # A weekly event comes round once or twice in the window: its days are read off a week
    week = (
        [ms(o.start) for o in occurrences(event, region, now, now + timedelta(days=7), group)]
        if rule is not None and rule.type == "weekly"
        else []
    )
    return {
        "id": event.id,
        "name": event.name,
        "kind": event.kind,
        "realm": event.realm,
        "icon": event.icon,
        "durationMin": event.duration_min,
        "entryMin": event.entry_min,
        **choice(settings, event),
        "live": {"start": ms(state.live.start), "end": ms(state.live.end)} if state.live else None,
        "entryCloses": ms(state.entry_closes) if state.entry_closes else None,
        "next": (
            {"start": ms(state.next.start), "end": ms(state.next.end), "group": state.next.group}
            if state.next
            else None
        ),
        "occurrences": [[ms(o.start), ms(o.end)] for o in window],
        "weekStarts": week,
    }


def _boss(boss: WorldBoss, now: datetime, shown: set[str]) -> dict[str, Any]:
    state = boss_state(boss, now)
    return {
        "id": boss.id,
        "name": boss.name,
        "area": boss.area,
        "level": boss.level,
        "respawnS": boss.respawn_s,
        "shown": boss.id in shown,
        "spawn": ms(state.spawn),
        "up": state.up,
        "estimated": state.estimated,
        "spawns": [ms(s) for s in boss_spawns(boss, now - WINDOW_BEFORE, now + WINDOW_AFTER)],
    }


def timers_view(
    data: TimersData,
    settings: Settings,
    now: datetime,
    utc_offset: timedelta,
    *,
    fetching: bool = False,
) -> dict[str, Any] | None:
    """getState()["timers"]; None when no schedule could be loaded at all."""
    schedule = data.schedule
    if schedule is None:
        return None
    now = now.astimezone(UTC)
    region, guessed = resolve_region(schedule, settings.timers_region, utc_offset)
    groups = server_groups(schedule, region)
    group = settings.timers_server_group if settings.timers_server_group in groups else None
    events = [_event(e, region, now, group, settings) for e in schedule.events]
    bosses = data.bosses
    # The world bosses are read on one server region; on another their times mean nothing.
    bosses_here = bosses is not None and bosses.region == region.id
    shown = set(settings.timers_world_shown)
    return {
        "now": ms(now),
        "region": region.id,
        "regionGuessed": guessed,
        "regions": [{"id": r.id, "label": r.label, "group": r.group} for r in schedule.regions],
        "serverGroups": groups,
        "serverGroup": group,
        "updatedAt": schedule.updated_at,
        "fetching": fetching,
        "events": [e for e in events if e is not None],
        "bosses": [_boss(b, now, shown) for b in bosses.bosses] if bosses and bosses_here else [],
        "bossesReadAt": ms(bosses.read_at) if bosses and bosses_here else None,
        "bossesMap": bosses.map if bosses and bosses_here else None,
        "wrongCycle": bosses_with_wrong_cycle(bosses) if bosses and bosses_here else [],
    }
