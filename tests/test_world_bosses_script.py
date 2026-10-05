"""scripts/world_bosses.py: the game's boss list, typed out, into world-bosses.json.

The reading below is the owner's two screenshots of the in-game list, line for line, with the
distances the game prints beside each name.
"""

import copy
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from map_overlay.store.timers import parse_world_bosses

REPO = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wb = load_script(REPO / "scripts" / "world_bosses.py", "world_bosses")

READING = """\
Melted Danar 2,870m
Time Left 29min 8s
Black Warrior Aed 3,625m
Time Left 13s
Faithful Rajit 3,103m
Time Left 3min 11s
Berserker Vargor 3,113m
Time Left 34min 4s
Predator Garsan 1,479m
Time Left 1h 31min 19s
Blood Warrior Lannar 1,676m
Time Left 1h 2min 26s
Deceiver Trid 2,043m
Time Left 1h 32min 40s
Blue Wave Kelpina 2,395m
Time Left 1h 33min 59s
High Overseer Nutah 3,056m
Time Left 1h 34min 20s
Advisor Resana 3,415m
Time Left 2h 33min 27s
Special Operations Lead... 2,783m
Time Left 2h 25min 44s
Desecrator Newbold 3,014m
Time Left 3h 25min 8s
Specter Archon Axios 2,462m
Time Left 3h 27min 31s
Addicted Hardirun 1,433m
Time Left 2h 29min 16s
Executioner Barthien 878m
Time Left 3h 28min 53s
Drakan Battalion Weapo... 1,247m
Time Left 5h 27min 24s
Veteran Shujakan 444m
Time Left 2h 26min 36s
Visionary Karuka 69m
Time Left 3h 24min 20s
Dark Shadow Vishwada 701m
Time Left 5h 22min 49s
Sharp Shylak 869m
Time Left 5h 24min 46s
Immortal Gartua 2,710m
Time Left 11h 16min 50s
High Commander Lagta 892m
Time Left 11h 20min 52s
Soul Ruler Kashapa 1,218m
Time Left 5h 21min 11s
Silent Dartan 2,753m
Time Left 5h 22min 40s
"""

READ_AT = datetime(2026, 10, 6, 9, 12, tzinfo=UTC)


@pytest.fixture
def doc() -> dict[str, Any]:
    return json.loads((REPO / "assets" / "timers" / "world-bosses.json").read_text("utf-8"))


def test_both_screenshots_read_as_24_bosses() -> None:
    readings = wb.parse_reading(READING)
    assert len(readings) == 24
    assert readings[0] == wb.Reading("Melted Danar", "29min 8s")
    assert readings[10].name == "Special Operations Lead..."


def test_cut_names_match_the_only_boss_they_start() -> None:
    known = ["Special Operations Leader Linx", "Drakan Battalion Weapon Guruta", "Sharp Shylak"]
    assert wb.match_name("Special Operations Lead...", known) == known[0]
    assert wb.match_name("Drakan Battalion Weapo…", known) == known[1]
    assert wb.match_name("sharp shylak", known) == known[2]
    assert wb.match_name("Sharp", known) is None  # not cut short, so not a prefix match
    assert wb.match_name("Nobody...", known) is None


def test_a_full_reading_rewrites_every_boss(doc: dict[str, Any]) -> None:
    report = wb.apply_reading(doc, wb.parse_reading(READING), READ_AT)
    assert doc["readAt"] == "2026-10-06T09:12:00Z"
    assert len(report) == 24
    w = parse_world_bosses(doc)
    aed = next(b for b in w.bosses if b.id == "black-warrior-aed")
    assert aed.spawns_at == READ_AT + timedelta(seconds=13)
    assert all("spawnsAt" not in b for b in doc["bosses"])


def test_a_boss_left_out_keeps_its_projected_spawn(doc: dict[str, Any]) -> None:
    before = parse_world_bosses(copy.deepcopy(doc))
    only_two = "Melted Danar\nTime Left 10min\nSharp Shylak\nTime Left 4h\n"
    report = wb.apply_reading(doc, wb.parse_reading(only_two), READ_AT)
    lagta = next(b for b in doc["bosses"] if b["id"] == "high-commander-lagta")
    assert "timeLeft" not in lagta and lagta["spawnsAt"].endswith("Z")
    after = parse_world_bosses(doc)
    lagta_after = next(b for b in after.bosses if b.id == "high-commander-lagta")
    lagta_before = next(b for b in before.bosses if b.id == "high-commander-lagta")
    # the reading was a day later: the projection moved on by whole cycles, to the second
    assert lagta_after.spawns_at > READ_AT - timedelta(minutes=3)
    assert (lagta_after.spawns_at - lagta_before.spawns_at).total_seconds() % (12 * 3600 + 90) == 0
    assert sum("not in the reading" in line for line in report) == 22


def test_a_time_left_longer_than_the_cycle_is_reported(doc: dict[str, Any]) -> None:
    report = wb.apply_reading(doc, wb.parse_reading("Melted Danar\nTime Left 45min\n"), READ_AT)
    assert "cycle in the file is wrong" in report[0]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "no 'Time Left'"),
        ("Time Left 3min\n", "no boss name"),
        ("Somebody Else\nTime Left 3min\n", "not a boss"),
        ("Melted Danar\nTime Left soon\n", "not a time"),
    ],
)
def test_a_bad_reading_is_refused(doc: dict[str, Any], text: str, message: str) -> None:
    with pytest.raises(wb.ReadingError, match=message):
        wb.apply_reading(doc, wb.parse_reading(text), READ_AT)


def test_the_command_writes_the_file_and_refuses_without_touching_it(tmp_path: Path) -> None:
    target = tmp_path / "world-bosses.json"
    target.write_bytes((REPO / "assets" / "timers" / "world-bosses.json").read_bytes())
    reading = tmp_path / "reading.txt"
    reading.write_text(READING, encoding="utf-8")
    args = [str(reading), "--file", str(target), "--read-at", "2026-10-06T09:12:00Z"]
    assert wb.main(args) == 0
    assert json.loads(target.read_text("utf-8"))["readAt"] == "2026-10-06T09:12:00Z"

    written = target.read_bytes()
    reading.write_text("Nobody\nTime Left 1min\n", encoding="utf-8")
    assert wb.main(args) == 1
    assert target.read_bytes() == written
