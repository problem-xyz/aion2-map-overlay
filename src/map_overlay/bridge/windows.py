"""Owns every window drawn over the game, and the region picker.

Backend used to hold these directly, which meant "hide the overlay, pick a region, put it all
back" was spread over three methods that each knew what the others had done. Here it is one
object with the before/after state in one place.

Two lifetime rules are load-bearing, both learned from crashes:
  * a window is never deleted from inside its own signal emission -- deleteLater is called
    from a connected slot, after the emission has unwound;
  * a page's channel never outlives the object registered on it, or QWebChannel keeps calling
    into a half-destroyed object: the editor's page is detached from Backend before the window
    goes, and the plaque's page goes together with its own bridge object.
"""

import logging

from PySide6.QtCore import QObject, Signal

from map_overlay.qt.editor_window import EditorWindow
from map_overlay.qt.overlay import OverlayWindow, primary_screen_geometry
from map_overlay.qt.region_selector import RegionSelector
from map_overlay.qt.steps_window import WebStepsWindow

log = logging.getLogger(__name__)

# How long the editor page gets to answer __requestClose before the window is closed anyway.
EDITOR_CLOSE_TIMEOUT_MS = 1000


class WindowManager(QObject):
    """Owns the overlay, the steps plaque, the editor window and the region picker.

    It owns their lifetimes as well as the objects: a caller reaches a window through the
    properties and must never close, delete or re-parent one itself -- the two rules above
    are enforced here and nowhere else. shutdown() is the one place a window is destroyed.

    Nothing here reads settings or state; every value a window needs arrives as an argument,
    which is why the methods take opacity, region and radius rather than looking them up.

    GUI thread only.
    """

    regionPicked = Signal(dict)
    pickFinished = Signal()

    def __init__(self, dev=False, parent=None) -> None:
        super().__init__(parent)
        self.dev = bool(dev)
        self.overlay = OverlayWindow()
        self.steps = WebStepsWindow(dev)
        self._selector = None
        self._editor = None

    def retitle(self) -> None:
        """Re-read every window title after a language change.

        A title is set once in a constructor, so nothing would pick a new language up on its
        own. The plaque also gets a data push: the page renders its own text and is told which
        language to use through dataChanged, not through getState.
        """
        self.overlay.retitle()
        self.steps.retitle()
        if self._editor is not None:
            self._editor.retitle()
        if self._selector is not None:
            self._selector.retitle()

    # ------------------------------------------------------------------ region picking
    @property
    def picking(self):
        return self._selector is not None

    def pick_region(self, prompt, on_picked, keep_overlay) -> None:
        """Dim the screen and let the user drag a rectangle.

        keep_overlay is a callable, not a flag: whether the overlay comes back depends on
        whether the engine is still running once the user is done, which can take a while.
        """
        if self._selector is not None:
            return
        was_overlay = self.overlay.isVisible()
        was_steps = self.steps.isVisible()
        self.overlay.hide()
        self.steps.hide()

        selector = RegionSelector(primary_screen_geometry(), prompt)
        self._selector = selector

        def done(region=None) -> None:
            # Drop the reference from a slot, not from inside the selector's own emission.
            self._selector = None
            selector.deleteLater()
            if region:
                on_picked(region)
                self.regionPicked.emit(region)
            if was_overlay and keep_overlay():
                self.overlay.show()
                self.overlay.apply_capture_mode()
            if was_steps:
                self.steps.show()
                self.steps.apply_capture_mode()
            self.pickFinished.emit()

        selector.selected.connect(done)
        selector.cancelled.connect(lambda: done(None))
        selector.show()
        selector.activateWindow()
        selector.raise_()

    # ------------------------------------------------------------------ route display
    def apply_route(self, doc, *, ref_size, arrive_radius, steps, done, name) -> None:
        """Hand the route to both windows over the game."""
        self.overlay.set_route(doc, ref_size, arrive_radius)
        self.overlay.set_progress(done)
        self.steps.set_steps(steps, done, name)

    def apply_progress(self, steps, done, name) -> None:
        self.overlay.set_progress(done)
        self.steps.set_steps(steps, done, name)

    def sync_steps(self, visible, region, opacity):
        """Show or hide the plaque. Returns the region to persist, or None.

        The plaque keeps its size within the screen, so the region it ends up with need not be
        the one it was given. That value is handed back rather than written here: this is
        called several times a second from the progress path.
        """
        if not visible or not self.steps.has_steps():
            self.steps.hide()
            return None
        region = region or self.steps.default_region()
        self.steps.set_region(region)
        self.steps.set_opacity(opacity)
        self.steps.show()
        self.steps.apply_capture_mode()
        return self.steps.region_dict()

    # ------------------------------------------------------------------ editor
    @property
    def editor(self):
        return self._editor

    def editor_visible(self):
        return bool(self._editor and self._editor.isVisible())

    def ensure_editor(self, backend, url, scale):
        if self._editor is None:
            self._editor = EditorWindow(backend, url, scale)
        return self._editor

    def raise_editor(self, backend, url, scale):
        """Show the editor and bring it to the front, un-minimising if needed."""
        from PySide6.QtCore import Qt  # noqa: PLC0415 -- only needed for this one flag

        window = self.ensure_editor(backend, url, scale)
        window.show()
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
        window.raise_()
        window.activateWindow()
        return window

    def show_overlay(self, region, opacity) -> None:
        self.overlay.set_region(region)
        self.overlay.set_opacity(opacity)
        self.overlay.show()
        self.overlay.apply_capture_mode()

    def close_editor(self) -> None:
        if self._editor:
            self._editor.hide()

    # ------------------------------------------------------------------ shutdown
    def hide_all(self) -> None:
        """Take every window off the screen and keep it, pages and channels included.

        For an update about to end the process: should the hand-over fail, the app carries on,
        and every window, the editor with its unsaved work, can come back as it was. The plaque
        is shown again by sync_steps(), the editor on the next request to open it.
        """
        self.close_editor()
        self.steps.hide()
        self.overlay.hide()

    def shutdown(self) -> None:
        if self._selector is not None:
            selector, self._selector = self._selector, None
            selector.close()
            selector.deleteLater()
        if self._editor:
            self._editor.force_close()
            self._editor = None
        # The plaque is deleted, not detached. Its channel and the bridge object it serves both
        # die with the window, page first, so nothing is left calling into a half-destroyed
        # object. Detaching a page that is still loading is itself a crash: an access violation
        # in Qt6WebEngineCore.dll on the next processEvents (measured in the test suite, which
        # builds a Backend per test, about one run in four). Left to the garbage collector
        # instead, the window went whenever Python got to it, as the next page was loading.
        self.steps.close()
        self.steps.deleteLater()
        self.overlay.close()
        self.overlay.deleteLater()
