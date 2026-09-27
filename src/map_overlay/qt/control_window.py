"""The control panel window."""

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import resource_path
from map_overlay.i18n.catalog import t
from map_overlay.qt.webview import attach_backend, system_dpi_scale, ui_dist, ui_url

UI_NOT_BUILT = (
    "<body style='font-family:Segoe UI;padding:24px;color:#ddd;background:#14161c'>"
    "<h3>{title}</h3><p>{body}</p>"
    "<pre>cd ui\nnpm ci\nnpm run build</pre>"
    "<p>{hint}</p></body>"
)

# The panel opens at this size and cannot be made smaller: the size the owner settled on, where
# every section lays out without a squeeze. Physical pixels at a desktop scale of 100%.
PANEL_SIZE = (600, 940)
TITLE_BAR = 40  # about what Windows adds above the client area, which is what resize() sets


class ControlWindow(QMainWindow):
    """The control panel, and with it the lifetime of everything the app shows.

    Closing this window shuts the `Backend` down -- the engine thread, the overlay, the steps
    plaque and the editor all hang off it -- so it is the app's exit path, not one window
    among several. It is created once, in `app.py`, and owns the backend as its Qt parent.

    Sizes here are multiplied by the desktop scale by hand: Qt's HiDPI scaling is off, so a
    figure in this file is a physical pixel count.
    """

    def __init__(self, backend: Backend, dev: bool) -> None:
        super().__init__()
        self.backend = backend
        self.setWindowTitle(t("native.window.control"))
        # The PNG, not packaging/icon.ico: that one is stamped into the exe by PyInstaller and is
        # never shipped as a file, while a QIcon needs an image Qt can read at runtime.
        self.setWindowIcon(QIcon(str(resource_path("assets/icon.png"))))
        scale = system_dpi_scale()
        width, height = (int(side * scale) for side in PANEL_SIZE)
        # On a screen too small for it, the window takes the whole screen, so it still fits
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            room = screen.availableGeometry()
            width, height = min(width, room.width()), min(height, room.height() - TITLE_BAR)
        self.resize(width, height)
        self.setMinimumSize(width, height)

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.channel = attach_backend(self.view, backend)
        self.view.setZoomFactor(scale)

        if dev or ui_dist().exists():
            self.view.setUrl(ui_url(dev))
        else:
            self.view.setHtml(
                UI_NOT_BUILT.format(
                    title=t("native.uiNotBuilt.title"),
                    body=t("native.uiNotBuilt.body"),
                    hint=t("native.uiNotBuilt.hint"),
                )
            )

    def closeEvent(self, event) -> None:
        self.backend.shutdown()
        super().closeEvent(event)

    def retitle(self) -> None:
        """Re-read the title after a language change.

        The product name is the same in every catalogue today, so this changes nothing on
        screen -- but the title is a translated string like any other, and leaving it out
        would make this the one window that silently stops following the setting.
        """
        self.setWindowTitle(t("native.window.control"))
