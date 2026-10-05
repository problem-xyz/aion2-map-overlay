"""Update world-bosses.json from the game's boss list, as typed or pasted from it.

    uv run python scripts/world_bosses.py reading.txt
    uv run python scripts/world_bosses.py - < reading.txt            # from stdin
    uv run python scripts/world_bosses.py reading.txt --file <path>  # another copy of the file
    uv run python scripts/world_bosses.py reading.txt --read-at 2026-10-06T09:12:00Z

The text is the list as the game shows it: a boss's name on one line, then "Time Left 29min 8s"
on the next. The distance the game prints beside a name ("2,870m") is ignored, and a name the
game cut short ("Special Operations Lead...") is matched by its start, when only one boss
begins that way.

readAt becomes the moment of the reading (now, unless --read-at says otherwise) and every boss
read gets its new timeLeft. A boss missing from the text keeps its place: its next spawn as the
last reading projects it is written as spawnsAt, so moving readAt does not move it.

Nothing is committed or pushed; the script says what changed. Exit status 1, with the file
untouched, when a name matches no boss or the text has no reading at all.
"""

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from map_overlay.core.fileio import atomic_write_text
from map_overlay.store.timers import TimersError, parse_duration, parse_world_bosses
from map_overlay.timers.schedule import boss_state

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "assets" / "timers" / "world-bosses.json"

TIME_LEFT = re.compile(r"^time\s*left\s*:?\s*(.+)$", re.IGNORECASE)
DISTANCE = re.compile(r"\s+[\d,.]+\s*m$")
CUT_SHORT = re.compile(r"(\.\.\.|…)$")


class ReadingError(Exception):
    """The text cannot be applied; the message says why."""


@dataclass(frozen=True)
class Reading:
    name: str
    time_left: str


def parse_reading(text: str) -> list[Reading]:
    """Name and time left of each boss in the text, in the order the game listed them."""
    out = []
    name: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = TIME_LEFT.match(line)
        if m:
            if name is None:
                raise ReadingError(f"'{line}' has no boss name above it")
            out.append(Reading(name, m[1].strip()))
            name = None
        else:
            name = DISTANCE.sub("", line).strip()
    return out


def match_name(name: str, known: Sequence[str]) -> str | None:
    """The known name this one is: the same, or the only one it is the start of when cut short."""
    folded = name.casefold()
    exact = [k for k in known if k.casefold() == folded]
    if exact:
        return exact[0]
    stem = CUT_SHORT.sub("", name).strip().casefold()
    if stem == folded:
        return None
    starts = [k for k in known if k.casefold().startswith(stem)]
    return starts[0] if len(starts) == 1 else None


def apply_reading(doc: dict[str, Any], readings: Sequence[Reading], read_at: datetime) -> list[str]:
    """Write the readings into doc in place; returns what changed, one line per boss."""
    if not readings:
        raise ReadingError("the text has no 'Time Left' lines")
    try:
        before = parse_world_bosses(doc)
    except TimersError as e:
        raise ReadingError(f"the file itself does not load: {e}") from e
    by_name = {b["name"]: b for b in doc["bosses"]}
    seen: set[str] = set()
    report = []
    for r in readings:
        name = match_name(r.name, list(by_name))
        if name is None:
            raise ReadingError(f"'{r.name}' is not a boss in the file")
        try:
            left = parse_duration(r.time_left, name)
        except TimersError as e:
            raise ReadingError(f"'{r.time_left}' for {name} is not a time") from e
        boss = by_name[name]
        boss.pop("spawnsAt", None)
        boss["timeLeft"] = r.time_left
        seen.add(name)
        respawn = parse_duration(boss["respawn"], name)
        warn = (
            "  (longer than its respawn: the cycle in the file is wrong)" if left > respawn else ""
        )
        report.append(f"{name}: {r.time_left}{warn}")
    for b in before.bosses:
        if b.name in seen:
            continue
        spawn = boss_state(b, read_at).spawn
        boss = by_name[b.name]
        boss.pop("timeLeft", None)
        boss["spawnsAt"] = spawn.strftime("%Y-%m-%dT%H:%M:%SZ")
        report.append(f"{b.name}: not in the reading, kept at {boss['spawnsAt']}")
    doc["readAt"] = read_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    parse_world_bosses(doc)  # what is written must load
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update world-bosses.json from the game's list.")
    parser.add_argument("reading", help="a text file with the game's list, or - for stdin")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="world-bosses.json")
    parser.add_argument(
        "--read-at", help="when the list was read, ISO with offset; now if left out"
    )
    args = parser.parse_args(argv)

    text = (
        sys.stdin.read()
        if args.reading == "-"
        else Path(args.reading).read_text(encoding="utf-8-sig")
    )
    read_at = datetime.fromisoformat(args.read_at) if args.read_at else datetime.now(UTC)
    if read_at.tzinfo is None:
        print("refused: --read-at needs an offset, e.g. 2026-10-06T09:12:00Z", file=sys.stderr)
        return 1
    doc = json.loads(args.file.read_text(encoding="utf-8"))
    try:
        report = apply_reading(doc, parse_reading(text), read_at.astimezone(UTC))
    except ReadingError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    atomic_write_text(args.file, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(f"{args.file}: read at {doc['readAt']}")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
