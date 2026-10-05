"""getState()["timers"]: the region worked out or chosen, each event with the user's choices over
the defaults, and the world bosses only where their reading belongs."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from map_overlay.core.settings import Settings
from map_overlay.store.timers import bundled_schedule, bundled_world_bosses
from map_overlay.timers.data import TimersData
from map_overlay.timers.view import guess_region, timers_view

NOW = datetime(2026, 10, 5, 12, 5, tzinfo=UTC)  # a Monday; the noon rift is five minutes in
BERLIN = timedelta(hours=2)


def data() -> TimersData:
    return TimersData(schedule=bundled_schedule(), bosses=bundled_world_bosses())


def view(**settings: Any) -> dict[str, Any]:
    out = timers_view(data(), Settings(**settings), NOW, BERLIN)
    assert out is not None
    return out


def event(v: dict[str, Any], event_id: str) -> dict[str, Any]:
    return next(e for e in v["events"] if e["id"] == event_id)


@pytest.mark.parametrize(
    ("hours", "region"),
    [
        (0, "global-eu"),
        (2, "global-eu"),
        (-3, "global-sa"),
        (-6, "global-nae"),
        (-4, "global-nae"),
        (-5, "global-nae"),
        (-7, "global-naw"),
        (-8, "global-naw"),
        (9, "global-as"),
        (5, "global-as"),
    ],
)
def test_the_region_is_guessed_from_the_clock(hours: int, region: str) -> None:
    schedule = bundled_schedule()
    assert schedule
    assert guess_region(schedule, timedelta(hours=hours)).id == region


def test_a_guessed_region_says_so_and_a_chosen_one_does_not() -> None:
    assert (view()["region"], view()["regionGuessed"]) == ("global-eu", True)
    chosen = view(timers_region="global-nae")
    assert (chosen["region"], chosen["regionGuessed"]) == ("global-nae", False)
    unknown = view(timers_region="mars")
    assert (unknown["region"], unknown["regionGuessed"]) == ("global-eu", True)


def test_moments_are_epoch_milliseconds() -> None:
    v = view()
    rift = event(v, "rift")
    assert v["now"] == int(NOW.timestamp() * 1000)
    assert rift["live"] == {
        "start": int(datetime(2026, 10, 5, 12, tzinfo=UTC).timestamp() * 1000),
        "end": int(datetime(2026, 10, 5, 13, tzinfo=UTC).timestamp() * 1000),
    }
    assert rift["entryCloses"] == int(datetime(2026, 10, 5, 12, 10, tzinfo=UTC).timestamp() * 1000)
    assert rift["next"]["start"] == int(datetime(2026, 10, 5, 15, tzinfo=UTC).timestamp() * 1000)


def test_the_occurrences_cover_two_hours_back_to_two_days_ahead() -> None:
    shugo = event(view(), "shugo-festival")
    starts = [s for s, _e in shugo["occurrences"]]
    # hourly from 10:00 today, still running at 10:05, to 12:00 the day after tomorrow
    assert len(starts) == 51
    assert starts == sorted(starts)


def test_the_users_choices_lie_over_the_defaults() -> None:
    v = view(
        timers_events={"rift": {"lead": 10, "signal": "voice"}, "shugo-festival": {"shown": False}}
    )
    assert {k: event(v, "rift")[k] for k in ("shown", "lead", "signal")} == {
        "shown": True,
        "lead": 10,
        "signal": "voice",
    }
    assert event(v, "shugo-festival")["shown"] is False
    assert event(v, "daily-reset")["lead"] == 0


def test_korea_has_server_groups_and_one_can_be_chosen() -> None:
    kr = view(timers_region="kr")
    assert kr["serverGroups"] == ["1", "2", "3"]
    assert kr["serverGroup"] is None
    one = view(timers_region="kr", timers_server_group="2")
    assert one["serverGroup"] == "2"
    assert view(timers_server_group="2")["serverGroup"] is None  # Europe has no groups


def test_world_bosses_belong_to_the_region_they_were_read_on() -> None:
    eu = view(timers_world_shown=["melted-danar"])
    assert len(eu["bosses"]) == 24
    danar = next(b for b in eu["bosses"] if b["id"] == "melted-danar")
    assert danar["shown"] and danar["respawnS"] == 1800
    assert eu["bossesReadAt"] is not None and eu["bossesMap"] == "altgard"
    elsewhere = view(timers_region="global-nae")
    assert elsewhere["bosses"] == [] and elsewhere["bossesReadAt"] is None


def test_no_schedule_means_no_timers() -> None:
    assert timers_view(TimersData(None, None), Settings(), NOW, BERLIN) is None


def test_a_weekly_event_names_its_starts_over_the_week() -> None:
    v = view()
    siege = event(v, "artifact-siege")
    days = {datetime.fromtimestamp(s / 1000, UTC).weekday() for s in siege["weekStarts"]}
    assert days == {0, 3, 5}  # Monday, Thursday, Saturday
    assert event(v, "rift")["weekStarts"] == []
