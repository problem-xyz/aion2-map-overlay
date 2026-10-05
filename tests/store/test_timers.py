"""The timers' files: what a valid one reads as, and that every broken field is refused whole."""

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from map_overlay.core.paths import resource_path
from map_overlay.store.timers import (
    TimersError,
    bundled_schedule,
    bundled_world_bosses,
    parse_duration,
    parse_schedule,
    parse_world_bosses,
)

SCHEDULE: dict[str, Any] = {
    "format": "map-overlay-timers",
    "version": 1,
    "updatedAt": "2026-10-02",
    "regions": [
        {"id": "global-eu", "group": "global", "label": "Europe", "timeZone": "Europe/Berlin"},
        {"id": "kr", "group": "kr", "label": "Korea", "timeZone": "Asia/Seoul"},
    ],
    "events": [
        {
            "id": "rift",
            "name": "Spacetime Rift",
            "kind": "event",
            "icon": "vortex",
            "durationMinutes": 60,
            "entryMinutes": 10,
            "schedules": {
                "global": {"type": "daily", "timeZone": "UTC", "times": ["00:00", "03:00"]},
                "kr": {"type": "daily", "times": ["02:00"]},
            },
        },
        {
            "id": "siege-bosses",
            "name": "Siege Bosses",
            "kind": "boss",
            "realm": "abyss",
            "icon": "demon",
            "schedules": {
                "global": {"type": "weekly", "days": ["sat", "mon"], "times": ["21:30"]},
                "kr": {
                    "type": "weekly",
                    "days": ["wed"],
                    "times": ["21:45", "22:15"],
                    "groups": ["1", "2"],
                },
            },
        },
        {
            "id": "shugo",
            "name": "Shugo Festival",
            "kind": "event",
            "icon": "fox",
            "schedules": {"global": {"type": "hourly", "minute": 0}},
        },
    ],
}

BOSSES: dict[str, Any] = {
    "format": "map-overlay-world-bosses",
    "version": 1,
    "readAt": "2026-10-05T13:18:00Z",
    "region": "global-eu",
    "bosses": [
        {"id": "aed", "name": "Black Warrior Aed", "respawn": "30m", "timeLeft": "13s"},
        {"id": "gartua", "name": "Immortal Gartua", "respawn": "12h", "timeLeft": "11h 16min 50s"},
        {
            "id": "lagta",
            "name": "High Commander Lagta",
            "respawn": "12h",
            "spawnsAt": "2026-10-06T02:38:00+02:00",
        },
    ],
}


def broken(doc: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    """A deep copy of doc with one field changed; a None value deletes it."""
    out = copy.deepcopy(doc)
    *parents, last = path.split(".")
    node: Any = out
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    if value is None:
        del node[last]
    else:
        node[last] = value
    return out


def test_a_valid_schedule_reads_through() -> None:
    s = parse_schedule(SCHEDULE)
    assert [r.id for r in s.regions] == ["global-eu", "kr"]
    rift = s.events[0]
    assert (rift.duration_min, rift.entry_min) == (60, 10)
    eu, kr = s.region("global-eu"), s.region("kr")
    assert eu and kr
    rule = rift.rule_for(eu)
    assert rule and rule.time_zone == "UTC" and rule.times == ((0, 0), (3, 0))
    assert rift.rule_for(kr) == dict(rift.rules)["kr"]


def test_weekly_days_become_sorted_weekday_numbers() -> None:
    bosses = parse_schedule(SCHEDULE).events[1]
    assert bosses.realm == "abyss"
    rule = dict(bosses.rules)["global"]
    assert rule.days == (0, 5)  # mon, sat
    assert dict(bosses.rules)["kr"].groups == ("1", "2")


def test_a_region_without_a_rule_has_none() -> None:
    s = parse_schedule(SCHEDULE)
    kr = s.region("kr")
    assert kr and s.events[2].rule_for(kr) is None


def test_unknown_fields_are_ignored() -> None:
    doc = broken(SCHEDULE, "events.0.note", "a field from a newer app")
    assert parse_schedule(doc).events[0].id == "rift"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("format", "map-overlay-route"),
        ("regions", []),
        ("events", []),
        ("updatedAt", None),
        ("regions.0.timeZone", "Mars/Olympus"),
        ("regions.0.group", None),
        ("events.0.kind", "festival"),
        ("events.0.name", ""),
        ("events.0.durationMinutes", -5),
        ("events.0.schedules", {}),
        ("events.0.schedules.global.type", "monthly"),
        ("events.0.schedules.global.times", ["25:00"]),
        ("events.0.schedules.global.times", ["9:00"]),
        ("events.0.schedules.global.times", []),
        ("events.0.schedules.global.timeZone", "Nowhere"),
        ("events.1.realm", "sky"),
        ("events.1.schedules.global.days", ["someday"]),
        ("events.1.schedules.kr.groups", ["1"]),
        ("events.2.schedules.global.minute", 60),
    ],
)
def test_each_broken_field_refuses_the_whole_schedule(path: str, value: Any) -> None:
    with pytest.raises(TimersError) as e:
        parse_schedule(broken(SCHEDULE, path, value))
    assert e.value.code == "timers.invalid"


def test_duplicate_ids_are_refused() -> None:
    doc = broken(SCHEDULE, "events.1.id", "rift")
    with pytest.raises(TimersError, match="events"):
        parse_schedule(doc)


def test_another_version_is_refused_with_its_number() -> None:
    with pytest.raises(TimersError) as e:
        parse_schedule(broken(SCHEDULE, "version", 2))
    assert e.value.code == "timers.version" and e.value.params == {"version": "2"}


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("13s", 13),
        ("3min 11s", 191),
        ("1h 2min 26s", 3746),
        ("11h 16min 50s", 40610),
        ("30m", 1800),
        ("1h 30m", 5400),
        ("12h", 43200),
    ],
)
def test_durations_read_as_the_game_and_the_files_write_them(text: str, seconds: int) -> None:
    assert parse_duration(text, "t") == seconds


@pytest.mark.parametrize("text", ["", "soon", "5 minutes", "1h and 2min", "12", None, 30])
def test_anything_else_is_not_a_duration(text: Any) -> None:
    with pytest.raises(TimersError):
        parse_duration(text, "t")


def test_world_bosses_become_utc_moments() -> None:
    w = parse_world_bosses(BOSSES)
    read_at = datetime(2026, 10, 5, 13, 18, tzinfo=UTC)
    assert w.read_at == read_at
    aed, gartua, lagta = w.bosses
    assert aed.spawns_at == read_at + timedelta(seconds=13)
    assert aed.respawn_s == 1800
    assert gartua.spawns_at == read_at + timedelta(hours=11, minutes=16, seconds=50)
    assert lagta.spawns_at == datetime(2026, 10, 6, 0, 38, tzinfo=UTC)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("readAt", "2026-10-05 13:18"),
        ("readAt", None),
        ("bosses.0.timeLeft", "soon"),
        ("bosses.0.respawn", None),
        ("bosses.0.level", -1),
        ("bosses.2.spawnsAt", "tomorrow"),
        ("bosses.1.id", "aed"),
        ("bosses.0.drops", "painting"),
        ("bosses.0.drops", ["painting", ""]),
    ],
)
def test_each_broken_boss_field_refuses_the_list(path: str, value: Any) -> None:
    with pytest.raises(TimersError):
        parse_world_bosses(broken(BOSSES, path, value))


def test_a_boss_drops_what_the_list_says_and_nothing_by_default() -> None:
    doc = broken(BOSSES, "bosses.0.drops", ["painting", "painting", "relic"])
    aed, gartua, _ = parse_world_bosses(doc).bosses
    assert aed.drops == ("painting", "relic"), "repeats go, an unknown kind is kept"
    assert gartua.drops == ()


def test_the_bundled_files_load() -> None:
    schedule = bundled_schedule()
    bosses = bundled_world_bosses()
    assert schedule and bosses
    assert {e.id for e in schedule.events} >= {"rift", "daily-reset", "weekly-reset"}
    assert len(bosses.bosses) == 24
    assert sum("painting" in b.drops for b in bosses.bosses) == 11
    eu = schedule.region(bosses.region)
    assert eu is not None, "the bosses' region must be one of the schedule's"
    # every Global region has a rule for every event
    for region in (r for r in schedule.regions if r.group == "global"):
        assert all(e.rule_for(region) for e in schedule.events), region.id


def test_the_bundled_files_name_no_events_the_owner_dropped() -> None:
    doc = json.loads(resource_path("assets/timers/schedule.json").read_text(encoding="utf-8"))
    ids = {e["id"] for e in doc["events"]}
    assert not ids & {"dimensional-invasion", "watcher-kaira", "global-launch"}
