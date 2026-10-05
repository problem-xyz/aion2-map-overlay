"""The timers' clock, against fixed moments: summer time, week edges, server groups, bosses.

2026-10-05 is a Monday. Europe/Berlin leaves summer time on 2026-10-25 and America/New_York on
2026-11-01, so those weeks are where a UTC event and a region's reset move apart by an hour.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from map_overlay.store.timers import (
    Region,
    Schedule,
    TimedEvent,
    WorldBoss,
    WorldBosses,
    bundled_schedule,
    parse_schedule,
)
from map_overlay.timers.schedule import (
    KILL,
    UP,
    boss_spawns,
    boss_state,
    bosses_with_wrong_cycle,
    event_state,
    occurrences,
)

BERLIN = ZoneInfo("Europe/Berlin")


def at(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.fixture(scope="module")
def schedule() -> Schedule:
    s = bundled_schedule()
    assert s is not None
    return s


def ev(schedule: Schedule, event_id: str) -> TimedEvent:
    return next(e for e in schedule.events if e.id == event_id)


def reg(schedule: Schedule, region_id: str) -> Region:
    r = schedule.region(region_id)
    assert r is not None
    return r


def test_the_rift_is_live_with_entry_open_for_its_first_ten_minutes(schedule: Schedule) -> None:
    rift, eu = ev(schedule, "rift"), reg(schedule, "global-eu")
    s = event_state(rift, eu, at(2026, 10, 5, 12, 5))
    assert s.live and s.live.start == at(2026, 10, 5, 12) and s.live.end == at(2026, 10, 5, 13)
    assert s.entry_closes == at(2026, 10, 5, 12, 10)
    assert s.next and s.next.start == at(2026, 10, 5, 15)

    later = event_state(rift, eu, at(2026, 10, 5, 12, 15))
    assert later.live and later.entry_closes is None


def test_between_rifts_nothing_is_live(schedule: Schedule) -> None:
    s = event_state(ev(schedule, "rift"), reg(schedule, "global-eu"), at(2026, 10, 5, 13, 50))
    assert s.live is None and s.next and s.next.start == at(2026, 10, 5, 15)


def test_the_shugo_festival_runs_ten_minutes_every_hour(schedule: Schedule) -> None:
    shugo, eu = ev(schedule, "shugo-festival"), reg(schedule, "global-eu")
    live = event_state(shugo, eu, at(2026, 10, 5, 13, 4))
    assert live.live and live.live.end == at(2026, 10, 5, 13, 10)
    idle = event_state(shugo, eu, at(2026, 10, 5, 13, 10))
    assert idle.live is None and idle.next and idle.next.start == at(2026, 10, 5, 14)


def test_a_utc_event_moves_an_hour_in_berlin_when_summer_time_ends(schedule: Schedule) -> None:
    siege, eu = ev(schedule, "artifact-siege"), reg(schedule, "global-eu")
    starts = [o.start for o in occurrences(siege, eu, at(2026, 10, 22), at(2026, 10, 27))]
    # Thu 22, Sat 24, Mon 26 at 21:00 UTC
    assert starts == [at(2026, 10, 22, 21), at(2026, 10, 24, 21), at(2026, 10, 26, 21)]
    local = [s.astimezone(BERLIN).hour for s in starts]
    assert local == [23, 23, 22]


def test_a_regional_reset_keeps_its_local_hour_across_the_change(schedule: Schedule) -> None:
    reset, eu = ev(schedule, "daily-reset"), reg(schedule, "global-eu")
    starts = [o.start for o in occurrences(reset, eu, at(2026, 10, 24), at(2026, 10, 27))]
    assert starts == [at(2026, 10, 24, 7), at(2026, 10, 25, 8), at(2026, 10, 26, 8)]
    assert {s.astimezone(BERLIN).hour for s in starts} == {9}


def test_new_york_changes_a_week_later(schedule: Schedule) -> None:
    reset, nae = ev(schedule, "daily-reset"), reg(schedule, "global-nae")
    starts = [o.start for o in occurrences(reset, nae, at(2026, 10, 31), at(2026, 11, 3))]
    assert starts == [at(2026, 10, 31, 13), at(2026, 11, 1, 14), at(2026, 11, 2, 14)]


def test_the_weekly_reset_is_found_across_the_week(schedule: Schedule) -> None:
    weekly, eu = ev(schedule, "weekly-reset"), reg(schedule, "global-eu")
    s = event_state(weekly, eu, at(2026, 10, 5, 13, 50))
    # a moment, not a span: never live, next on Wednesday 09:00 Berlin
    assert s.live is None and s.next and s.next.start == at(2026, 10, 7, 7)
    after = event_state(weekly, eu, at(2026, 10, 7, 7))
    assert after.next and after.next.start == at(2026, 10, 14, 7)


def test_nahma_after_sunday_night_is_on_friday(schedule: Schedule) -> None:
    nahma, eu = ev(schedule, "guardian-nahma"), reg(schedule, "global-eu")
    s = event_state(nahma, eu, at(2026, 10, 11, 21, 40))
    assert s.live is None and s.next and s.next.start == at(2026, 10, 16, 21)


def test_a_server_group_keeps_only_its_own_times(schedule: Schedule) -> None:
    bosses, kr = ev(schedule, "siege-bosses"), reg(schedule, "kr")
    # Wednesday 2026-10-07 in Korea; 22:15 KST is 13:15 UTC
    every = occurrences(bosses, kr, at(2026, 10, 7), at(2026, 10, 8))
    assert [o.group for o in every] == ["1", "2", "3"]
    mine = occurrences(bosses, kr, at(2026, 10, 7), at(2026, 10, 8), server_group="2")
    assert [(o.start, o.group) for o in mine] == [(at(2026, 10, 7, 13, 15), "2")]


def test_a_region_the_event_does_not_run_in_has_nothing() -> None:
    doc = {
        "format": "map-overlay-timers",
        "version": 1,
        "updatedAt": "x",
        "regions": [{"id": "kr", "group": "kr", "label": "Korea", "timeZone": "Asia/Seoul"}],
        "events": [
            {
                "id": "launch",
                "name": "Launch",
                "kind": "event",
                "icon": "x",
                "schedules": {"global": {"type": "once", "at": "2026-10-05T13:00:00Z"}},
            }
        ],
    }
    s = parse_schedule(doc)
    assert occurrences(s.events[0], s.regions[0], at(2026, 10, 1), at(2026, 10, 9)) == []


def test_a_once_event_is_next_until_it_passes() -> None:
    doc = {
        "format": "map-overlay-timers",
        "version": 1,
        "updatedAt": "x",
        "regions": [{"id": "eu", "group": "global", "label": "EU", "timeZone": "Europe/Berlin"}],
        "events": [
            {
                "id": "launch",
                "name": "Launch",
                "kind": "event",
                "icon": "x",
                "schedules": {"global": {"type": "once", "at": "2026-10-05T13:00:00Z"}},
            }
        ],
    }
    s = parse_schedule(doc)
    before = event_state(s.events[0], s.regions[0], at(2026, 10, 5, 12))
    assert before.next and before.next.start == at(2026, 10, 5, 13)
    assert event_state(s.events[0], s.regions[0], at(2026, 10, 5, 14)).next is None


def boss(spawns_at: datetime, respawn_min: int = 30) -> WorldBoss:
    return WorldBoss(
        id="aed",
        name="Black Warrior Aed",
        area="",
        level=45,
        respawn_s=respawn_min * 60,
        spawns_at=spawns_at,
    )


READ = at(2026, 10, 5, 13, 18)


def test_before_its_spawn_a_boss_waits_on_the_reading() -> None:
    b = boss(READ + timedelta(seconds=13))
    s = boss_state(b, READ)
    assert (s.spawn, s.up, s.estimated) == (READ + timedelta(seconds=13), False, False)


def test_a_boss_is_up_for_a_few_minutes_after_spawning() -> None:
    b = boss(READ)
    assert boss_state(b, READ + timedelta(minutes=1)).up
    after = boss_state(b, READ + UP)
    assert not after.up and after.estimated
    assert after.spawn == READ + KILL + timedelta(minutes=30)


def test_many_cycles_later_the_estimate_is_the_right_cycle() -> None:
    b = boss(READ)
    cycle = KILL + timedelta(minutes=30)
    now = READ + timedelta(hours=10, minutes=7)
    s = boss_state(b, now)
    assert s.estimated
    assert (s.spawn - READ) % cycle == timedelta(0)
    assert s.spawn - cycle + UP <= now < s.spawn + UP


def test_a_boss_without_a_cycle_stays_on_its_reading() -> None:
    b = boss(READ, respawn_min=0)
    s = boss_state(b, READ + timedelta(hours=2))
    assert s.spawn == READ and not s.up and not s.estimated
    assert boss_spawns(b, READ - timedelta(hours=1), READ + timedelta(hours=5)) == [READ]


def test_the_spawns_in_a_window_are_a_cycle_apart() -> None:
    b = boss(READ)
    spawns = boss_spawns(b, READ + timedelta(minutes=40), READ + timedelta(hours=2, minutes=40))
    cycle = KILL + timedelta(minutes=30)
    assert spawns == [READ + cycle * k for k in (2, 3, 4, 5)]


def test_a_spawn_still_up_at_the_window_start_is_in_it() -> None:
    b = boss(READ)
    assert boss_spawns(b, READ + timedelta(minutes=2), READ + timedelta(minutes=10)) == [READ]


def test_a_time_left_longer_than_the_cycle_flags_the_cycle() -> None:
    ok = boss(READ + timedelta(minutes=29))
    wrong = WorldBoss("trid", "Deceiver Trid", "", 45, 3600, READ + timedelta(hours=1, minutes=5))
    reading = WorldBosses(read_at=READ, region="global-eu", map="", faction="", bosses=(ok, wrong))
    assert bosses_with_wrong_cycle(reading) == ["trid"]
