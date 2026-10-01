"""The engine loop's bookkeeping, driven without a screen capture.

Nothing here grabs a frame, builds a Tracker or starts the QThread. The steps under test --
`_absorb_failure`, `_absorb_detection` and `_publish_transform` -- are pure bookkeeping over one
`_LoopState`, and every collaborator they touch (detector, flow, tracker, the tracker rebuild) is
replaced by a stub that records what it was asked for. `_absorb_failure` takes `now` as an
argument, so the notice throttle is tested by passing timestamps rather than by sleeping.

The two thresholds are separate numbers, easily run together into one: three consecutive raised
detections rebuild the tracker, eight stop the engine. The tests take both from the constants in
`map_overlay.vision.engine`.
"""

from dataclasses import asdict
from typing import Any

import numpy as np
import pytest

from map_overlay.core.settings import Settings
from map_overlay.vision.detector import DetectFailure, Detector
from map_overlay.vision.engine import (
    FAILURE_NOTICE_INTERVAL,
    GIVE_UP_AFTER_FAILURES,
    REBUILD_AFTER_FAILURES,
    Engine,
    VisionError,
    _LoopState,
)
from map_overlay.vision.flow import FlowTracker
from map_overlay.vision.tracker import Tracker, TrackerBuildParams

# Filed separately; do not fix it from here. Detector.run publishes *both* an error and a
# (None, info) result for a single detection that raised, and the loop reads them in the same
# pass, one step apart.
DOUBLE_COUNT_DEFECT = (
    "one raised detection increments misses twice: Engine._absorb_failure does `st.misses += 1`, "
    "then Engine._absorb_detection takes the (None, info) result Detector.run publishes beside "
    "the same error and does `st.misses += 1` again -- so hold_frames is effectively halved "
    "whenever the detector is raising"
)
INFO_BLANKED_DEFECT = (
    "the same double delivery blanks the stats: Engine._absorb_detection does `st.info = info` "
    "with the near-empty info Detector.run attaches to a raised detection, so matches/inliers "
    "from the last real match are lost from the next _publish_stats payload"
)


class FakeDetector(Detector):
    """Hands back the results a test queued, the way `Detector.take` does: once each.

    A Detector so that the engine's attribute accepts it; its thread is never started.
    """

    def __init__(self, results: list[tuple[Any, dict[str, Any]]] | None = None) -> None:
        super().__init__()
        self.results: list[tuple[Any, dict[str, Any]]] = list(results or [])

    def take(self) -> tuple[Any, dict[str, Any]] | None:
        return self.results.pop(0) if self.results else None


class FakeFlow(FlowTracker):
    """Counts the resets the loop asks for; the real optical flow needs frames."""

    def __init__(self) -> None:
        super().__init__()
        self.resets = 0

    def reset(self) -> None:
        self.resets += 1


class FakeTracker(Tracker):
    """Only the two fields `_absorb_failure` reads back when it asks for a rebuild.

    A Tracker in type only. Its own constructor is skipped on purpose: that one needs a
    reference image and seconds of feature detection.
    """

    def __init__(self) -> None:
        self.path = "reference.png"
        self.coords_size = None
        self.build = TrackerBuildParams.from_mapping(asdict(Settings()))


class RebuildRecorder:
    """Stands in for `Engine._build_tracker`.

    A rebuild is a request here, not a real Tracker: building one needs a reference image and
    seconds of feature detection, and what the loop decides is *when* to ask.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, path: Any, build: Any, *, size: Any = None) -> None:
        self.calls.append((path, build))


@pytest.fixture
def engine() -> Engine:
    """An Engine with every collaborator stubbed. The thread is never started."""
    made = Engine()
    made._state = _LoopState()
    made._detector = FakeDetector()
    made._flow = FakeFlow()
    made._tracker = FakeTracker()
    return made


def loop_settings(**overrides: Any) -> dict[str, Any]:
    """The shipped defaults, as `_snapshot` would hand them to a loop step."""
    settings = asdict(Settings())
    settings.update(overrides)
    return settings


def translation(dx: float, dy: float) -> np.ndarray:
    """A 3x3 reference -> region matrix that only shifts."""
    m = np.eye(3)
    m[0, 2] = dx
    m[1, 2] = dy
    return m


def detect_failure(message: str = "cv2 raised on this frame") -> DetectFailure:
    return DetectFailure(message, "Traceback (most recent call last):\n  ...\n")


def test_the_two_failure_thresholds_are_separate_numbers() -> None:
    # Pinned because they are easily run together into "three failures, then failed": a rebuild
    # at three, giving up at eight, and a 5 s floor between user notices.
    assert REBUILD_AFTER_FAILURES == 3
    assert GIVE_UP_AFTER_FAILURES == 8
    assert FAILURE_NOTICE_INTERVAL == 5.0


def test_consecutive_failed_detections_are_counted(engine: Engine) -> None:
    engine._absorb_failure(detect_failure(), 0.0)
    engine._absorb_failure(detect_failure(), 1.0)

    assert engine._state.detect_failures == 2
    assert engine._state.anchored is False


def test_a_successful_detection_resets_the_failure_count(engine: Engine) -> None:
    engine._absorb_failure(detect_failure(), 0.0)
    engine._absorb_failure(detect_failure(), 1.0)
    assert engine._state.detect_failures == 2

    engine._detector = FakeDetector([(translation(1.0, 1.0), {"matches": 40, "inliers": 28})])
    engine._absorb_detection(loop_settings(), use_flow=False)

    assert engine._state.detect_failures == 0


def test_the_tracker_is_rebuilt_at_exactly_three_failures(engine: Engine) -> None:
    tracker = FakeTracker()
    engine._tracker = tracker
    rebuilds = RebuildRecorder()
    engine._build_tracker = rebuilds
    warned: list[str] = []
    engine.warned.connect(warned.append)

    engine._absorb_failure(detect_failure(), 0.0)
    engine._absorb_failure(detect_failure(), 1.0)
    assert rebuilds.calls == []  # two in a row is still "transient"

    engine._absorb_failure(detect_failure(), 2.0)  # REBUILD_AFTER_FAILURES
    assert rebuilds.calls == [(tracker.path, tracker.build)]
    assert warned.count("vision.tracker_rebuilt") == 1

    engine._absorb_failure(detect_failure(), 3.0)
    # the loop compares with `==`, so a fourth failure does not rebuild again
    assert len(rebuilds.calls) == 1
    assert warned.count("vision.tracker_rebuilt") == 1


def test_a_missing_tracker_is_not_rebuilt(engine: Engine) -> None:
    """Failures before the first successful build must not reach `_build_tracker`."""
    engine._tracker = None
    engine._build_tracker = RebuildRecorder()

    for i in range(REBUILD_AFTER_FAILURES):
        engine._absorb_failure(detect_failure(), float(i))

    assert engine._build_tracker.calls == []


def test_the_detector_is_declared_broken_at_exactly_eight_failures(engine: Engine) -> None:
    engine._build_tracker = RebuildRecorder()

    # GIVE_UP_AFTER_FAILURES is 8, so seven in a row are still absorbed
    for i in range(7):
        engine._absorb_failure(detect_failure(), float(i))
    assert engine._state.detect_failures == 7

    with pytest.raises(VisionError) as caught:
        engine._absorb_failure(detect_failure("tracker.find: bad frame"), 7.0)

    assert caught.value.code == "vision.detector_broken"
    assert caught.value.params["reason"] == "tracker.find: bad frame"


def test_repeated_failures_inside_the_notice_interval_warn_once(engine: Engine) -> None:
    # No tracker, so the rebuild at three failures cannot emit a warning of its own: every
    # warning seen here comes from the notice throttle.
    engine._tracker = None
    warned: list[str] = []
    engine.warned.connect(warned.append)

    engine._absorb_failure(detect_failure("first"), 100.0)
    engine._absorb_failure(detect_failure("second"), 101.0)
    engine._absorb_failure(detect_failure("third"), 104.9)
    assert warned == ["first"]  # FAILURE_NOTICE_INTERVAL is 5 s

    engine._absorb_failure(detect_failure("fourth"), 106.0)
    assert warned == ["first", "fourth"]
    assert engine._state.last_failure_notice == 106.0


def test_a_successful_detection_anchors_and_smooths_towards_the_match(engine: Engine) -> None:
    st = engine._state
    st.current = translation(10.0, 10.0)
    st.misses = 4
    st.found = False
    match = translation(20.0, 10.0)  # 10 px away: under the 40 px jump cut-off in _smooth
    engine._detector = FakeDetector([(match, {"matches": 48, "inliers": 31, "detectMs": 12.5})])

    engine._absorb_detection(loop_settings(smoothing=0.5), use_flow=False)

    assert st.misses == 0
    assert st.anchored is True
    assert st.found is True
    # smoothing 0.5 is the shipped default: half the previous placement, half the new one
    assert st.current[0, 2] == pytest.approx(15.0)
    assert st.current[1, 2] == pytest.approx(10.0)
    assert st.info["inliers"] == 31
    assert st.detect_ms == 12.5


def test_a_detection_is_carried_forward_by_the_drift_since_it_was_submitted(
    engine: Engine,
) -> None:
    st = engine._state
    st.flow_valid = True
    st.drift_since_submit = translation(4.0, -2.0)
    engine._detector = FakeDetector([(translation(20.0, 10.0), {})])

    # smoothing 0 keeps the arithmetic visible: _smooth returns the target untouched
    engine._absorb_detection(loop_settings(smoothing=0.0), use_flow=True)

    assert st.current[0, 2] == pytest.approx(24.0)
    assert st.current[1, 2] == pytest.approx(8.0)


def test_the_drift_is_ignored_when_the_flow_is_not_trusted(engine: Engine) -> None:
    st = engine._state
    st.flow_valid = False
    st.drift_since_submit = translation(4.0, -2.0)
    engine._detector = FakeDetector([(translation(20.0, 10.0), {})])

    engine._absorb_detection(loop_settings(smoothing=0.0), use_flow=True)

    assert st.current[0, 2] == pytest.approx(20.0)
    assert st.current[1, 2] == pytest.approx(10.0)


def test_the_binding_survives_hold_frames_misses_and_is_cleared_by_the_next_one(
    engine: Engine,
) -> None:
    st = engine._state
    st.current = translation(5.0, 5.0)
    st.found = True
    settings = loop_settings(hold_frames=3)
    engine._detector = FakeDetector([(None, {}) for _ in range(4)])
    flow = FakeFlow()
    engine._flow = flow

    for _ in range(3):
        engine._absorb_detection(settings, use_flow=False)

    assert st.misses == 3
    assert st.anchored is False
    assert st.found is True  # still holding: the loop clears only *past* hold_frames
    assert st.current is not None
    assert flow.resets == 0

    engine._absorb_detection(settings, use_flow=False)

    assert st.misses == 4
    assert st.current is None
    assert st.found is False
    assert flow.resets == 1


def map_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("map ")]


def test_finding_and_losing_the_map_is_logged_once_each_with_the_numbers(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    """A user's log is the only way to see why the route disappeared on their machine."""
    caplog.set_level("INFO", logger="map_overlay.vision.engine")
    hit = {"mode": "local", "keypoints": 900, "matches": 48, "inliers": 31, "reproj": 0.84}
    miss = {"mode": "global", "keypoints": 3, "matches": 0, "inliers": 0, "reproj": None}
    settings = loop_settings(hold_frames=1, min_inliers=20)
    engine._detector = FakeDetector(
        [(translation(1.0, 1.0), hit), (translation(1.0, 1.0), hit), (None, miss), (None, miss)]
    )

    for _ in range(4):
        engine._absorb_detection(settings, use_flow=False)

    found, lost = map_lines(caplog)
    assert found.startswith("map found after ")
    assert "local search, 900 keypoints, 48 matches, 31 inliers, reprojection 0.84 px" in found
    assert lost.startswith("map lost after ")
    assert "2 misses in a row" in lost
    assert "global search, 3 keypoints, 0 matches, 0 inliers (needs 20 inliers)" in lost
    assert engine._state.found is False


def test_a_miss_after_a_raised_detection_says_so(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="map_overlay.vision.engine")
    engine._state.found = True
    engine._detector = FakeDetector([(None, {"detectMs": 9.0})])

    engine._absorb_detection(loop_settings(hold_frames=0), use_flow=False)

    assert "the last one raised" in map_lines(caplog)[0]


def test_a_tracker_rebuild_loses_the_map_so_the_next_match_is_logged_as_found(
    engine: Engine, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level("INFO", logger="map_overlay.vision.engine")
    monkeypatch.setattr("map_overlay.vision.engine.Tracker", lambda *_a, **_k: FakeTracker())
    engine._state.found = True
    engine._state.current = translation(1.0, 1.0)

    engine._build_tracker("reference.png", FakeTracker().build)

    assert engine._state.found is False
    assert engine._state.current is None
    assert map_lines(caplog)[0].endswith("the tracker was rebuilt")


def test_the_transform_is_emitted_once_per_real_change(engine: Engine) -> None:
    sent: list[Any] = []
    engine.transformChanged.connect(sent.append)
    engine._state.current = translation(3.0, 4.0)

    engine._publish_transform()
    engine._publish_transform()  # nothing moved since

    assert len(sent) == 1
    assert sent[0][0, 2] == 3.0


def test_clearing_the_binding_emits_none(engine: Engine) -> None:
    sent: list[Any] = []
    engine.transformChanged.connect(sent.append)
    engine._state.current = translation(3.0, 4.0)
    engine._publish_transform()

    engine._state.current = None
    engine._publish_transform()

    assert len(sent) == 2
    assert sent[1] is None


def test_the_emitted_matrix_is_a_copy_the_loop_cannot_edit(engine: Engine) -> None:
    """The overlay reads the matrix on the GUI thread; it must not alias the loop's own."""
    sent: list[Any] = []
    engine.transformChanged.connect(sent.append)
    engine._state.current = translation(3.0, 4.0)
    engine._publish_transform()

    engine._state.current[0, 2] = 99.0

    assert sent[0][0, 2] == 3.0


@pytest.mark.xfail(strict=True, reason=DOUBLE_COUNT_DEFECT)
def test_one_failed_detection_advances_misses_by_one(engine: Engine) -> None:
    # What the loop sees in a single pass over a detection that raised: Detector.run stores the
    # error *and* a (None, info) result, and run() calls _absorb_failure then _absorb_detection.
    engine._detector = FakeDetector([(None, {"detectMs": 9.0})])

    engine._absorb_failure(detect_failure(), 0.0)
    engine._absorb_detection(loop_settings(), use_flow=False)

    assert engine._state.misses == 1


@pytest.mark.xfail(strict=True, reason=INFO_BLANKED_DEFECT)
def test_a_failed_detection_keeps_the_last_match_counts_for_the_stats(engine: Engine) -> None:
    st = engine._state
    st.info = {"matches": 48, "inliers": 31, "reproj": 0.8}  # from the last real match
    engine._detector = FakeDetector([(None, {"detectMs": 9.0})])

    engine._absorb_failure(detect_failure(), 0.0)
    engine._absorb_detection(loop_settings(), use_flow=False)

    # _publish_stats reads st.info; a detection that raised should not blank it
    assert st.info.get("matches") == 48


# --------------------------------------------------------------------------- a stop while starting


class FakeCapture:
    """Opens nothing. `opening` runs inside the constructor, where dxcam spends its time."""

    opening: Any = None

    def __init__(self, region: dict[str, int], screen_size: Any = None) -> None:
        self.region = dict(region)
        self.backend = "mss"
        self.closed = False
        if FakeCapture.opening is not None:
            FakeCapture.opening()

    def close(self) -> None:
        self.closed = True


REGION = {"left": 0, "top": 0, "width": 800, "height": 600}


@pytest.fixture
def fresh(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> tuple[Engine, list[str]]:
    """An engine that has not opened capture yet, with started_ok recorded."""
    monkeypatch.setattr("map_overlay.vision.engine.Capture", FakeCapture)
    monkeypatch.setattr(FakeCapture, "opening", None)
    engine._capture = None
    started: list[str] = []
    engine.started_ok.connect(started.append)
    return engine, started


def test_a_stop_before_the_first_configuration_opens_no_capture(
    fresh: tuple[Engine, list[str]],
) -> None:
    engine, started = fresh
    engine.request_stop()

    engine._apply_config(loop_settings(), REGION, "reference.png")

    assert engine._capture is None
    assert started == []


def test_a_stop_while_capture_opens_is_not_announced_as_a_start(
    fresh: tuple[Engine, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, started = fresh
    monkeypatch.setattr(FakeCapture, "opening", engine.request_stop)

    engine._apply_config(loop_settings(), REGION, "reference.png")

    # run() closes it on the way out, as it does any capture it holds
    assert isinstance(engine._capture, FakeCapture)
    assert started == []
