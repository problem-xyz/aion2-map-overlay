"""EngineController's phase machine, driven by a stub engine that captures nothing.

Every transition is a reply to the thread: STARTING is the controller's own, RUNNING arrives with
`started_ok`, IDLE with `finished`. So the stub is a real QThread whose `run` parks on an Event --
`isRunning` and `wait` then behave exactly as Qt's do, which is what `shutdown` is measured
against -- while the two reporting signals are emitted by the test, from the GUI thread, where
they arrive as direct calls. That is what makes the ordered sequence assertable without sleeping.

The sequence is the subject, not the final value. A controller with the STOPPING window removed
still ends every scenario below on the right phase; what it loses is the window in which a Start
must be parked rather than run, and only the whole ordered `phaseChanged` list shows that.
"""

import logging
import threading
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.engine_controller import EngineController, Phase

LOGGER = "map_overlay.bridge.engine_controller"

# Generous on purpose: a loaded CI box must not fail a join by being slow, and a stub thread that
# is genuinely stuck fails on the assertion after it rather than by hanging the run.
JOIN_MS = 5000

# Self-defence. A test that fails before the fixture releases the park must not leave a thread
# behind for the rest of the session.
PARK_CEILING_S = 30.0

# Short enough to keep the timeout test instant, long enough not to be a flake on a busy box.
NO_FINISH_MS = 200

SETTINGS: dict[str, Any] = {"fps": 60, "tracking": "flow"}
REGION: dict[str, int] = {"left": 0, "top": 0, "width": 800, "height": 600}
SCREEN: tuple[int, int] = (1920, 1080)


class StubEngine(QThread):
    """Stands in for Engine: the GUI-thread API the controller calls, and the signals it binds.

    `run` parks instead of capturing, so the thread is alive and joinable on demand. `start`
    joins any previous run before launching the next, which is how a replayed launch is kept
    deterministic -- the real Engine refuses to start while its old thread is winding down, and
    that race has nothing to do with what these tests measure.
    """

    # The Engine's own names, which the controller binds by; N815 is waived in src for the same
    # reason and the per-file ignore does not reach tests.
    transformChanged = Signal(object)  # noqa: N815
    playerMoved = Signal(float, float)  # noqa: N815
    statsChanged = Signal(dict)  # noqa: N815
    previewReady = Signal(str)  # noqa: N815
    failed = Signal(str)
    warned = Signal(str)
    started_ok = Signal(str)
    # `finished` is QThread's own signal; the real Engine does not declare one either.

    def __init__(self, cache_dir: object = None) -> None:
        super().__init__()
        self.cache_dir = cache_dir
        self.configs: list[dict[str, Any]] = []
        self.previews: list[bool] = []
        self.start_calls = 0
        self.stop_requests = 0
        self.refuse_start = False
        self.ignore_stop = False  # a thread that will not come down: what shutdown's timeout is for
        self.timed_out = False
        self._park = threading.Event()

    def configure(self, **kwargs: Any) -> None:
        self.configs.append(kwargs)

    def set_preview(self, enabled: bool) -> None:
        self.previews.append(enabled)

    def request_stop(self) -> None:
        self.stop_requests += 1
        if not self.ignore_stop:
            self._park.set()

    # Returns whether it launched, as Engine.start does; QThread.start returns nothing.
    def start(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        priority: QThread.Priority = QThread.Priority.InheritPriority,
    ) -> bool:
        self.start_calls += 1
        if self.refuse_start:
            return False
        if not self.wait(JOIN_MS):
            return False
        self._park.clear()
        super().start(priority)
        return True

    def run(self) -> None:
        self.timed_out = not self._park.wait(PARK_CEILING_S)

    def release(self) -> None:
        """End the parked run whatever the engine was told, for the fixture to join on."""
        self._park.set()


@pytest.fixture
def controller(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[EngineController]:
    # EngineController builds a real Engine in __init__, so the class has to be replaced before
    # the controller exists, not after.
    monkeypatch.setattr("map_overlay.bridge.engine_controller.Engine", StubEngine)
    made = EngineController()
    yield made
    stub = made._engine
    assert isinstance(stub, StubEngine)
    stub.release()
    assert stub.wait(JOIN_MS), "the stub engine thread never finished"
    assert not stub.timed_out, "the stub engine thread was left parked until its own ceiling"


@pytest.fixture
def engine(controller: EngineController) -> StubEngine:
    """The stub the controller built for itself; there is no other handle to it."""
    stub = controller._engine
    assert isinstance(stub, StubEngine)
    return stub


@pytest.fixture
def phases(controller: EngineController) -> list[Phase]:
    seen: list[Phase] = []
    controller.phaseChanged.connect(seen.append)
    return seen


def start(controller: EngineController, reference: str = "map-a.png") -> bool:
    """A start request whose reference names it, so a replayed configuration can be told apart."""
    return controller.start(SETTINGS, REGION, reference, SCREEN)


def test_a_fresh_controller_is_idle_and_has_not_started_anything(
    controller: EngineController, engine: StubEngine
) -> None:
    assert controller.phase is Phase.IDLE
    assert controller.running is False
    assert controller.capture_backend_name is None
    assert engine.start_calls == 0


def test_a_start_reaches_running_through_starting_and_a_stop_returns_to_idle(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    assert start(controller) is True
    assert controller.phase is Phase.STARTING

    engine.started_ok.emit("dxcam")
    assert controller.phase is Phase.RUNNING

    assert controller.stop() is True
    assert controller.phase is Phase.STOPPING
    assert engine.stop_requests == 1

    engine.finished.emit()

    assert phases == [Phase.STARTING, Phase.RUNNING, Phase.STOPPING, Phase.IDLE]
    assert controller.phase is Phase.IDLE
    assert engine.start_calls == 1


def test_a_stop_while_starting_is_not_undone_by_the_late_started_report(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    """Capture takes a moment to open, so a stop can land before the thread says it started.

    That report must not lift the phase back to RUNNING: the panel would show a run it cannot
    start again, and the capture-backend notice would follow a stop the user already saw.
    """
    assert start(controller)
    controller.stop()

    engine.started_ok.emit("mss")
    assert controller.phase is Phase.STOPPING
    assert controller.capture_backend_name == "mss"

    engine.finished.emit()
    assert phases == [Phase.STARTING, Phase.STOPPING, Phase.IDLE]


def test_running_is_true_from_the_accepted_start_until_the_thread_reports_finished(
    controller: EngineController, engine: StubEngine
) -> None:
    assert controller.running is False

    assert start(controller)
    assert controller.running is True  # STARTING: the thread has not confirmed anything yet

    engine.started_ok.emit("mss")
    assert controller.running is True

    controller.stop()
    # STOPPING is not running: this is the window a start() must be parked in, and a controller
    # that called it running would accept one and launch a second engine over the first.
    assert controller.running is False

    engine.finished.emit()
    assert controller.running is False


def test_start_hands_the_engine_everything_the_loop_needs(
    controller: EngineController, engine: StubEngine
) -> None:
    assert start(controller) is True

    assert engine.configs == [
        {
            "settings": SETTINGS,
            "region": REGION,
            "reference": "map-a.png",
            "screen_size": SCREEN,
            "reference_size": None,  # the image is the map itself: nothing to bring it onto
        }
    ]
    assert engine.start_calls == 1


def test_a_second_start_is_refused_while_the_engine_is_already_up(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    assert start(controller, "map-a.png") is True

    assert start(controller, "map-b.png") is False  # STARTING
    engine.started_ok.emit("dxcam")
    assert start(controller, "map-c.png") is False  # RUNNING

    assert [config["reference"] for config in engine.configs] == ["map-a.png"]
    assert engine.start_calls == 1
    assert phases == [Phase.STARTING, Phase.RUNNING]


def test_a_start_requested_while_stopping_is_replayed_when_the_thread_finishes(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    assert start(controller, "map-a.png")
    engine.started_ok.emit("dxcam")
    assert controller.stop()

    assert start(controller, "map-b.png") is True  # accepted, and deliberately not run yet
    assert controller.phase is Phase.STOPPING
    assert controller._restart_pending is not None
    assert [config["reference"] for config in engine.configs] == ["map-a.png"]
    assert engine.start_calls == 1

    engine.finished.emit()

    assert phases == [
        Phase.STARTING,
        Phase.RUNNING,
        Phase.STOPPING,
        Phase.IDLE,
        Phase.STARTING,
    ]
    assert controller.phase is Phase.STARTING
    assert [config["reference"] for config in engine.configs] == ["map-a.png", "map-b.png"]
    assert engine.start_calls == 2
    assert controller._restart_pending is None


def test_only_the_last_start_requested_while_stopping_is_replayed(
    controller: EngineController, engine: StubEngine
) -> None:
    assert start(controller, "map-a.png")
    engine.started_ok.emit("dxcam")
    assert controller.stop()

    assert start(controller, "map-b.png") is True
    assert start(controller, "map-c.png") is True

    engine.finished.emit()

    assert [config["reference"] for config in engine.configs] == ["map-a.png", "map-c.png"]


def test_a_stop_during_stopping_drops_the_parked_start(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    """Stop is the user's last word: a Start they already changed their mind about stays dropped."""
    assert start(controller, "map-a.png")
    engine.started_ok.emit("dxcam")
    assert controller.stop()
    assert start(controller, "map-b.png") is True

    assert controller.stop() is False  # STOPPING is not running, so there is nothing left to ask
    assert controller._restart_pending is None

    engine.finished.emit()

    assert phases == [Phase.STARTING, Phase.RUNNING, Phase.STOPPING, Phase.IDLE]
    assert controller.phase is Phase.IDLE
    assert [config["reference"] for config in engine.configs] == ["map-a.png"]
    assert engine.start_calls == 1


def test_stop_is_refused_and_silent_when_nothing_is_running(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    assert controller.stop() is False

    assert engine.stop_requests == 0
    assert controller.phase is Phase.IDLE
    assert phases == []


def test_a_launch_the_thread_refuses_leaves_the_controller_idle(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    engine.refuse_start = True

    assert start(controller) is False

    assert controller.phase is Phase.IDLE
    assert controller.running is False
    assert phases == []


def test_the_phase_signal_fires_only_on_a_real_change(
    controller: EngineController, engine: StubEngine, phases: list[Phase]
) -> None:
    """The overlay and the panel repaint on this signal; a repeated phase is not a change."""
    assert start(controller)
    engine.started_ok.emit("dxcam")
    engine.started_ok.emit("dxcam")
    engine.finished.emit()
    engine.finished.emit()

    assert phases == [Phase.STARTING, Phase.RUNNING, Phase.IDLE]


def test_the_capture_backend_name_is_taken_from_the_thread_that_reports_it(
    controller: EngineController, engine: StubEngine
) -> None:
    assert controller.capture_backend_name is None

    assert start(controller)
    assert controller.capture_backend_name is None  # STARTING: no backend has been chosen yet

    engine.started_ok.emit("dxcam")
    assert controller.capture_backend_name == "dxcam"


def test_reconfigure_reaches_the_engine_only_while_it_is_running(
    controller: EngineController, engine: StubEngine
) -> None:
    controller.reconfigure(settings={"fps": 30})
    assert engine.configs == []  # IDLE

    assert start(controller)
    engine.started_ok.emit("dxcam")
    controller.reconfigure(settings={"fps": 30})
    assert engine.configs[-1] == {"settings": {"fps": 30}}

    controller.stop()
    controller.reconfigure(settings={"fps": 15})
    assert engine.configs[-1] == {"settings": {"fps": 30}}  # STOPPING: nothing left to reconfigure


def test_the_preview_switch_reaches_the_engine_whatever_the_phase(
    controller: EngineController, engine: StubEngine
) -> None:
    """Unlike reconfigure, this one is unconditional: the engine only stores the flag."""
    controller.set_preview(True)
    assert start(controller)
    controller.set_preview(False)

    assert engine.previews == [True, False]


def test_the_engines_own_signals_are_re_emitted_to_the_gui(
    controller: EngineController, engine: StubEngine
) -> None:
    matrix = object()
    transforms: list[Any] = []
    moves: list[tuple[float, float]] = []
    stats: list[dict[str, Any]] = []
    previews: list[str] = []
    failures: list[str] = []
    warnings: list[str] = []
    controller.transformChanged.connect(transforms.append)
    controller.playerMoved.connect(lambda x, y: moves.append((x, y)))
    controller.stats.connect(stats.append)
    controller.preview.connect(previews.append)
    controller.failed.connect(failures.append)
    controller.warned.connect(warnings.append)

    engine.transformChanged.emit(matrix)
    engine.playerMoved.emit(1.5, -2.5)
    engine.statsChanged.emit({"fps": 60})
    engine.previewReady.emit("<base64 jpeg>")
    engine.failed.emit("vision.no_region_or_route")
    engine.warned.emit("vision.tracker_rebuilt")

    assert transforms == [matrix]
    assert moves == [(1.5, -2.5)]
    assert stats == [{"fps": 60}]
    assert previews == ["<base64 jpeg>"]
    assert failures == ["vision.no_region_or_route"]
    assert warnings == ["vision.tracker_rebuilt"]


def test_shutdown_joins_the_thread_and_lands_on_idle(
    controller: EngineController,
    engine: StubEngine,
    phases: list[Phase],
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert start(controller)
    engine.started_ok.emit("dxcam")

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        controller.shutdown()

    assert engine.stop_requests == 1
    assert engine.isRunning() is False  # shutdown returned only once the thread was down
    assert caplog.records == []
    assert phases == [Phase.STARTING, Phase.RUNNING, Phase.IDLE]
    assert controller.phase is Phase.IDLE


def test_shutdown_gives_up_on_a_thread_that_will_not_come_down(
    controller: EngineController,
    engine: StubEngine,
    phases: list[Phase],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stuck frame must not hold the app open: the wait has a deadline and IDLE follows anyway."""
    assert start(controller)
    engine.started_ok.emit("dxcam")
    engine.ignore_stop = True

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        controller.shutdown(timeout_ms=NO_FINISH_MS)

    assert engine.isRunning() is True
    assert len(caplog.records) == 1
    assert "did not finish" in caplog.text
    assert phases == [Phase.STARTING, Phase.RUNNING, Phase.IDLE]
    assert controller.phase is Phase.IDLE


def test_shutdown_drops_a_parked_start_instead_of_replaying_it_on_the_way_out(
    controller: EngineController, engine: StubEngine
) -> None:
    assert start(controller, "map-a.png")
    engine.started_ok.emit("dxcam")
    assert controller.stop()
    assert start(controller, "map-b.png") is True

    controller.shutdown()
    engine.finished.emit()  # the stopping run reporting in after the app asked to close

    assert controller.phase is Phase.IDLE
    assert [config["reference"] for config in engine.configs] == ["map-a.png"]
    assert engine.start_calls == 1
