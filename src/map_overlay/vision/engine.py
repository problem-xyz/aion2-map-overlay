"""The engine thread: capture -> track -> overlay matrix.

Runs off the GUI thread so that neither the panel nor the overlay can be stalled by a slow
frame. Full re-detection happens beside it, in the Detector thread, and only corrects the
binding that optical flow carries between detections.

The loop is written as small steps over one _LoopState rather than a single long function,
because the interesting part is the order the steps run in, and that was impossible to see
when it was 130 lines of interleaved bookkeeping.
"""

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from map_overlay.core.constants import (
    DETECTOR_JOIN_S,
    FRAME_CHANGE_PROBE_STRIDE,
    PLAYER_EMIT_HZ,
    PREVIEW_INTERVAL_S,
    STATS_INTERVAL_S,
)
from map_overlay.core.settings import Settings
from map_overlay.vision.capture import Capture
from map_overlay.vision.detector import DetectJob, Detector
from map_overlay.vision.features import CancelledError
from map_overlay.vision.flow import FlowTracker
from map_overlay.vision.preview import render_preview
from map_overlay.vision.tracker import Tracker, TrackerBuildParams, TrackerParams

log = logging.getLogger(__name__)

# Detection failures are transient far more often than not, so the loop absorbs them. These
# decide when "transient" stops being a fair description.
REBUILD_AFTER_FAILURES = 3
GIVE_UP_AFTER_FAILURES = 8
FAILURE_NOTICE_INTERVAL = 5.0


class VisionError(RuntimeError):
    """A failure the user has to act on: no reference, or one nothing can be matched against."""

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


@dataclass
class _LoopState:
    """Everything the loop carries from one frame to the next."""

    current: Any = None  # reference -> region: the placement the player sees
    emitted: Any = None  # what the overlay was last told
    drift_since_submit: Any = field(default_factory=lambda: np.eye(3))  # drift since the sent frame
    flow_valid: bool = False  # whether drift_since_submit can be trusted
    misses: int = 0  # consecutive failed detections
    found: bool = False
    anchored: bool = False
    info: dict = field(default_factory=dict)
    prev_small: Any = None
    player: Any = None  # last player position sent, in reference pixels
    last_stats: float = 0.0
    last_preview: float = 0.0
    last_submit: float = 0.0
    last_player: float = 0.0
    last_failure_notice: float = 0.0
    detect_failures: int = 0  # consecutive detector exceptions
    frame_times: list = field(default_factory=list)
    detect_ms: Any = None


class Engine(QThread):
    """The capture -> track -> transform loop, on a thread of its own.

    `configure`, `set_preview`, `start` and `request_stop` are the GUI-thread API, and they only
    leave a note under the lock for the loop to pick up on its next pass. Everything else --
    capture, tracker, detector, flow and `_LoopState` -- is created in `run` and belongs to the
    engine thread; no widget is ever touched from here. Workers downstream get immutable
    snapshots (a settings copy per pass, a frozen `DetectJob` per detection) rather than state
    the loop keeps editing.

    The signals are the only way out, and Qt delivers them to the GUI thread as queued calls.
    `failed` and `warned` carry either a dotted `vision.*` code or a raw exception string; the
    bridge is what turns the second kind into a code the UI can translate.

    The loop is a hot path: it drops frames whose subsampled probe is identical to the previous
    one, copies a frame only when handing it to the detector, and reports its timings through
    the `statsChanged` payload instead of printing them.
    """

    transformChanged = Signal(object)  # 3x3 ndarray (reference -> region), or None
    playerMoved = Signal(float, float)  # player position, in reference pixels
    statsChanged = Signal(dict)
    previewReady = Signal(str)  # JPEG, base64
    failed = Signal(str)
    warned = Signal(str)  # non-fatal: the overlay keeps going
    started_ok = Signal(str)  # capture backend name

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._settings = asdict(Settings())
        self._region = None
        self._screen_size = None
        self._reference = None
        self._gen = 0  # bumped by any configuration change
        self._stop = threading.Event()
        self._preview = False

        # Owned by run(); only ever touched from the engine thread. run() makes the detector
        # and the flow tracker before any loop step, so they are declared here, not set.
        self._capture: Capture | None = None
        self._tracker: Tracker | None = None
        self._detector: Detector
        self._flow: FlowTracker
        self._state = _LoopState()

    # ------------------------------------------------------------------ configuration (GUI thread)
    def configure(self, settings=None, region=None, reference=None, screen_size=None) -> None:
        with self._lock:
            if settings:
                self._settings.update(settings)
            if region is not None:
                self._region = dict(region)
            if screen_size is not None:
                self._screen_size = tuple(screen_size)
            if reference is not None:
                self._reference = reference
            self._gen += 1

    def set_preview(self, enabled) -> None:
        with self._lock:
            self._preview = bool(enabled)

    def request_stop(self) -> None:
        self._stop.set()

    # Returns whether it launched; QThread.start returns nothing.
    def start(self, priority=QThread.Priority.InheritPriority) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Clear the stop flag here, not in run().

        Clearing it inside run() loses a stop requested before the thread was scheduled, and
        the engine then runs on with nobody expecting it to.
        """
        if self.isRunning():
            return False
        self._stop.clear()
        super().start(priority)
        return True

    def _snapshot(self):
        with self._lock:
            region = dict(self._region) if self._region else None
            return dict(self._settings), region, self._reference, self._gen

    # ------------------------------------------------------------------ smoothing
    @staticmethod
    def _smooth(prev, cur, alpha):
        if prev is None or cur is None or alpha <= 0:
            return cur
        # a real jump (panned or zoomed) is followed immediately, not smeared
        s_prev = np.hypot(prev[0, 0], prev[1, 0])
        s_cur = np.hypot(cur[0, 0], cur[1, 0])
        dt = np.hypot(cur[0, 2] - prev[0, 2], cur[1, 2] - prev[1, 2])
        if dt > 40 or abs(s_cur / max(s_prev, 1e-6) - 1) > 0.10:
            return cur
        return alpha * prev + (1 - alpha) * cur

    # ------------------------------------------------------------------ player position
    @staticmethod
    def _anchor(region, settings):
        """Where in the captured region the player is. Fractions, so a new region still works."""
        return (
            region["width"] * float(settings["player_anchor_x"]),
            region["height"] * float(settings["player_anchor_y"]),
        )

    @staticmethod
    def _unproject(m, point):
        """Region point -> reference pixels. None if the matrix is singular."""
        try:
            inv = np.linalg.inv(m)
        except np.linalg.LinAlgError:
            return None
        p = inv @ np.array([point[0], point[1], 1.0])
        if abs(p[2]) < 1e-9:
            return None
        return p[:2] / p[2]

    # ------------------------------------------------------------------ loop steps
    def _apply_config(self, settings, region, reference) -> None:
        if region is None or reference is None:
            raise VisionError("vision.no_region_or_route")
        # A stop that came before capture opened, or while it was opening (dxcam takes a few
        # hundred milliseconds), ends the run here: started_ok would announce one that is over.
        if self._stop.is_set():
            return
        st = self._state
        if self._capture is None or self._capture.region != region:
            if self._capture:
                self._capture.close()
            with self._lock:
                screen_size = self._screen_size
            self._capture = Capture(region, screen_size)
            if self._stop.is_set():
                return
            self.started_ok.emit(self._capture.backend)
            st.prev_small = None

        build = TrackerBuildParams.from_mapping(settings)
        if self._tracker is None or self._tracker.path != reference or self._tracker.build != build:
            self._build_tracker(reference, build)

        self._flow.max_points = max(40, int(settings["flow_points"]))
        self._flow.min_points = max(12, self._flow.max_points // 5)

    def _build_tracker(self, reference, build) -> None:
        try:
            # Feature detection over a large reference takes seconds; let it be abandoned so
            # that closing the app does not have to wait for it.
            self._tracker = Tracker(reference, build, should_stop=self._stop.is_set)
        except CancelledError:
            return
        except FileNotFoundError as e:
            raise VisionError("vision.reference_unreadable", path=reference) from e
        except ValueError as e:
            raise VisionError("vision.reference_too_plain", path=reference) from e
        self._detector.set_tracker(self._tracker)
        st = self._state
        st.current = None
        st.flow_valid = False
        self._flow.reset()

    def _grab(self):
        """A new, changed frame, or None when there is nothing to do this tick."""
        st = self._state
        # _apply_config opens the capture before the loop first grabs.
        frame = self._capture.grab()  # pyright: ignore[reportOptionalMemberAccess]
        if frame is None:  # dxcam: no new frame
            time.sleep(0.001)
            return None
        probe = frame[::FRAME_CHANGE_PROBE_STRIDE, ::FRAME_CHANGE_PROBE_STRIDE]
        if st.prev_small is not None and np.array_equal(probe, st.prev_small):
            time.sleep(0.001)  # same picture, nothing to compute
            return None
        st.prev_small = probe.copy()
        return frame

    def _track_flow(self, gray, use_flow) -> None:
        """Carry the map by its own movement: cheap, and with almost no lag."""
        st = self._state
        if not use_flow:
            self._flow.reset()
            st.flow_valid = False
            return
        shift = self._flow.step(gray)
        if shift is None:
            st.flow_valid = False
            return
        if st.current is not None:
            st.current = shift @ st.current
        st.drift_since_submit = shift @ st.drift_since_submit

    def _absorb_failure(self, failure, now) -> None:
        """A detection that raised. Treated as a miss; only repetition is fatal."""
        st = self._state
        st.detect_failures += 1
        st.misses += 1
        st.anchored = False
        log.error(
            "detection failed (%d in a row): %s\n%s",
            st.detect_failures,
            failure.message,
            failure.traceback,
        )

        if st.detect_failures >= GIVE_UP_AFTER_FAILURES:
            raise VisionError("vision.detector_broken", reason=failure.message)

        if now - st.last_failure_notice > FAILURE_NOTICE_INTERVAL:
            st.last_failure_notice = now
            self.warned.emit(failure.message)

        if st.detect_failures == REBUILD_AFTER_FAILURES and self._tracker is not None:
            log.warning("rebuilding the tracker after %d failures", st.detect_failures)
            self._build_tracker(self._tracker.path, self._tracker.build)
            self.warned.emit("vision.tracker_rebuilt")

    def _absorb_detection(self, settings, use_flow) -> None:
        st = self._state
        result = self._detector.take()
        if result is None:
            return
        m, info = result
        st.info = info
        st.detect_ms = info.get("detectMs", st.detect_ms)
        if m is not None:
            st.detect_failures = 0
            target = st.drift_since_submit @ m if (use_flow and st.flow_valid) else m
            st.current = self._smooth(st.current, target, settings["smoothing"])
            st.misses = 0
            st.anchored = st.found = True
            return
        st.misses += 1
        st.anchored = False
        if st.misses > settings["hold_frames"]:
            st.current = None
            st.found = False
            self._flow.reset()

    def _maybe_submit(self, frame, settings, use_flow, t0) -> None:
        """Ask for the next detection; less often while the binding is holding."""
        st = self._state
        interval = float(settings["detect_interval"]) if (use_flow and st.anchored) else 0.0
        if not (self._detector.idle and (t0 - st.last_submit) >= interval):
            return
        job = DetectJob(frame.copy(), TrackerParams.from_mapping(settings))
        if self._detector.submit(job):
            st.last_submit = t0
            st.drift_since_submit = np.eye(3)
            st.flow_valid = use_flow

    def _publish_transform(self) -> None:
        """Emit only on a real change: repainting a transparent window costs more than this."""
        st = self._state
        changed = (st.current is None) != (st.emitted is None) or (
            st.current is not None
            and st.emitted is not None
            and not np.array_equal(st.current, st.emitted)
        )
        if not changed:
            return
        st.emitted = None if st.current is None else st.current.copy()
        self.transformChanged.emit(None if st.emitted is None else st.emitted.copy())

    def _publish_player(self, now, anchor, settings) -> None:
        st = self._state
        if not (settings["auto_progress"] and st.current is not None):
            return
        if now - st.last_player <= 1 / PLAYER_EMIT_HZ:
            return
        point = self._unproject(st.current, anchor)
        if point is not None and (st.player is None or np.hypot(*(point - st.player)) > 1.0):
            st.player = point
            st.last_player = now
            self.playerMoved.emit(float(point[0]), float(point[1]))

    def _publish_stats(self, now, t0, use_flow) -> None:
        st = self._state
        if now - st.last_stats <= STATS_INTERVAL_S:
            return
        st.last_stats = now
        reproj = st.info.get("reproj")
        self.statsChanged.emit(
            {
                "found": st.found,
                "anchored": st.anchored,
                "fps": len(st.frame_times),
                "processMs": round((now - t0) * 1000, 1),
                "detectMs": st.detect_ms,
                "flowPoints": self._flow.points if use_flow else 0,
                "matches": st.info.get("matches", 0),
                "inliers": st.info.get("inliers", 0),
                "reprojError": None if reproj is None else round(reproj, 2),
                # Open since _apply_config, as in _grab.
                "backend": self._capture.backend,  # pyright: ignore[reportOptionalMemberAccess]
            }
        )

    def _publish_preview(self, now, frame, anchor, settings) -> None:
        st = self._state
        with self._lock:
            wanted = self._preview
        if not wanted or now - st.last_preview <= PREVIEW_INTERVAL_S:
            return
        st.last_preview = now
        # the crosshair is only meaningful while points are marked on arrival; otherwise noise
        mark = anchor if settings["auto_progress"] else None
        self.previewReady.emit(render_preview(frame, st.current, self._tracker, mark))

    @staticmethod
    def _throttle(t0, settings) -> None:
        """Upper frame-rate bound. Normally the game sets the pace, not this line."""
        spare = 1.0 / max(1, settings["fps"]) - (time.perf_counter() - t0)
        if spare > 0:
            time.sleep(spare)

    # ------------------------------------------------------------------ main loop
    def run(self) -> None:
        self._state = _LoopState()
        self._detector = Detector()
        self._detector.start()
        self._flow = FlowTracker()
        gen_seen = -1

        try:
            while not self._stop.is_set():
                settings, region, reference, gen = self._snapshot()
                if gen != gen_seen:
                    gen_seen = gen
                    self._apply_config(settings, region, reference)
                    # Stopped while configuring, or the tracker build was abandoned for it.
                    if self._stop.is_set() or self._tracker is None:
                        break

                now = time.perf_counter()
                failure = self._detector.error()
                if failure:
                    self._absorb_failure(failure, now)

                t0 = time.perf_counter()
                frame = self._grab()
                if frame is None:
                    continue

                use_flow = settings["tracking"] == "flow"
                self._track_flow(cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY), use_flow)
                self._absorb_detection(settings, use_flow)
                self._maybe_submit(frame, settings, use_flow, t0)
                self._publish_transform()

                now = time.perf_counter()
                anchor = self._anchor(region, settings)
                self._publish_player(now, anchor, settings)
                self._state.frame_times = [
                    t for t in [*self._state.frame_times, now] if now - t < 1.0
                ]
                self._publish_stats(now, t0, use_flow)
                self._publish_preview(now, frame, anchor, settings)
                self._throttle(t0, settings)
        except VisionError as e:
            log.error("engine stopped: %s %s", e.code, e.params)
            self.failed.emit(e.code)
        except Exception as e:
            log.exception("engine loop failed")
            self.failed.emit(str(e))
        finally:
            self._detector.stop()
            self._detector.join(DETECTOR_JOIN_S)
            if self._capture:
                self._capture.close()
                self._capture = None
            self._tracker = None
            self.transformChanged.emit(None)
