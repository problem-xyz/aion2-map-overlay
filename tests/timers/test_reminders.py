"""The reminders: which fall due when, what each sounds like, and that the service sounds each one
once, at its moment, and never a pile of them after the machine slept."""

import io
import itertools
import threading
import wave
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.timers_data import TimersDataService
from map_overlay.bridge.timers_service import TimersService
from map_overlay.core.paths import DataDirs, resource_path
from map_overlay.core.settings import Settings
from map_overlay.store.timers import bundled_schedule, bundled_world_bosses
from map_overlay.timers.data import Fetched, TimersData, TimersStore
from map_overlay.timers.reminders import Reminder, reminders_between, sound_for
from map_overlay.timers.sound import SoundPlayer, scaled

BERLIN = timedelta(hours=2)
NOON = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # a Monday


def data() -> TimersData:
    return TimersData(schedule=bundled_schedule(), bosses=bundled_world_bosses())


def only(**events: dict[str, object]) -> dict[str, dict[str, object]]:
    """Every event silenced but the ones given."""
    schedule = bundled_schedule()
    assert schedule
    out: dict[str, dict[str, object]] = {e.id: {"lead": 0} for e in schedule.events}
    out.update(events)
    return out


def test_a_reminder_falls_due_lead_minutes_before_the_start() -> None:
    settings = Settings(timers_events=only(rift={"lead": 5, "signal": "voice"}))
    due = reminders_between(
        data(), settings, BERLIN, NOON + timedelta(hours=2), NOON + timedelta(hours=3)
    )
    assert [(r.event_id, r.at, r.start, r.signal) for r in due] == [
        ("rift", NOON + timedelta(hours=2, minutes=55), NOON + timedelta(hours=3), "voice")
    ]


def test_the_stretch_is_open_at_its_start_and_closed_at_its_end() -> None:
    settings = Settings(timers_events=only(rift={"lead": 5}))
    at = NOON + timedelta(hours=2, minutes=55)
    assert reminders_between(data(), settings, BERLIN, at, at + timedelta(minutes=1)) == []
    assert len(reminders_between(data(), settings, BERLIN, at - timedelta(seconds=1), at)) == 1


def test_resets_and_events_without_a_lead_stay_quiet() -> None:
    day = reminders_between(
        data(), Settings(timers_events=only()), BERLIN, NOON, NOON + timedelta(days=2)
    )
    assert day == []


def test_world_bosses_remind_only_when_on_the_plaque() -> None:
    quiet = Settings(timers_events=only(), timers_world_lead=5)
    assert reminders_between(data(), quiet, BERLIN, NOON, NOON + timedelta(hours=2)) == []
    shown = Settings(timers_events=only(), timers_world_lead=5, timers_world_shown=["melted-danar"])
    # an hour past the reading, whenever it was made, the spawns are a cycle and a kill apart
    bosses = data().bosses
    assert bosses is not None
    after = bosses.read_at + timedelta(hours=1)
    due = reminders_between(data(), shown, BERLIN, after, after + timedelta(hours=2))
    assert due and all(r.boss and r.event_id == "melted-danar" for r in due)
    gaps = {(b.at - a.at) for a, b in itertools.pairwise(due)}
    assert gaps == {timedelta(minutes=31, seconds=30)}


def test_a_phrase_that_does_not_ship_falls_back_to_the_chime(tmp_path: Path) -> None:
    (tmp_path / "voice").mkdir()
    (tmp_path / "chime.wav").write_bytes(b"x")
    (tmp_path / "voice" / "rift-5.wav").write_bytes(b"x")
    (tmp_path / "voice" / "world-boss-5.wav").write_bytes(b"x")

    def r(event_id: str, lead: int, signal: str = "voice", boss: bool = False) -> Reminder:
        return Reminder(event_id, "", NOON, NOON, lead, signal, boss)  # pyright: ignore[reportArgumentType]

    assert sound_for(r("rift", 5), tmp_path).name == "rift-5.wav"
    assert sound_for(r("rift", 10), tmp_path).name == "chime.wav"
    assert sound_for(r("rift", 5, "chime"), tmp_path).name == "chime.wav"
    assert sound_for(r("melted-danar", 5, boss=True), tmp_path).name == "world-boss-5.wav"
    assert sound_for(None, tmp_path).name == "chime.wav"


def test_the_chime_ships() -> None:
    assert sound_for(None).is_file()
    assert sound_for(None) == resource_path("assets/sounds/chime.wav")


def samples(data: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(data), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")


def test_the_volume_scales_the_samples() -> None:
    chime = sound_for(None).read_bytes()
    full = samples(chime).astype(np.int32)
    half = samples(scaled(chime, 0.5)).astype(np.int32)
    assert np.abs(half - full // 2).max() <= 1
    assert not samples(scaled(chime, 0)).any()
    assert scaled(b"not a wav", 0.5) == b"not a wav"


# ---------- the service: one sound per reminder, at its moment ----------


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class Played:
    def __init__(self) -> None:
        self.sounds: list[bytes] = []

    def player(self) -> SoundPlayer:
        return SoundPlayer(play=self.sounds.append, stop=lambda: None)


@pytest.fixture
def service(
    qapp: QApplication, dirs: DataDirs
) -> Iterator[tuple[TimersService, Clock, Played, dict[str, object]]]:
    clock = Clock(NOON + timedelta(hours=2, minutes=50))
    played = Played()
    store: dict[str, object] = {"settings": Settings(timers_events=only(rift={"lead": 5}))}
    offline = TimersDataService(
        TimersStore(dirs.cache), lambda _u, _e: Fetched(None, None), 10**9, 10**9
    )
    s = TimersService(
        dirs,
        settings=lambda: store["settings"],  # pyright: ignore[reportArgumentType]
        update_settings=lambda _patch: None,
        notify=lambda _level, _code: None,
        data=offline,
        player=played.player(),
        clock=clock,
    )
    s.start()
    yield s, clock, played, store
    s.close()


def fire(s: TimersService) -> None:
    s._on_due()
    for thread in threading.enumerate():
        if thread.name == "timers-sound":
            thread.join(2)


def test_the_service_wakes_for_the_next_reminder(
    service: tuple[TimersService, Clock, Played, dict[str, object]],
) -> None:
    s, _clock, _played, _store = service
    assert s._remind.isActive()
    # 14:55 is five minutes ahead of the clock
    assert 299_000 <= s._remind.remainingTime() <= 301_000


def test_a_reminder_sounds_once(
    service: tuple[TimersService, Clock, Played, dict[str, object]],
) -> None:
    s, clock, played, _store = service
    names: list[str] = []
    s.reminded.connect(names.append)
    clock.now = NOON + timedelta(hours=2, minutes=55, seconds=1)
    fire(s)
    fire(s)
    assert len(played.sounds) == 1 and len(names) == 1
    assert '"id": "rift"' in names[0]


def test_after_a_sleep_the_missed_reminders_stay_quiet(
    service: tuple[TimersService, Clock, Played, dict[str, object]],
) -> None:
    s, clock, played, _store = service
    clock.now = NOON + timedelta(hours=9)  # slept through 14:55, 17:55 and 20:55
    fire(s)
    assert played.sounds == []


def test_with_the_sound_off_the_plaque_is_asked_to_show_itself(
    service: tuple[TimersService, Clock, Played, dict[str, object]],
) -> None:
    s, clock, played, store = service
    store["settings"] = Settings(timers_events=only(rift={"lead": 5}), timers_sound=False)
    peeks: list[bool] = []
    s.peek.connect(lambda: peeks.append(True))
    clock.now = NOON + timedelta(hours=2, minutes=55, seconds=1)
    fire(s)
    assert played.sounds == [] and peeks == [True]


def test_the_preview_plays_whatever_the_sound_switch_says(
    service: tuple[TimersService, Clock, Played, dict[str, object]],
) -> None:
    s, _clock, played, store = service
    store["settings"] = Settings(timers_sound=False, timers_volume=0.5)
    s.preview("rift")
    s.preview("")
    for thread in threading.enumerate():
        if thread.name == "timers-sound":
            thread.join(2)
    assert len(played.sounds) == 2
