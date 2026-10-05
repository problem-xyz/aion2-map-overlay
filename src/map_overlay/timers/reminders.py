"""Which reminders fall due when, and what each one sounds like. No Qt.

A reminder is due `lead` minutes before an occurrence starts, for every event the user gave a
lead, and for every world boss on the plaque under the bosses' common lead. The service asks
for the reminders in the stretch since it last looked, so a reminder is never missed between
two looks and never sounded twice; and for the next one, to wake exactly then.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from map_overlay.core.paths import resource_path
from map_overlay.core.settings import Settings
from map_overlay.timers.data import TimersData
from map_overlay.timers.schedule import boss_spawns, occurrences
from map_overlay.timers.view import choice, resolve_region, server_groups

Signal = Literal["voice", "chime"]

SOUNDS_DIR = "assets/sounds"
CHIME = "chime.wav"
# A world boss's phrase is one for them all: "A world boss spawns in 5 minutes".
WORLD_BOSS_VOICE = "world-boss"


@dataclass(frozen=True)
class Reminder:
    event_id: str  # a world boss's id for a boss
    name: str
    start: datetime  # when the event starts or the boss spawns (UTC)
    at: datetime  # when the reminder is due (UTC)
    lead: int  # minutes
    signal: Signal
    boss: bool = False

    @property
    def key(self) -> tuple[str, datetime]:
        """The same occurrence of the same event: sounded once whatever looks at it twice."""
        return (self.event_id, self.start)


def reminders_between(
    data: TimersData, settings: Settings, utc_offset: timedelta, after: datetime, until: datetime
) -> list[Reminder]:
    """Every reminder due in (after, until], earliest first."""
    schedule = data.schedule
    if schedule is None or until <= after:
        return []
    region, _guessed = resolve_region(schedule, settings.timers_region, utc_offset)
    groups = server_groups(schedule, region)
    group = settings.timers_server_group if settings.timers_server_group in groups else None
    out: list[Reminder] = []
    for event in schedule.events:
        picked = choice(settings, event)
        lead = timedelta(minutes=int(picked["lead"]))
        if not lead:
            continue
        for o in occurrences(
            event, region, after + lead, until + lead + timedelta(seconds=1), group
        ):
            at = o.start - lead
            if after < at <= until:
                out.append(
                    Reminder(
                        event.id, event.name, o.start, at, int(picked["lead"]), picked["signal"]
                    )
                )
    bosses = data.bosses
    lead_min = settings.timers_world_lead
    if bosses is not None and bosses.region == region.id and lead_min > 0:
        lead = timedelta(minutes=lead_min)
        shown = set(settings.timers_world_shown)
        for boss in bosses.bosses:
            if boss.id not in shown:
                continue
            for spawn in boss_spawns(boss, after + lead, until + lead + timedelta(seconds=1)):
                at = spawn - lead
                if after < at <= until:
                    signal: Signal = settings.timers_world_signal  # pyright: ignore[reportAssignmentType]
                    out.append(Reminder(boss.id, boss.name, spawn, at, lead_min, signal, boss=True))
    out.sort(key=lambda r: (r.at, r.event_id))
    return out


def sound_for(reminder: Reminder | None, sounds_dir: Path | None = None) -> Path:
    """The file a reminder plays: its phrase where one ships, else the chime; None, the chime.

    Phrases are voice/<event id>-<lead>.wav, and voice/world-boss-<lead>.wav for any world boss.
    A schedule may name an event the app has no phrase for yet; it chimes until one ships.
    """
    root = sounds_dir or resource_path(SOUNDS_DIR)
    if reminder is not None and reminder.signal == "voice":
        name = WORLD_BOSS_VOICE if reminder.boss else reminder.event_id
        phrase = root / "voice" / f"{name}-{reminder.lead}.wav"
        if phrase.is_file():
            return phrase
    return root / CHIME
