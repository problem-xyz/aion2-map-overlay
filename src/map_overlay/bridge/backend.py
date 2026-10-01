"""Backend: the object the React pages see over QWebChannel.

Every method here runs on the Qt GUI thread. Backend itself is a facade: it owns no data and
no widgets, only the services below it, and each slot is a call into one of them plus a state
emit. Anything longer than about five lines in a slot belongs in a service.

FROZEN CONTRACT -- do not change a signature below, and do not change the route, map or
object-set file formats. The UI is built against these names and saved user data against
those formats. New capability means a new slot or a new optional field, plus a bump of `api`
in getState(); it never means editing one of these.

    signals: stateChanged, statsChanged, previewChanged, notify, editorRequest,
             progressChanged, stepsChanged, updateChanged

    slots (38):
      checkForUpdates()
      closeEditor()
      copyRouteCode(route_id)
      copyText(text)
      deleteRoute(route_id)
      downloadUpdate()
      exportRoute(route_id)
      getEditorRoute() -> str
      getObjects(map_id) -> str
      getState() -> str
      importRouteFile()
      installUpdate(restart)
      openEditor(route_id)
      openLogsFolder()
      openMapsFolder()
      openRoutesFolder()
      openUrl(url)
      pasteRouteCode()
      refreshRoutes()
      reorderRoutes(payload)
      resetProgress()
      resetRegion()
      resetSettings()
      saveRoute(payload) -> str
      selectRegion()
      setCaptureVisible(visible)
      setOverlayVisible(visible)
      setPlayerAnchor(fx, fy)
      setPreview(enabled)
      setProgress(done)
      setRoute(route_id)
      setStepsPinned(pinned)
      setStepsSize(size)
      setStepsVisible(visible)
      skipUpdate(version)
      start()
      stop()
      updateSettings(payload)

The `steps` object exposed to the steps page has its own 6 slots and 1 signal, declared in
qt/steps_window.py, and is frozen on the same terms.
"""

import contextlib
import json
import logging
import sys
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import QLocale, QObject, QTimer, Signal, Slot

from map_overlay import __version__
from map_overlay.bridge.engine_controller import EngineController, Phase
from map_overlay.bridge.notifier import Notifier
from map_overlay.bridge.progress import ProgressTracker
from map_overlay.bridge.route_service import RouteService
from map_overlay.bridge.settings_store import SettingsStore
from map_overlay.bridge.state import build_state, progress_state, steps_of, steps_state
from map_overlay.bridge.tile_queue import TileBuildQueue
from map_overlay.bridge.windows import WindowManager
from map_overlay.core.appinfo import DISCORD_URL, DONATE_URL, PARTNER_DISCORD_URL, REPO_URL
from map_overlay.core.errors import AppError
from map_overlay.core.geometry import ScreenCheck, check_regions
from map_overlay.core.links import is_project_url
from map_overlay.core.paths import DataDirs, is_portable, run_migration
from map_overlay.core.settings import STEPS_SIZE_SCALE, Settings, plaque_scale
from map_overlay.i18n.catalog import format_code, resolve_language, set_language, t
from map_overlay.qt.dialogs import DialogService
from map_overlay.qt.folder_watcher import FolderWatcher
from map_overlay.qt.overlay import primary_screen_geometry
from map_overlay.qt.region_selector import RegionSelector
from map_overlay.qt.screens import ScreenWatcher, primary_rect, screen_rects
from map_overlay.qt.steps_window import WebStepsWindow, scale_region
from map_overlay.qt.webview import local_file_url, system_dpi_scale, ui_url
from map_overlay.qt.win32 import supports_capture_exclusion, windows_version
from map_overlay.store import legacy
from map_overlay.store.banner import Banner, load_banner
from map_overlay.store.maps import MapSpec
from map_overlay.store.objects import cube_points, icons_under
from map_overlay.updater.manager import ManagerFactory, velopack_manager
from map_overlay.updater.service import UpdatePayload, UpdaterService

log = logging.getLogger(__name__)

# copyText() carries a line of the page's own text, an address or a code; nothing longer
_COPY_TEXT_MAX = 256

# How long the overlay goes on saying why a run ended, over the map, before it goes.
OVERLAY_ERROR_MS = 8000


class Backend(QObject):
    """The one QWebChannel object every React page is built against.

    The names below are wire format, not internal API: the panel, the steps page and the
    editor bind to these exact slots and signals, and the documents they carry are the
    formats already on the user's disk. Grow this class -- a new slot, a new optional key --
    and bump API_VERSION in bridge/state.py so a page can tell what it is talking to. Never
    rename one, change a signature, or drop a key.

    Every method runs on the Qt GUI thread. Backend owns no data and no widgets of its own:
    a slot is a call into one of the services plus a state emit.
    """

    stateChanged = Signal(str)  # JSON: the whole state, as getState() returns it
    statsChanged = Signal(str)  # JSON: StatsPayload
    previewChanged = Signal(str)  # base64 JPEG
    notify = Signal(str)  # JSON: {"level": "info"|"error", "text": "..."}
    editorRequest = Signal(str)  # JSON: which route the editor should open
    progressChanged = Signal(str)  # JSON: {"done": n, "total": n} -- kept off stateChanged,
    # because the whole state drags every thumbnail along with it
    stepsChanged = Signal(str)  # JSON: the steps plaque state. Kept off it for the same
    # reason: the plaque is dragged by mouse, and the whole state reads every route and map
    updateChanged = Signal(str)  # JSON: UpdatePayload, as getState()["update"] carries it. On
    # every change, download progress included; stateChanged follows only a change of phase

    # Counts the errors the overlay was given to show, so that the timer of one already cleared
    # does not clear the next. A class default: Backend.__init__ is at its statement limit.
    _overlay_error_shown = 0

    def __init__(
        self,
        dirs: DataDirs,
        dev=False,
        parent=None,
        *,
        update_factory: ManagerFactory | None = None,
        maps: tuple[MapSpec, ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self.dirs = dirs
        self.dev = bool(dev)

        self._store = SettingsStore(dirs, self)
        # Before any window exists: a title is set in a constructor, so the language has to be
        # chosen first or every window would be born in English and need re-titling.
        set_language(resolve_language(self.settings.language, QLocale.system().name()))
        # `maps` is for tests: the shipped registry means cutting two 8192 px images.
        self._routes = RouteService(dirs, dev=dev, maps=maps)
        self._banner = load_banner()
        self._progress = ProgressTracker(self._store, self)
        self._step_objects: list[str] = []  # the icon under each point, for the plaque
        self._cubes: list[tuple[float, float]] = []  # the route's map's hidden cubes, reference px
        # The map a Start with no route was run on, for its cubes alone; a route's map wins.
        self._free_map: str | None = None
        self.overlay_visible = True

        self._editor_req = {"seq": 0, "id": None, "doc": None}
        self._notifier = Notifier(self.notify.emit)
        self._dialogs = DialogService(self._dialog_parent)
        self._tiles = TileBuildQueue(dirs, self._routes.tiles_source_for_map, self)
        self._tiles.mapDone.connect(self._on_tiles_done)
        self._migrate_legacy()
        self._seed_routes()
        if self._store.corrupt_backup:
            self._notifier.queue(
                "settings.corrupt", "warning", backup=self._store.corrupt_backup.name
            )
        if self._store.reset_keys:
            self._notifier.queue(
                "settings.values_reset", "warning", keys=", ".join(self._store.reset_keys)
            )
        # A route named in state may have been deleted between runs.
        if self.route and not self._routes.route_exists(self.route):
            self._store.set_state(route=None)
        self._capture_exclusion = self._probe_capture_exclusion()

        self._windows = WindowManager(dev, self)
        self.overlay.set_recordable(self._recordable)
        self._setup_steps()

        self.engine = EngineController(self)
        self.engine.transformChanged.connect(self.overlay.set_transform)
        self.engine.playerMoved.connect(self._on_player)
        self.engine.stats.connect(self._on_stats)
        self.engine.preview.connect(self.previewChanged)
        self.engine.failed.connect(self._on_engine_failed)
        self.engine.warned.connect(self._on_engine_warned)
        self.engine.phaseChanged.connect(self._on_engine_phase)
        self._progress.changed.connect(self._on_progress_changed)
        # Before the plaque is first shown: the monitor either rectangle was saved on may have
        # been unplugged since the last run.
        self._check_screens()
        self._screens = ScreenWatcher(self)
        self._screens.changed.connect(self._revalidate_screens)
        # A route dropped into the folder, or deleted from it, shows in the panel without a restart.
        self._routes_folder = FolderWatcher(dirs.routes, self)
        self._routes_folder.changed.connect(self._on_routes_folder_changed)
        self._tiles.enqueue([m["id"] for m in self._routes.maps() if not m["tiles"]["ready"]])
        if self.route:  # the steps list must be there before the overlay is ever started
            self._apply_route(self._route_doc(self.route, quiet=True))

        # post, not emit: a package left by an earlier run reports ready before the page listens.
        self._updates = UpdaterService(
            settings=lambda: self.settings,
            update_settings=self._store.update_settings,
            notify=self._notifier.post,
            prepare_exit=self._before_update_exit,
            resume_after_failed_exit=self._after_failed_update_exit,
            factory=update_factory or velopack_manager,
            parent=self,
        )
        self._update_phase = self._updates.snapshot()["phase"]
        self._updates.stateChanged.connect(self._on_update_changed)
        self._updates.start()

    def _migrate_legacy(self) -> None:
        """Move version 2 routes out of routes/, naming that folder if something would not move."""
        moved = run_migration(
            "migrating the version 2 layout", partial(legacy.migrate_v2_layout, self.dirs)
        )
        if moved is None:
            self._notifier.queue("data.migration_failed", "warning", path=str(self.dirs.routes))
        elif moved:
            self._notifier.queue("legacy.routes_moved", names=", ".join(moved))

    def _seed_routes(self) -> None:
        """Give a new install the starter routes, each once, and update the untouched ones."""
        seeded = self._store.state.seeded_routes
        result = self._routes.seed_bundled(seeded)
        if result.handled:
            self._store.set_state(seeded_routes=[*seeded, *result.handled])
        if result.updated:
            self._notifier.queue("route.starters_updated", names=", ".join(result.updated))

    def _probe_capture_exclusion(self) -> bool:
        """Can the windows over the game be hidden from capture here? Warns once if not."""
        version = windows_version()
        if version is None or supports_capture_exclusion(version):
            return True
        shown = ".".join(str(part) for part in version)
        log.warning("Windows %s has no WDA_EXCLUDEFROMCAPTURE: the overlay stays capturable", shown)
        self._notifier.queue("system.old_windows", "warning", version=shown)
        return False

    @property
    def _recordable(self) -> bool:
        """What the windows over the game are told about screen capture.

        Where Windows cannot exclude a window from capture, asking it to applies WDA_MONITOR
        instead and the overlay turns into a black box in the engine's own frames -- so there
        they stay visible whatever capture_visible says, and the panel greys the option out.
        """
        return self.settings.capture_visible or not self._capture_exclusion

    def _check_screens(self) -> ScreenCheck:
        """Drop a map area no monitor shows any more, and pull the plaque back onto one.

        A lost area stops a running engine first: capture there is black frames under mss and
        an exception on every frame under dxcam. The plaque is moved without a notice, because
        the user can see where it went. The notice is posted, not emitted: at start-up, and
        after a monitor change that lands before a slow page has connected, nobody is
        listening yet, and it waits for the first getState().
        """
        region = self.state.region
        screens = screen_rects()
        check = check_regions(region, self.state.steps_region, screens, primary_rect())
        if check.region_lost and region is not None:
            log.warning("map area %s is on none of the screens %s: cleared", region, screens)
            self.stop()
            self._store.set_state(region=None)
            # The position as text: the UI groups a number, and "at 6,000, 200" reads as three
            # numbers where "at 6000, 200" reads as two -- format.coordinate's reason, over here.
            params = dict(region, left=str(region["left"]), top=str(region["top"]))
            self._notifier.post("warning", "region.offscreen", **params)
        if check.steps_moved:
            log.info(
                "steps plaque moved onto a screen: %s -> %s",
                self.state.steps_region,
                check.steps_region,
            )
            self._store.set_state(steps_region=check.steps_region)
        return check

    def _revalidate_screens(self) -> bool:
        """After a monitor change, and before a start. True when the map area had to go."""
        check = self._check_screens()
        if check.steps_moved:
            self._sync_steps()
        if check.region_lost or check.steps_moved:
            self._emit_state()
        return check.region_lost

    @property
    def overlay(self):
        return self._windows.overlay

    @property
    def steps(self):
        return self._windows.steps

    @property
    def running(self):
        return self.engine.running

    @property
    def settings(self):
        return self._store.settings

    @property
    def state(self):
        return self._store.state

    @property
    def route(self):
        return self._store.state.route

    @property
    def progress(self):
        return self._store.state.progress

    def _route_doc(self, route_id, quiet=False):
        try:
            return self._routes.route_doc(route_id)
        except AppError as e:
            if not quiet:
                self._notifier.from_error(e)
        except OSError as e:
            if not quiet:
                self._notify("error", "route.save_failed", reason=str(e))
            return None

    def _apply_route(self, doc) -> None:
        self._routes.active_doc = doc
        # What each point sits on, for the plaque's icons: worked out once per route, not on
        # every point passed
        map_id = doc["map"] if doc else self._free_map
        sets = self._routes.load_objects(map_id) if map_id else []
        self._step_objects = self._objects_under(doc, sets)
        meta = self._map_meta(map_id) if map_id else None
        self._cubes = cube_points(sets, meta["size"]) if meta else []
        # The ring shows where a point ticks itself off. With auto marking off nothing does, so
        # it is left out, like the crosshair in the preview; updateSettings redraws on the switch.
        radius = self.settings.arrive_radius if self.settings.auto_progress else 0.0
        self._windows.apply_route(
            doc,
            ref_size=meta["size"] if doc and meta else None,
            arrive_radius=radius,
            steps=steps_of(doc, self._step_objects),
            done=self._progress.done_count(doc),
            name=doc["name"] if doc else "",
        )
        self._apply_cubes()
        self._sync_steps()

    def _apply_cubes(self) -> None:
        """The hidden cubes over the game while the Cubes switch is on, and the window for them."""
        cubes = self._cubes if self.settings.show_cubes else []
        self.overlay.set_cubes(cubes, self.settings.cube_radius)
        self._sync_overlay()

    def _overlay_wanted(self) -> bool:
        """The route and the cubes share the one window: it is up while either is drawn."""
        return self.overlay_visible or (self.settings.show_cubes and bool(self._cubes))

    def _sync_overlay(self) -> None:
        if not self.running:
            return
        if self._overlay_wanted():
            if not self.overlay.isVisible() and self.state.region:
                self._windows.show_overlay(self.state.region, self.settings.opacity)
        else:
            self.overlay.hide()

    def _objects_under(self, doc, sets) -> list[str]:
        if not doc:
            return []
        return icons_under(sets, doc["mapSize"], [(m["x"], m["y"]) for m in doc["markers"]])

    def _set_done(self, done) -> None:
        self._progress.set_done(done, self._routes.active_doc)

    def _on_progress_changed(self, done, total) -> None:
        doc = self._routes.active_doc
        self._windows.apply_progress(
            steps_of(doc, self._step_objects),
            self._progress.done_count(doc),
            doc["name"] if doc else "",
        )
        self._sync_steps()
        self.progressChanged.emit(json.dumps({"done": done, "total": total}))

    def _on_player(self, x, y) -> None:
        """Player position arrived in reference pixels: is the next point reached?"""
        doc = self._routes.active_doc
        meta = self._map_meta(doc["map"]) if doc else None
        reached = self._progress.on_player(x, y, doc, meta["size"] if meta else None)
        if reached is not None:
            self._progress.set_done(reached, doc)

    @Slot(int)
    def setProgress(self, done: int) -> None:
        self._set_done(done)
        self._emit_state()

    @Slot()
    def resetProgress(self) -> None:
        self._set_done(0)
        self._emit_state()

    def _map_meta(self, map_id):
        return self._routes.map_meta(map_id)

    def _on_tiles_done(self, map_id, ok) -> None:
        meta = self._map_meta(map_id)
        label = meta["label"] if meta else map_id
        if ok:
            self._notify("info", "map.tiles_ready", label=label)
        else:
            self._notify("error", "map.tiles_failed", label=label)
        self._emit_state()

    def _state(self):
        maps = self._routes.maps()
        doc = self._routes.active_doc
        routes = self._routes.list_routes({m["id"]: m for m in maps}, self.state.route_order)
        # A state rebuild can run before the page has connected -- a map finishing its tiles
        # at start-up -- and each of these notices comes up only once.
        for skipped in self._routes.take_skipped():
            self._notifier.post("warning", skipped.code, **skipped.params)
        # store/ builds both lists as plain dicts in the MapInfo and RouteInfo shapes; those
        # types live in bridge/, which store/ does not import.
        return build_state(
            version=__version__,
            settings=self.settings,
            state=self.state,
            maps=maps,  # pyright: ignore[reportArgumentType]
            routes=routes,  # pyright: ignore[reportArgumentType]
            running=self.running,
            overlay_visible=self.overlay_visible,
            capture_backend=self.engine.capture_backend_name,
            platform=sys.platform,
            progress=progress_state(doc, self._progress.done_count(doc)),
            editor_open=self._windows.editor_visible(),
            tiles_busy=self._tiles.busy(),
            dev=self.dev,
            portable=is_portable(),
            update=self._updates.snapshot(),
            capture_exclusion=self._capture_exclusion,
            repo_url=REPO_URL,
            links={
                "donate": DONATE_URL,
                "discord": DISCORD_URL,
                "partnerDiscord": PARTNER_DISCORD_URL,
            },
            banner=(self._banner_payload(self._banner) if self._banner else None),
        )

    def _banner_payload(self, banner: Banner) -> dict[str, str]:
        out = {
            "image": local_file_url(banner.image, self.dev),
            "url": banner.url,
            "label": banner.label,
        }
        if banner.code and banner.discount:
            out |= {"code": banner.code, "discount": banner.discount}
        return out

    def _emit_state(self) -> None:
        self.stateChanged.emit(json.dumps(self._state(), ensure_ascii=False))

    def _emit_steps(self) -> None:
        payload = steps_state(self.settings, self.state)
        self.stepsChanged.emit(json.dumps(payload, ensure_ascii=False))

    def _notify(self, level, code, **params) -> None:
        self._notifier.emit(level, code, **params)

    def queue_notice(self, code: str, level: str = "info", **params: Any) -> None:
        """A notice raised before the page connected; drained on the first getState()."""
        self._notifier.queue(code, level, **params)

    @Slot(result=str)
    def getState(self) -> str:
        state = json.dumps(self._state(), ensure_ascii=False)
        self._notifier.drain()  # queued notices waited for the page to connect
        return state

    def _dialog_parent(self):
        return self._windows.editor if self._windows.editor_visible() else self.parent()

    @Slot()
    def start(self) -> None:
        if self.running:
            return
        # The layout may have changed less than a settle interval ago, before the watcher fired.
        if self._revalidate_screens():
            return
        # With the Cubes switch on there is something to draw without a route: the map's cubes.
        # The map is then asked for, after the map area, so that a first Start asks it once.
        free = not self.route and self.settings.show_cubes
        doc, ref, error = (None, None, None) if free else self._routes.runnable_route(self.route)
        if error:
            self._notifier.from_error(error)
            return
        if not self.state.region:
            # The first Start has no map area to capture yet. It asks for one and starts once the
            # box is drawn, rather than sending a new user off to find the button that asks; Esc
            # leaves things as they were, and nothing starts.
            self._pick_region(RegionSelector.START_PROMPT, self._start_in)
            return
        if free:
            ref = self._ask_free_map()
            if ref is None:
                return

        self._apply_route(doc)
        scr = primary_screen_geometry()
        self.engine.start(
            settings=asdict(self.settings),
            region=self.state.region,
            reference=str(ref),
            screen_size=(scr.width(), scr.height()),
        )
        # The overlay comes up with STARTING, in _on_engine_phase: a Start pressed while the
        # last run is still stopping is parked, and the IDLE that ends that run hides it.
        self._emit_state()

    def _ask_free_map(self):
        """Which map a Start with no route runs on: its reference, or None if cancelled."""
        maps = self._routes.maps()
        if not maps:
            return None
        labels = [m["label"] for m in maps]
        ids = [m["id"] for m in maps]
        current = ids.index(self._free_map) if self._free_map in ids else 0
        choice = self._dialogs.ask_choice(
            t("native.dialog.cubesMap"), t("native.dialog.cubesMapPrompt"), labels, current
        )
        if choice is None:
            return None
        map_id = ids[labels.index(choice)]
        _doc, ref, error = self._routes.runnable_map(map_id)
        if error:
            self._notifier.from_error(error)
            return None
        self._free_map = map_id
        return ref

    @Slot()
    def stop(self) -> None:
        """Returns as soon as the thread has been asked. IDLE arrives on phaseChanged."""
        if not self.engine.stop():
            return
        self.overlay.set_transform(None)
        self._clear_overlay_error()
        self.overlay.hide()
        self._emit_state()

    def _on_engine_failed(self, text) -> None:
        code = text if text.startswith("vision.") else "vision.crashed"
        self._notify("error", code, reason=text, path="")
        # Over the map as well, where the player is looking, and in their words: a crash says
        # what to do rather than what OpenCV said, which the panel's notice still carries.
        detail = (
            t("native.overlay.crashedHint")
            if code == "vision.crashed"
            else t(f"notify.{code}", reason=text, path="")
        )
        self.overlay.show_error(t("native.overlay.stopped"), detail)
        self._overlay_error_shown += 1
        shown = self._overlay_error_shown
        QTimer.singleShot(OVERLAY_ERROR_MS, self, lambda: self._overlay_error_expired(shown))

    def _overlay_error_expired(self, shown: int) -> None:
        if shown == self._overlay_error_shown:  # not cleared, nor replaced by a later one
            self._clear_overlay_error()

    def _clear_overlay_error(self) -> None:
        self._overlay_error_shown += 1
        self.overlay.clear_error()
        if not self.running:
            self.overlay.hide()

    def _on_engine_warned(self, text) -> None:
        """Detection hiccuped; the overlay carries on by optical flow."""
        self._notify(
            "warning", text if text.startswith("vision.") else "vision.detect_failed", reason=text
        )

    def _on_engine_phase(self, phase) -> None:
        """The thread can also stop on its own, after an error.

        STARTING is where the overlay is shown, both for a Start and for a Start that was
        parked while the previous run stopped and is replayed only after its IDLE.
        """
        if phase is Phase.IDLE and not self.overlay.has_error():
            self.overlay.hide()  # an error stays up a while, saying why; see _on_engine_failed
        if phase is Phase.STARTING:
            self._clear_overlay_error()
        if phase is Phase.STARTING and self._overlay_wanted() and self.state.region:
            self._windows.show_overlay(self.state.region, self.settings.opacity)
            self._apply_route_view(self.settings)
        if phase is Phase.RUNNING and self.engine.capture_backend_name == "mss":
            # Only when capture fell back. Announcing the fast path on every start would be
            # noise, but a silent fallback leaves the user wondering why it got heavier.
            self._notify("info", "vision.capture_backend", name=self.engine.capture_backend_name)
        self._emit_state()

    def _on_stats(self, stats) -> None:
        self.statsChanged.emit(json.dumps(stats))

    @Slot(bool)
    def setOverlayVisible(self, visible: bool) -> None:
        self.overlay_visible = bool(visible)
        self.overlay.set_route_visible(self.overlay_visible)
        self._sync_overlay()
        self._emit_state()

    @Slot(bool)
    def setCaptureVisible(self, visible: bool) -> None:
        """Whether screen recorders (OBS, Discord, Game Bar) see the overlay."""
        self._store.update_settings({"capture_visible": bool(visible)})
        self.overlay.set_recordable(self._recordable)
        self.steps.set_recordable(self._recordable)
        if self.settings.capture_visible:
            self._notify("info", "overlay.capture_visible_on")
        self._emit_state()

    @Slot(bool)
    def setPreview(self, enabled: bool) -> None:
        self.engine.set_preview(enabled)

    @Slot(str)
    def updateSettings(self, payload: str) -> None:
        try:
            data = json.loads(payload)
        except ValueError:
            return
        if not isinstance(data, dict) or not data:
            return
        # A caller that knows only the three steps means the scale they stand for
        size = data.get("steps_size")
        if "steps_scale" not in data and size in STEPS_SIZE_SCALE:
            data = {**data, "steps_scale": STEPS_SIZE_SCALE[size]}
        # The patch goes through the same coercion as the file on disk: unknown keys dropped,
        # types checked, ranges clamped. A UI bug cannot put a bad value into settings.json.
        before = self.settings
        after = self._store.update_settings(data)
        if after == before:
            return
        self._apply_settings(before, after)
        self._emit_state()

    @Slot()
    def resetSettings(self) -> None:
        """Every preference back to its default, applied exactly as if the user had set each.

        Settings only: the map area, the plaque position, the open route and its progress are
        state and stay. KEPT_ON_RESET in settings_store says which fields survive and why.
        State is emitted even when nothing changed, because the panel may be showing an edit
        it had not sent yet and then dropped when the user confirmed the reset.
        """
        before = self.settings
        self._apply_settings(before, self._store.reset_settings())
        self._notify("info", "settings.reset")
        self._emit_state()

    def _apply_settings(self, before: Settings, after: Settings) -> None:
        """Push a settings change out to every window and thread holding a copy of it."""
        if after == before:
            return
        self.overlay.set_opacity(after.opacity)
        self.steps.set_opacity(after.opacity)
        self._apply_route_view(after)
        if before.capture_visible != after.capture_visible:
            self.overlay.set_recordable(self._recordable)
            self.steps.set_recordable(self._recordable)
        if before.steps_pinned != after.steps_pinned:
            self.steps.set_pinned(after.steps_pinned)
        if before.steps_scale != after.steps_scale:
            self._resize_steps(before.steps_scale)
        if (before.auto_progress, before.arrive_radius) != (
            after.auto_progress,
            after.arrive_radius,
        ):
            self._apply_route(self._routes.active_doc)  # the arrival ring came, went or resized
        elif (before.show_cubes, before.cube_radius) != (after.show_cubes, after.cube_radius):
            self._apply_cubes()
        if before.language != after.language:
            self.apply_language()
        if before.updates_auto_check != after.updates_auto_check:
            self._updates.schedule_auto()
        if before.updates_skipped_version != after.updates_skipped_version:
            self._updates.settings_changed()
        self.engine.reconfigure(settings=asdict(after))

    def _apply_route_view(self, settings: Settings) -> None:
        self.overlay.set_view(settings.route_view, settings.route_ahead, settings.route_past)
        self.steps.set_past(settings.route_past)

    def _pick_region(self, prompt, apply_result) -> None:
        def picked(region) -> None:
            apply_result(region)
            self._notify("info", "region.selected", width=region["width"], height=region["height"])
            # Else the panel goes on showing no area until some other change sends the state
            self._emit_state()

        self._windows.pick_region(prompt, picked, lambda: self.running)

    def _apply_region(self, region) -> None:
        self._store.set_state(region=region)
        if self.running:
            self.overlay.set_region(region)
        self.engine.reconfigure(region=region)

    def _start_in(self, region) -> None:
        """The area a first Start asked for is drawn: keep it, and carry on starting."""
        self._apply_region(region)
        self.start()

    @Slot()
    def selectRegion(self) -> None:
        self._pick_region(RegionSelector.DEFAULT_PROMPT, self._apply_region)

    @Slot()
    def resetRegion(self) -> None:
        """Forget the map area. A running engine stops first: it has nothing left to capture."""
        if not self.state.region:
            return
        self.stop()
        self._store.set_state(region=None)
        self._emit_state()

    def _sync_steps(self) -> None:
        region = self._windows.sync_steps(
            self.state.steps_visible, self.state.steps_region, self.settings.opacity
        )
        if region:
            self._store.set_state(steps_region=region)
            if not self.state.steps_hint_shown:
                # The list is on from the start on a new install, so no switch ever brings the
                # hint: it comes the first time the list is on screen. Posted, since that can be
                # at start, before the page listens.
                self._store.set_state(steps_hint_shown=True)
                self._notifier.post("info", "steps.drag_hint")

    def _setup_steps(self) -> None:
        window = self.steps
        window.set_recordable(self._recordable)
        window.set_scale(self.settings.steps_scale)
        window.set_past(self.settings.route_past)
        window.set_pinned(self.settings.steps_pinned)
        window.regionChanged.connect(self._on_steps_moved)
        window.actionClicked.connect(self._on_steps_action)

    def _on_steps_moved(self, region) -> None:
        """regionChanged fires once, on mouse release, so the position is written once."""
        self._store.set_state(steps_region=region)
        self._emit_steps()

    def _on_steps_action(self, name) -> None:
        if name == "close":
            self.setStepsVisible(False)
        elif name == "pin":
            self.setStepsPinned(not self.settings.steps_pinned)  # the pin shows in both states
        elif name == "size":
            order = WebStepsWindow.ORDER
            self.setStepsSize(order[(order.index(self.settings.steps_size) + 1) % len(order)])
        elif name in ("prev", "next"):
            self._step_progress(1 if name == "next" else -1)

    def _step_progress(self, delta: int) -> None:
        """Tick the next point off by hand, or take the last one back. The panel hears of it
        through progressChanged, as it does of a point reached on foot."""
        doc = self._routes.active_doc
        self._set_done(self._progress.done_count(doc) + delta)

    def _route_ids(self) -> list[str]:
        """The routes' ids in the panel's order."""
        maps = {m["id"]: m for m in self._routes.maps()}
        return [r["id"] for r in self._routes.list_routes(maps, self.state.route_order)]

    def _put_last(self, route_id: str) -> None:
        """A new route goes to the foot of the list. The whole order is written, not only the
        new id: a route the order does not name would otherwise be listed after the new one."""
        ids = [i for i in self._route_ids() if i != route_id]
        self._store.set_state(route_order=[*ids, route_id])

    @Slot(bool)
    def setStepsPinned(self, pinned: bool) -> None:
        """A pinned plaque passes clicks through to the game and hides its buttons."""
        self._store.update_settings({"steps_pinned": bool(pinned)})
        self.steps.set_pinned(self.settings.steps_pinned)
        self._emit_steps()

    @Slot(str)
    def setStepsSize(self, size: str) -> None:
        """One of the three old steps, which set the scale they stand for: the type, and the
        plaque's size with it. The top-left corner stays put. The panel sets steps_scale itself.
        """
        if size not in WebStepsWindow.SIZES:
            return
        scale = WebStepsWindow.SIZES[size]
        before = self.settings.steps_scale
        if (size, scale) == (self.settings.steps_size, before):
            return
        self._store.update_settings({"steps_size": size, "steps_scale": scale})
        self._resize_steps(before)
        self._emit_steps()

    def _resize_steps(self, before: float) -> None:
        """The zoom changed from `before`: the plaque's size, as the user left it, goes with it."""
        self.steps.set_scale(self.settings.steps_scale)
        if self.state.steps_region:
            ratio = plaque_scale(self.settings.steps_scale) / plaque_scale(before)
            self._store.set_state(steps_region=scale_region(self.state.steps_region, ratio))
        self._sync_steps()

    @Slot(bool)
    def setStepsVisible(self, visible: bool) -> None:
        self._store.set_state(steps_visible=bool(visible))
        if self.state.steps_visible and not self.state.steps_hint_shown:
            # Once per machine, the first time the list is shown: repeated on every switch it is
            # advice the user has already taken, standing over the panel for seconds each time.
            self._store.set_state(steps_hint_shown=True)
            self._notify("info", "steps.drag_hint")
        doc = self._route_doc(self.route, quiet=True) if self.route else None
        if doc:
            self._apply_route(doc)
        else:
            self._sync_steps()
        self._emit_state()

    @Slot(str)
    def setRoute(self, route_id: str) -> None:
        doc = self._route_doc(route_id)
        if doc is None:
            return
        prev = self._route_doc(self.route, quiet=True) if self.route else None
        self._store.set_state(route=route_id)
        self._apply_route(doc)
        if self.running and (prev is None or prev["map"] != doc["map"]):
            self._retarget_engine(doc)
        self._emit_state()

    def _on_routes_folder_changed(self) -> None:
        """Something in routes/ changed behind the app: a file copied in, deleted or edited by hand.

        The open route follows its file. One that is gone is closed, as a deleted one is, but its
        progress is kept in case it comes back. One that is no valid route now -- a hand edit saved
        half-way -- stays as it was.
        """
        if self.route and not self._routes.route_exists(self.route):
            if self.running:
                self.stop()
            self._store.set_state(route=None)
            self._apply_route(None)
        elif self.route:
            doc = self._route_doc(self.route, quiet=True)
            prev = self._routes.active_doc
            if doc is not None and doc != prev:
                self._apply_route(doc)
                if self.running and (prev is None or prev["map"] != doc["map"]):
                    self._retarget_engine(doc)
        self._emit_state()

    @Slot()
    def refreshRoutes(self) -> None:
        """Not called by the UI today. Kept: it costs nothing and a manual refresh is the
        obvious escape hatch when something on disk changed behind the app."""
        self._emit_state()

    @Slot(str)
    def reorderRoutes(self, payload: str) -> None:
        """payload: JSON list of route ids, in the order the panel should list them.

        An id that is no route is dropped, and a route the list leaves out keeps its place
        after the named ones, so a stale page cannot lose a route from the list.
        """
        try:
            order = json.loads(payload)
        except ValueError:
            order = None
        if not isinstance(order, list):
            log.warning("reorderRoutes: not a list of ids: %.200r", payload)
            return
        known = set(self._route_ids())
        named = [i for i in order if isinstance(i, str) and i in known]
        self._store.set_state(route_order=named)
        self._emit_state()

    @Slot(float, float)
    def setPlayerAnchor(self, fx: float, fy: float) -> None:
        """Where in the capture region to follow the player. Fractions of width and height."""
        self._store.update_settings(
            {
                "player_anchor_x": min(1.0, max(0.0, float(fx))),
                "player_anchor_y": min(1.0, max(0.0, float(fy))),
            }
        )
        self.engine.reconfigure(settings=asdict(self.settings))
        self._emit_state()

    @Slot(str)
    def deleteRoute(self, route_id: str) -> None:
        if self.running and self.route == route_id:
            self.stop()
        self._routes.delete_route(route_id)
        self._progress.forget(route_id)
        self._store.set_state(route_order=[i for i in self.state.route_order if i != route_id])
        if self.route == route_id:
            self._store.set_state(route=None)
            self._apply_route(None)
        self._emit_state()

    @Slot()
    def openRoutesFolder(self) -> None:
        self._dialogs.open_folder(self.dirs.routes)

    @Slot()
    def openMapsFolder(self) -> None:
        """Not called by the UI today; the routes folder button has one, maps does not yet."""
        self._dialogs.open_folder(self.dirs.maps)

    @Slot()
    def openLogsFolder(self) -> None:
        """New slot, not a changed one. The UI has no button for it yet."""
        self._dialogs.open_folder(self.dirs.logs)

    @Slot(str)
    def openUrl(self, url: str) -> None:
        """Open one of the project's own GitHub pages (release notes), or the banner's page.

        Anything else is refused and logged: the check lives here, not in the page, so a page
        that was talked into asking for another address still cannot open it.
        """
        if not is_project_url(url) and not (self._banner and url == self._banner.url):
            log.warning("openUrl refused a link outside the project: %r", url)
            return
        self._dialogs.open_url(url)

    @Slot(str)
    def openEditor(self, route_id: str) -> None:
        """route_id == "" means: start a new route."""
        doc, error = self._routes.editor_doc(route_id)
        if error:
            self._notifier.from_error(error)
            return
        self._windows.raise_editor(self, ui_url(self.dev, "editor"), system_dpi_scale())
        self._request_editor(route_id or None, doc)
        self._emit_state()

    def _request_editor(self, route_id, doc) -> None:
        """Point the editor page at a document: by signal now, by getEditorRoute on a reload."""
        self._editor_req = {"seq": self._editor_req["seq"] + 1, "id": route_id, "doc": doc}
        self.editorRequest.emit(json.dumps(self._editor_req, ensure_ascii=False))

    @Slot(result=str)
    def getEditorRoute(self) -> str:
        return json.dumps(self._editor_req, ensure_ascii=False)

    @Slot()
    def closeEditor(self) -> None:
        self._windows.close_editor()
        self._emit_state()

    @Slot(str, result=str)
    def saveRoute(self, payload: str) -> str:
        """payload: {"id": "..."|null, "doc": {...}} -> {"ok": true, "id": "..."}."""
        route_id, doc, error = self._routes.parse_save_payload(payload)
        if error:
            return self._save_failed(error.code, **error.params)
        is_new = not self._routes.route_exists(route_id)
        # doc is set from here: parse_save_payload returns None for it only beside an error.
        # Unpacking the tuple loses that link for the checker, hence the two ignores below.
        try:
            self._routes.save_route(route_id, doc)
        except AppError as e:  # route.too_large: a file the app could not read back
            return self._save_failed(e.code, **e.params)
        except OSError as e:
            return self._save_failed("route.save_failed", reason=str(e))

        if is_new:
            self._put_last(route_id)  # pyright: ignore[reportArgumentType]
        # may have been shortened
        self._progress.clamp_to(route_id, len(doc["markers"]))  # pyright: ignore[reportOptionalSubscript]
        if not self.route:
            self._store.set_state(route=route_id)
        if self.route == route_id:
            self._apply_route(doc)
            self._retarget_engine(doc)
        self._notify("info", "route.saved", name=doc["name"])  # pyright: ignore[reportOptionalSubscript]
        self._emit_state()
        return json.dumps({"ok": True, "id": route_id})

    def _save_failed(self, code, **params):
        self._notifier.emit("error", code, **params)
        return json.dumps(
            {
                "ok": False,
                "error": format_code(code, params),
                "code": code,
                "params": params,
            }
        )

    def _retarget_engine(self, doc) -> None:
        """Point a running engine at this route's map."""
        ref = self._routes.reference_for_map(doc["map"])
        if ref is not None and ref.exists():
            self.engine.reconfigure(reference=str(ref))

    @Slot(str, result=str)
    def getObjects(self, map_id: str) -> str:
        return json.dumps(self._routes.load_objects(map_id), ensure_ascii=False)

    def _pick_map_for(self, missing):
        def pick(maps):
            labels = [f"{m['label']} ({m['id']})" for m in maps]
            choice = self._dialogs.ask_choice(
                t("native.dialog.routeMap"),
                t("native.dialog.routeMapPrompt", id=missing),
                labels,
            )
            return maps[labels.index(choice)] if choice is not None else None

        return pick

    def _import_doc(self, doc, done_code):
        """done_code is the notice for this source: one code per source rather than a {source}
        word, so that every language phrases the whole sentence and nothing is left in English."""
        doc, note = self._routes.prepare_import(doc, self._pick_map_for(doc["map"]))
        if doc is None:
            return None
        if note == "rescaled":
            self._notify("info", "route.rescaled")

        try:
            # route.too_large as well: a file just under the limit can come out past it once
            # it is written indented, and an import must not leave a file it cannot list.
            route_id = self._routes.store_new(doc)
        except AppError as e:
            self._notifier.from_error(e)
            return None
        except OSError as e:
            self._notify("error", "route.save_failed", reason=str(e))
            return None
        self._put_last(route_id)
        self._store.set_state(route=route_id)
        self._apply_route(doc)
        if self._windows.editor_visible():
            # Import and Paste code are editor buttons too. Left alone, the editor would keep
            # showing the route it had open while the new one is active everywhere else. The
            # page asks before dropping unsaved work, as it does for any route it is sent.
            self._request_editor(route_id, doc)
        self._notify("info", done_code, name=doc["name"])
        self._emit_state()
        return route_id

    @Slot(str)
    def exportRoute(self, route_id: str) -> None:
        doc = self._route_doc(route_id)
        if doc is None:
            return
        path = self._dialogs.save_json(t("native.dialog.saveRoute"), f"{route_id}.json")
        if not path:
            return
        try:
            self._routes.export_route(doc, path)
        except AppError as e:
            self._notifier.from_error(e)
            return
        except OSError as e:
            self._notify("error", "route.export_failed", reason=str(e))
            return
        self._notify("info", "route.exported", file=Path(path).name)

    @Slot()
    def importRouteFile(self) -> None:
        path = self._dialogs.open_json(t("native.dialog.openRoute"))
        if not path:
            return
        try:
            doc = self._routes.read_route_file(path)
        except AppError as e:
            self._notifier.from_error(e)
            return
        except OSError as e:
            self._notify("error", "route.file_invalid", reason=str(e))
            return
        self._import_doc(doc, "route.imported.file")

    @Slot(str)
    def copyRouteCode(self, route_id: str) -> None:
        doc = self._route_doc(route_id)
        if doc is None:
            return
        code = self._routes.encode_share(doc)
        self._dialogs.copy(code)
        self._notify("info", "share.copied", count=len(code))

    @Slot(str)
    def copyText(self, text: str) -> None:
        """Put a line the page shows, a wallet address, on the clipboard.

        QtWebEngine keeps the clipboard from scripts, so the page asks for it here.
        """
        if not isinstance(text, str) or not text or len(text) > _COPY_TEXT_MAX:
            log.warning("copyText refused a value of %s", type(text).__name__)
            return
        self._dialogs.copy(text)

    @Slot()
    def pasteRouteCode(self) -> None:
        try:
            doc = self._routes.decode_share(self._dialogs.paste())
        except AppError as e:
            self._notifier.from_error(e)
            return
        self._import_doc(doc, "route.imported.clipboard")

    # ------------------------------------------------------------------ updates
    @Slot()
    def checkForUpdates(self) -> None:
        self._updates.check()

    @Slot()
    def downloadUpdate(self) -> None:
        self._updates.download()

    @Slot(bool)
    def installUpdate(self, restart: bool) -> None:
        """true: apply now and restart. false: apply when the app closes, as it would anyway."""
        self._updates.install(bool(restart))

    @Slot(str)
    def skipUpdate(self, version: str) -> None:
        """Do not offer this version again; "" forgets the skip."""
        self._updates.skip(version)
        self._emit_state()  # the setting changed as well

    def _on_update_changed(self, payload: UpdatePayload) -> None:
        self.updateChanged.emit(json.dumps(payload, ensure_ascii=False))
        if payload["phase"] != self._update_phase:
            self._update_phase = payload["phase"]
            self._emit_state()

    def _before_update_exit(self) -> None:
        """Save and stop what an exit would, but keep the windows, in case the hand-over fails.

        Velopack ends the process inside its call, so nothing after it runs. If it succeeds,
        unsaved work in the route editor goes, as on an ordinary exit; if it fails, the app
        carries on with the engine stopped and every window ready to come back. A tile pyramid
        being cut is left to it: without its done.json it is cut again at the next start.
        """
        self._store.flush()
        self.engine.shutdown()  # waits for the thread, at most ENGINE_SHUTDOWN_WAIT_MS (2 s)
        self._windows.hide_all()
        self._store.flush()  # anything the stop above changed

    def _after_failed_update_exit(self) -> None:
        """The hand-over failed and the app carries on: put the steps plaque back if it was on.

        The overlay stays down with the engine, and the editor opens again on request, so the
        plaque is the one window whose absence the state would not explain.
        """
        self._sync_steps()
        self._emit_state()

    def hand_over_update(self) -> None:
        """The very end of the process: give a downloaded update to Update.exe (app.py main())."""
        self._updates.hand_over()

    def shutdown(self) -> None:
        # Before anything else: a debounced write that never lands is a lost setting.
        self._store.flush()
        self._screens.close()
        self._routes_folder.close()
        self._tiles.shutdown()
        self.engine.shutdown()
        self._overlay_error_shown += 1  # an error's timer still running must not reach the window
        # Disconnect before the overlay goes: a late transform from the dying thread would
        # otherwise arrive at a widget that is already being destroyed.
        with contextlib.suppress(RuntimeError, TypeError):
            self.engine.transformChanged.disconnect(self.overlay.set_transform)
        self._windows.shutdown()
        # No more checks. A downloaded update is not handed over here but in hand_over_update(),
        # after the event loop: Update.exe's wait for this process can be denied, and then it
        # applies at once, racing whatever of the exit is still to run.
        self._updates.close()

    def apply_language(self) -> None:
        """Point the catalogue at the chosen language and re-title what is already open.

        `auto` is resolved here rather than in i18n/catalog.py, so that module stays free of
        Qt; QLocale is the only thing that knows what the OS is set to. The UI resolves the
        same setting for itself from navigator.language, which agrees in every case that
        matters and needs no round trip.
        """
        set_language(resolve_language(self.settings.language, QLocale.system().name()))
        self._windows.retitle()
        # The control window is this object's Qt parent and owns its own title. Reaching it
        # by name would import the window back into the bridge, which is the cycle the
        # split was made to avoid.
        retitle = getattr(self.parent(), "retitle", None)
        if callable(retitle):
            retitle()
