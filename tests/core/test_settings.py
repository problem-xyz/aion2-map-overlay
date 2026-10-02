"""Settings coercion, the schema handed to the UI, and the pre-v1 migration."""

import json
import logging
import math
from dataclasses import MISSING, fields
from pathlib import Path

import pytest

from map_overlay.core.settings import (
    SETTINGS_VERSION,
    STATE_VERSION,
    Settings,
    State,
    coerce,
    load,
    migrate_0_to_1,
    plaque_scale,
    settings_payload,
    settings_schema,
    state_payload,
)


def test_empty_input_gives_defaults() -> None:
    settings, reset = coerce({}, Settings)
    assert settings == Settings()
    assert reset == []


def test_a_string_where_a_number_belongs_does_not_crash() -> None:
    """In the file, "fps": "60" must cost a reset, not a start-up failure."""
    settings, reset = coerce({"fps": "60"}, Settings)
    assert settings.fps == Settings.fps
    assert reset == ["fps"]


def test_out_of_range_is_clamped_and_reported() -> None:
    settings, reset = coerce({"opacity": 5.0, "min_inliers": -3}, Settings)
    assert settings.opacity == 1.0
    assert settings.min_inliers == 8
    assert reset == ["min_inliers", "opacity"]


# Every ranged field, spelled out. Derived from the metadata alone, a field that lost its range
# would quietly drop out of the clamp tests below instead of failing them.
RANGED = {
    "opacity": (0.1, 1.0),
    "fps": (30, 240),
    "detect_scale": (0.25, 1.0),
    "min_inliers": (8, 60),
    "smoothing": (0.0, 0.9),
    "detect_interval": (0.1, 2.0),
    "flow_points": (40, 2000),
    "hold_frames": (0, 100),
    "player_anchor_x": (0.0, 1.0),
    "player_anchor_y": (0.0, 1.0),
    "arrive_radius": (8 / 4096, 32 / 4096),
    "ratio": (0.5, 0.95),
    "reproj_thr": (0.5, 20.0),
    "ref_features": (0, 1_000_000),
    "frame_features": (200, 20000),
    "steps_scale": (0.5, 1.5),
    "route_ahead": (1, 10),
    "route_past": (0, 10),
    "cube_radius": (0, 100),
    "editor_route_ahead": (1, 10),
    "editor_opacity": (0.1, 1.0),
}


def test_the_ranged_fields_are_exactly_the_ones_pinned_here() -> None:
    declared = {f.name: f.metadata["range"] for f in fields(Settings) if "range" in f.metadata}
    assert declared == RANGED


@pytest.mark.parametrize(("name", "bounds"), sorted(RANGED.items()))
def test_a_value_below_the_range_is_clamped_to_its_lower_end(
    name: str, bounds: tuple[float, float]
) -> None:
    lo, hi = bounds
    settings, reset = coerce({name: lo - (hi - lo)}, Settings)
    assert getattr(settings, name) == lo
    assert reset == [name]


@pytest.mark.parametrize(("name", "bounds"), sorted(RANGED.items()))
def test_a_value_above_the_range_is_clamped_to_its_upper_end(
    name: str, bounds: tuple[float, float]
) -> None:
    lo, hi = bounds
    settings, reset = coerce({name: hi + (hi - lo)}, Settings)
    assert getattr(settings, name) == hi
    assert reset == [name]


@pytest.mark.parametrize(("name", "bounds"), sorted(RANGED.items()))
def test_both_ends_of_a_range_are_accepted_as_they_are(
    name: str, bounds: tuple[float, float]
) -> None:
    """The range is inclusive: the slider's own end stops must not cost a "values reset" toast."""
    for end in bounds:
        settings, reset = coerce({name: end}, Settings)
        assert getattr(settings, name) == end
        assert reset == []


def test_a_clamped_integer_stays_an_integer() -> None:
    """A float from JSON for an int field is cast before the clamp, not after."""
    settings, _ = coerce({"fps": 999.7, "min_inliers": 12.9}, Settings)
    assert (settings.fps, settings.min_inliers) == (240, 12)
    assert isinstance(settings.fps, int)
    assert isinstance(settings.min_inliers, int)


# Both an int and a float field of each kind: int() and float() fail on different inputs.
SOME_RANGED = ["fps", "min_inliers", "ref_features", "opacity", "smoothing", "arrive_radius"]


# json.loads reads all three from a hand-edited file, and so does updateSettings.
@pytest.mark.parametrize("raw", [math.nan, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
@pytest.mark.parametrize("name", SOME_RANGED)
def test_nan_and_infinity_get_the_default(raw: float, name: str) -> None:
    """int(inf) raises and NaN passes a clamp, since it compares unequal to anything: either
    was a start-up crash, or a NaN written back to disk and sent to the panel."""
    settings, reset = coerce({name: raw}, Settings)
    assert getattr(settings, name) == getattr(Settings(), name)
    assert reset == [name]


@pytest.mark.parametrize("name", SOME_RANGED)
def test_an_integer_too_long_for_a_float_is_pulled_to_the_nearest_end(name: str) -> None:
    lo, hi = RANGED[name]
    for raw, end in ((10**400, hi), (-(10**400), lo)):
        settings, reset = coerce({name: raw}, Settings)
        assert getattr(settings, name) == end
        assert reset == [name]


def test_a_file_with_nan_and_infinity_loads_into_a_payload_json_parse_accepts(
    tmp_path: Path,
) -> None:
    """The coerced payload only. That the store writes it with allow_nan=False, and refuses to
    write a NaN that got past coercion, is pinned in tests/bridge/test_settings_store.py."""
    settings_path = tmp_path / "settings.json"
    state_path = tmp_path / "state.json"
    settings_path.write_text(
        '{"version": 1, "fps": Infinity, "opacity": NaN, "arrive_radius": -Infinity}',
        encoding="utf-8",
    )
    state_path.write_text(
        '{"version": 1, "region": {"left": NaN, "top": 0, "width": 800, "height": 600},'
        ' "steps_region": {"left": 0, "top": 0, "width": Infinity, "height": 160},'
        ' "progress": {"a": Infinity, "b": 3}}',
        encoding="utf-8",
    )

    result = load(settings_path, state_path)

    assert result.settings == Settings()
    assert (result.state.region, result.state.steps_region) == (None, None)
    assert result.state.progress == {"b": 3}
    assert result.reset_keys == ["arrive_radius", "fps", "opacity", "region", "steps_region"]
    # allow_nan=False is what JSON.parse in the panel holds us to
    json.dumps(settings_payload(result.settings), allow_nan=False)
    json.dumps(state_payload(result.state), allow_nan=False)


def test_a_region_too_large_for_a_window_rectangle_is_rejected() -> None:
    region = {"left": 0, "top": 0, "width": 2**40, "height": 600}
    state, reset = coerce({"region": region}, State)
    assert state.region is None
    assert reset == ["region"]


def test_the_log_tells_a_clamp_from_a_reset(caplog: pytest.LogCaptureFixture) -> None:
    """The notice lists both kinds together; the log is where a user can see which was which."""
    with caplog.at_level(logging.WARNING, logger="map_overlay.core.settings"):
        coerce({"opacity": 0.02, "fps": "60"}, Settings)
    lines = [r.getMessage() for r in caplog.records]
    assert "Settings: opacity 0.02 pulled into range: 0.1" in lines
    assert "Settings: reset to defaults: fps" in lines


# --------------------------------------------------------------------------- schema export


def test_the_schema_describes_every_settings_field_and_nothing_else() -> None:
    assert set(settings_schema()) == {f.name for f in fields(Settings)}


def test_the_schema_carries_each_fields_type_and_default() -> None:
    schema = settings_schema()
    for f in fields(Settings):
        entry = schema[f.name]
        default = f.default_factory() if f.default_factory is not MISSING else f.default
        assert entry["default"] == default, f.name
        names = {bool: "bool", int: "int", float: "float", str: "str", list: "list"}
        assert entry["type"] == names[type(default)], f.name


def test_a_list_of_ids_keeps_its_strings_once_each_and_drops_the_rest() -> None:
    settings, reset = coerce({"resources": ["odyle", "", 3, "ruby", "odyle"]}, Settings)

    assert settings.resources == ["odyle", "ruby"]
    assert reset == []
    settings, reset = coerce({"resources": "odyle"}, Settings)
    assert settings.resources == []
    assert reset == ["resources"]


def test_the_schema_ranges_are_the_metadata_coerce_enforces() -> None:
    """Copied from the field metadata, not restated: the panel offers what the file accepts."""
    schema = settings_schema()
    for f in fields(Settings):
        entry = schema[f.name]
        if "range" in f.metadata:
            assert (entry.get("min"), entry.get("max")) == f.metadata["range"], f.name
        else:
            assert "min" not in entry, f.name
            assert "max" not in entry, f.name
        if "choices" in f.metadata:
            assert entry.get("choices") == list(f.metadata["choices"]), f.name
        else:
            assert "choices" not in entry, f.name


def test_every_default_lies_inside_its_own_range_and_choices() -> None:
    """A default outside its range would be clamped on the first load and reported as a reset."""
    for name, entry in settings_schema().items():
        default = entry["default"]
        lo, hi = entry.get("min"), entry.get("max")
        if lo is not None and hi is not None:
            assert isinstance(default, (int, float)), name
            assert lo <= default <= hi, name
        allowed = entry.get("choices")
        if allowed is not None:
            assert default in allowed, name


def test_the_schema_survives_json_as_it_is_sent_to_the_ui() -> None:
    schema = settings_schema()
    assert json.loads(json.dumps(schema)) == schema


def test_invalid_choice_falls_back_to_default() -> None:
    settings, reset = coerce({"detector": "bogus"}, Settings)
    assert settings.detector == "sift"
    assert reset == ["detector"]


def test_ints_are_not_accepted_as_booleans() -> None:
    """1 from JSON is a number, not a ticked checkbox."""
    settings, reset = coerce({"capture_visible": 1}, Settings)
    assert settings.capture_visible is False
    assert "capture_visible" in reset


def test_seeded_routes_keep_only_distinct_ids() -> None:
    state, reset = coerce({"seeded_routes": ["a", 3, "", "b", "a"]}, State)
    assert state.seeded_routes == ["a", "b"]
    assert reset == []

    state, reset = coerce({"seeded_routes": "a"}, State)
    assert state.seeded_routes == []
    assert reset == ["seeded_routes"]


def test_unknown_keys_are_dropped_without_a_reset() -> None:
    settings, reset = coerce({"bogus": 1, "opacity": 0.5}, Settings)
    assert settings.opacity == 0.5
    assert reset == []
    assert not hasattr(settings, "bogus")


def test_language_defaults_to_auto_and_an_unknown_tag_falls_back() -> None:
    """The UI follows the OS language only while this still says "auto"."""
    settings, reset = coerce({}, Settings)
    assert settings.language == "auto"
    assert reset == []

    settings, reset = coerce({"language": "de"}, Settings)
    assert settings.language == "auto"
    assert reset == ["language"]


def test_a_malformed_region_is_rejected() -> None:
    state, reset = coerce({"region": {"left": 1, "top": 2}}, State)
    assert state.region is None
    assert reset == ["region"]

    state, reset = coerce({"region": {"left": 1, "top": 2, "width": 0, "height": 5}}, State)
    assert state.region is None


def test_a_valid_region_survives() -> None:
    region = {"left": 10, "top": 20, "width": 800, "height": 600}
    state, reset = coerce({"region": region}, State)
    assert state.region == region
    assert reset == []


def test_migration_splits_the_old_single_file() -> None:
    old = {
        "settings": {"opacity": 0.75, "fps": 100, "ref_features": 100000},
        "region": {"left": 1, "top": 2, "width": 3, "height": 4},
        "route": "Test_1",
        "capture_visible": True,
        "steps_pinned": False,
        "steps_size": "l",
        "progress": {"Test_1": 7},
    }

    settings, state = migrate_0_to_1(old)

    assert settings["opacity"] == 0.75
    # the three that used to sit at the top level are settings now
    assert (settings["capture_visible"], settings["steps_pinned"], settings["steps_size"]) == (
        True,
        False,
        "l",
    )
    assert state["route"] == "Test_1"
    assert state["progress"] == {"Test_1": 7}
    assert "settings" not in state


def test_migration_applies_the_two_shipped_default_fixes() -> None:
    settings, _ = migrate_0_to_1({"settings": {"ref_features": 4000, "fps": 15}})
    assert settings["ref_features"] == Settings.ref_features
    assert settings["fps"] == Settings.fps

    # an explicit "no limit" is a choice, not a stale default
    settings, _ = migrate_0_to_1({"settings": {"ref_features": 0}})
    assert settings["ref_features"] == 0


def test_load_migrates_a_pre_v1_file(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"settings": {"opacity": 0.5}, "steps_size": "s", "route": "r"}),
        encoding="utf-8",
    )

    result = load(settings_path, tmp_path / "state.json")

    assert result.migrated
    assert result.settings.opacity == 0.5
    assert result.settings.steps_size == "s"
    assert result.state.route == "r"


def test_load_migrates_the_file_from_the_code_review(tmp_path: Path) -> None:
    """A real pre-v1 settings.json, with no state.json beside it.

    fps 120 is the interesting value. The migration raises an fps below 30 because that default
    was wrong in a shipped version, so a higher number the user chose has to come through it
    untouched.
    """
    settings_path = tmp_path / "settings.json"
    state_path = tmp_path / "state.json"
    settings_path.write_text(
        json.dumps(
            {
                "settings": {"opacity": 0.9, "fps": 120, "detector": "sift"},
                "region": {"left": 0, "top": 0, "width": 1920, "height": 1080},
                "capture_visible": False,
                "steps_pinned": True,
                "steps_size": "m",
                "route": "Test_1",
                "progress": {"Test_1": 7},
            }
        ),
        encoding="utf-8",
    )

    result = load(settings_path, state_path)

    assert result.migrated
    # what would be written back carries the version the old file never had
    assert settings_payload(result.settings)["version"] == SETTINGS_VERSION
    assert result.settings.fps == 120
    assert result.settings.opacity == 0.9
    assert result.state.route == "Test_1"
    assert result.state.progress == {"Test_1": 7}
    assert result.state.region == {"left": 0, "top": 0, "width": 1920, "height": 1080}
    # a file this ordinary must migrate without a single value being rejected
    assert result.reset_keys == []
    assert result.corrupt_backup is None


def test_a_current_pair_of_files_loads_unchanged(tmp_path: Path) -> None:
    """Nothing repaired means settings_store leaves both files alone and says nothing."""
    settings_path = tmp_path / "settings.json"
    state_path = tmp_path / "state.json"
    settings_path.write_text(
        json.dumps(settings_payload(Settings(fps=90, language="ru"))), encoding="utf-8"
    )
    state_path.write_text(
        json.dumps(state_payload(State(route="Test_1", progress={"Test_1": 3}))), encoding="utf-8"
    )

    result = load(settings_path, state_path)

    assert result.settings == Settings(fps=90, language="ru")
    assert result.state == State(route="Test_1", progress={"Test_1": 3})
    assert (result.migrated, result.reset_keys, result.corrupt_backup) == (False, [], None)


def test_a_first_run_with_no_files_reports_nothing(tmp_path: Path) -> None:
    result = load(tmp_path / "settings.json", tmp_path / "state.json")

    assert result.settings == Settings()
    assert result.state == State()
    # an absent file is not a repair: corrupt_backup is only for one that could not be parsed
    assert (result.migrated, result.reset_keys, result.corrupt_backup) == (False, [], None)


def test_reset_keys_gathers_both_files_into_one_sorted_list(tmp_path: Path) -> None:
    """backend.py joins this into a single settings.values_reset toast, not one per field."""
    settings_path = tmp_path / "settings.json"
    state_path = tmp_path / "state.json"
    settings_path.write_text(
        json.dumps({"version": 1, "fps": "60", "opacity": 5.0}), encoding="utf-8"
    )
    state_path.write_text(
        json.dumps({"version": 1, "region": {"left": 1}, "progress": []}), encoding="utf-8"
    )

    result = load(settings_path, state_path)

    assert result.reset_keys == ["fps", "opacity", "progress", "region"]
    assert not result.migrated
    assert result.corrupt_backup is None


def test_load_moves_a_corrupt_file_aside_and_uses_defaults(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"opacity": 0.5, "fps"', encoding="utf-8")

    result = load(settings_path, tmp_path / "state.json")

    assert result.settings == Settings()
    assert result.corrupt_backup is not None
    assert result.corrupt_backup.exists()
    # the unreadable bytes are kept, not deleted, and the original name is free again
    assert result.corrupt_backup.name.startswith("settings.json.broken-")
    assert result.corrupt_backup.read_text(encoding="utf-8") == '{"opacity": 0.5, "fps"'
    assert not settings_path.exists()
    # corrupt_backup is the whole notice here: nothing was validated, so reset_keys stays empty
    # and the user is not told twice about one broken file
    assert result.reset_keys == []
    assert not result.migrated


def test_version_is_written_and_not_treated_as_a_field() -> None:
    payload = settings_payload(Settings())
    assert payload["version"] == SETTINGS_VERSION

    settings, reset = coerce(payload, Settings)
    assert settings == Settings()
    assert reset == []
    assert STATE_VERSION == 1


@pytest.mark.parametrize(("size", "scale"), [("s", 0.5), ("m", 0.5), ("l", 0.86)])
def test_a_file_from_before_the_scale_keeps_the_plaque_its_size(
    tmp_path: Path, size: str, scale: float
) -> None:
    """The plaque's three steps became a slider: a user who had chosen L must not find it M."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "steps_size": size}), encoding="utf-8")
    result = load(path, tmp_path / "state.json")
    assert result.settings.steps_scale == scale
    assert (result.migrated, result.reset_keys) == (False, [])


@pytest.mark.parametrize("stored", [0.008, 0.03])
def test_a_radius_from_the_old_wider_range_comes_down_to_the_top_unannounced(
    tmp_path: Path, stored: float
) -> None:
    """0.008 was the default and most files carry it: its user must not be warned on start."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "arrive_radius": stored}), encoding="utf-8")
    result = load(path, tmp_path / "state.json")
    assert result.settings.arrive_radius == 32 / 4096
    assert result.reset_keys == []


def test_a_radius_inside_the_range_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "arrive_radius": 0.002}), encoding="utf-8")
    assert load(path, tmp_path / "state.json").settings.arrive_radius == 0.002


def test_a_scale_the_file_already_has_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"version": 1, "steps_size": "l", "steps_scale": 0.9}), encoding="utf-8"
    )
    assert load(path, tmp_path / "state.json").settings.steps_scale == 0.9


@pytest.mark.parametrize(
    ("setting", "factor"),
    [(0.5, 1.0), (0.75, 1.175), (1.0, 1.35), (1.25, 1.475), (1.5, 1.6), (0.2, 1.0), (2.0, 1.6)],
)
def test_the_plaque_is_drawn_at_the_sizes_the_owner_set(setting: float, factor: float) -> None:
    """50% on the slider is the old full size, 100% is 135% of it, 150% is 160%."""
    assert plaque_scale(setting) == factor


def test_route_order_keeps_each_id_once_and_drops_what_is_not_one() -> None:
    state, reset = coerce({"route_order": ["b", "", 3, "a", "b", None]}, State)
    assert state.route_order == ["b", "a"]
    assert reset == []


def test_a_route_order_that_is_not_a_list_is_reset() -> None:
    state, reset = coerce({"route_order": "a,b"}, State)
    assert state.route_order == []
    assert reset == ["route_order"]
