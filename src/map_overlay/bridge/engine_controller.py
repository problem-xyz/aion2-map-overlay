"""Owns the vision Engine and the state machine around it.

The engine is a thread, so "running" is not a boolean the caller can flip. Between asking it
to stop and it actually finishing there is a window in which start() must not be honoured,
and the old code had no name for it. IDLE / STARTING / RUNNING / STOPPING gives it one.

stop() does not wait. Waiting on the GUI thread for a frame to finish is how the window goes
white and Windows offers to close it; the only wait left is in shutdown(), with a timeout,
because by then there is nothing else to draw. A Start pressed while STOPPING is remembered
and replayed when the thread reports finished, so the click is never silently dropped.
"""

import logging
from enum import Enum

from PySide6.QtCore import QObject, Signal

from map_overlay.core.constants import ENGINE_SHUTDOWN_WAIT_MS
from map_overlay.vision.engine import Engine

log = logging.getLogger(__name__)


class Phase(Enum):
    """Where the engine thread stands between a request and the thread agreeing to it.

    STARTING and RUNNING both count as running. STOPPING is the window the boolean did not
    have: the thread has been asked to stop but has not reported finished, and a start()
    during it is remembered rather than run. Only the controller sets this; a caller reads it.
    """

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class EngineController(QObject):
    """The only thing allowed to start, stop or reconfigure the vision Engine.

    Live on the GUI thread and call every method from there. Most of the signals below are
    the Engine's own, re-emitted, so they arrive queued on the GUI thread; phaseChanged is
    this object's. Nothing here blocks except shutdown(), which waits with a timeout.

    start() and stop() only request a transition -- the thread confirms it through
    phaseChanged, so a caller must not assume the phase has changed when the call returns.
    """

    phaseChanged = Signal(object)  # Phase
    stats = Signal(dict)
    preview = Signal(str)
    playerMoved = Signal(float, float)
    transformChanged = Signal(object)
    failed = Signal(str)
    warned = Signal(str)

    def __init__(self, parent=None, cache_dir=None) -> None:
        super().__init__(parent)
        self._engine = Engine(cache_dir)
        self._phase = Phase.IDLE
        self._restart_pending = None
        self.capture_backend_name = None

        self._engine.transformChanged.connect(self.transformChanged)
        self._engine.playerMoved.connect(self.playerMoved)
        self._engine.statsChanged.connect(self.stats)
        self._engine.previewReady.connect(self.preview)
        self._engine.failed.connect(self.failed)
        self._engine.warned.connect(self.warned)
        self._engine.started_ok.connect(self._on_started)
        self._engine.finished.connect(self._on_finished)

    # ------------------------------------------------------------------ phase
    @property
    def phase(self):
        return self._phase

    @property
    def running(self):
        """True from the moment start() is accepted until the thread reports finished."""
        return self._phase in (Phase.STARTING, Phase.RUNNING)

    def _set_phase(self, phase) -> None:
        if phase is not self._phase:
            self._phase = phase
            # INFO: a handful per session, and a user's log otherwise cannot tell a Stop/Start
            # from the capture reopening on its own.
            log.info("engine phase -> %s", phase.value)
            self.phaseChanged.emit(phase)

    # ------------------------------------------------------------------ control
    def start(self, settings, region, reference, screen_size, reference_size=None):
        config = {
            "settings": settings,
            "region": region,
            "reference": reference,
            "screen_size": screen_size,
            "reference_size": reference_size,
        }
        if self._phase is Phase.STOPPING:
            # The previous run has not finished. Remember the request instead of dropping it.
            self._restart_pending = config
            return True
        if self.running:
            return False
        return self._launch(config)

    def _launch(self, config):
        self._engine.configure(**config)
        if not self._engine.start():
            return False
        self._set_phase(Phase.STARTING)
        return True

    def stop(self):
        """Ask the thread to stop and return immediately. IDLE arrives with finished."""
        self._restart_pending = None
        if not self.running:
            return False
        self._set_phase(Phase.STOPPING)
        self._engine.request_stop()
        return True

    def reconfigure(self, **kwargs) -> None:
        """Push changed settings into a running engine. A no-op when it is not running."""
        if self.running:
            self._engine.configure(**kwargs)

    def set_preview(self, enabled) -> None:
        self._engine.set_preview(enabled)

    def shutdown(self, timeout_ms=ENGINE_SHUTDOWN_WAIT_MS) -> None:
        """The one place a wait is allowed: nothing is left to keep responsive."""
        self._restart_pending = None
        self._engine.request_stop()
        if self._engine.isRunning() and not self._engine.wait(timeout_ms):
            log.warning("engine thread did not finish within %d ms", timeout_ms)
        self._set_phase(Phase.IDLE)

    # ------------------------------------------------------------------ engine callbacks
    def _on_started(self, backend) -> None:
        self.capture_backend_name = backend
        # Only out of STARTING. A stop asked for while the thread was still opening capture
        # has already moved the phase to STOPPING, and RUNNING now would put a run nobody
        # wants back on screen until finished arrives.
        if self._phase is Phase.STARTING:
            self._set_phase(Phase.RUNNING)

    def _on_finished(self) -> None:
        self._set_phase(Phase.IDLE)
        if self._restart_pending is not None:
            config, self._restart_pending = self._restart_pending, None
            log.debug("replaying the start requested while stopping")
            self._launch(config)
