"""The route editor window: the same built page, opened in #editor mode."""

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from map_overlay.i18n.catalog import t
from map_overlay.qt.webview import attach_backend

log = logging.getLogger(__name__)

# The page is asked whether it has unsaved work. If its answer never comes -- a script error,
# a page that never finished loading -- the window must still close.
CLOSE_TIMEOUT_MS = 1000

# Truthy once the page has taken the close over: closed the window, or put its question up.
REQUEST_CLOSE_JS = "!!(window.__requestClose && window.__requestClose())"


class EditorWindow(QMainWindow):
    """The route editor: the built page again, opened in its `#editor` mode.

    Built once and hidden rather than destroyed, so the page keeps its state between openings.
    Closing it is a request, not an order: the close event is ignored, the page is asked about
    unsaved work and answers by calling `closeEditor()` back through the bridge.
    `force_close()` is the shutdown path and skips the question.
    """

    def __init__(self, backend, url, scale=1.0) -> None:
        super().__init__()
        self.setWindowTitle(t("native.window.editor"))
        self.resize(int(1280 * scale), int(860 * scale))
        self.setMinimumSize(int(900 * scale), int(600 * scale))

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.channel = attach_backend(self.view, backend)
        self.view.setZoomFactor(scale)
        self._loaded = False
        self._force = False
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(CLOSE_TIMEOUT_MS)
        self._close_timer.timeout.connect(self._close_if_still_open)
        self._page_titled = False
        self.view.loadFinished.connect(self._on_loaded)
        self.view.titleChanged.connect(self._on_title)
        self.view.setUrl(url)

    def _on_loaded(self, ok) -> None:
        self._loaded = bool(ok)

    def _on_title(self, title) -> None:
        if title and not title.lower().startswith("http"):
            self._page_titled = True
            self.setWindowTitle(title)

    def force_close(self) -> None:
        """Application is going down: too late to ask about unsaved work.

        The channel is detached first. QWebChannel keeps a reference to the registered object
        and will call into it while the page tears down, which is a crash if the window has
        already been deleted. deleteLater is deferred to the next event-loop turn for the
        same reason: this can be reached from inside a signal from the window itself.
        """
        self._force = True
        page = self.view.page()
        if self.channel is not None:
            # Qt takes nullptr here to detach; PySide6's stubs do not allow None.
            page.setWebChannel(None)  # pyright: ignore[reportArgumentType]
            self.channel = None
        self.close()
        QTimer.singleShot(0, self.deleteLater)

    def closeEvent(self, event) -> None:
        """The page asks about unsaved work itself and calls closeEditor() back.

        The timer is for a page that never answers, not for a user who has not answered yet:
        once the page reports it has taken the close over, the question stays up as long as
        the user needs.
        """
        if self._force:
            super().closeEvent(event)
            return
        event.ignore()
        if not self._loaded:
            self.hide()
            return
        # If the page never answers, hide anyway rather than trapping the user in a window
        # that will not close.
        self._close_timer.start()
        self.view.page().runJavaScript(REQUEST_CLOSE_JS, self._on_close_answer)

    def _on_close_answer(self, handled) -> None:
        if handled:
            self._close_timer.stop()

    def _close_if_still_open(self) -> None:
        if self.isVisible() and not self._force:
            log.warning("editor page did not answer __requestClose in %d ms", CLOSE_TIMEOUT_MS)
            self.hide()

    def retitle(self) -> None:
        """Re-read the title, unless the page owns it.

        Once loaded, the page sets the title itself through titleChanged -- it knows the
        route name and the unsaved marker. Its own text re-renders on a language change and
        pushes a new title, so overwriting it here would only flicker the old one back.
        """
        if not self._page_titled:
            self.setWindowTitle(t("native.window.editor"))
