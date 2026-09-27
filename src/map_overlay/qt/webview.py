"""Loading the React UI into a QWebEngineView and wiring the QWebChannel to it."""

import ctypes
import functools
import logging
import sys

from PySide6.QtCore import QFile, QIODevice, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineSettings

from map_overlay.core.paths import resource_path

DEV_URL = "http://localhost:5173"
log = logging.getLogger(__name__)
_ui_log = logging.getLogger("ui")

# The client half of QWebChannel, compiled into Qt6WebChannel.dll. The page gets it from there
# rather than from its own bundle, so it stays part of the Qt libraries, which the LGPL lets a
# user replace (THIRD-PARTY-NOTICES) and which it always matches in version.
QWEBCHANNEL_JS = ":/qtwebchannel/qwebchannel.js"

BACKGROUND = QColor("#1c2029")


def ui_dist():
    return resource_path("ui/dist/index.html")


def ui_url(dev, fragment=""):
    """URL of the UI: the Vite dev server, or the built file.

    One page serves every window; `fragment` is what picks the mode it starts in
    ("steps", "editor", empty for the control panel).
    """
    url = QUrl(DEV_URL) if dev else QUrl.fromLocalFile(str(ui_dist()))
    if fragment:
        url.setFragment(fragment)
    return url


def system_dpi_scale():
    """The Windows desktop scale (1.0, 1.25, 1.5...).

    Qt's own HiDPI scaling is switched off at startup so that capture and overlay coordinates
    stay in physical pixels; window sizes and the page zoom have to be scaled by hand here, or
    every window comes up tiny on a HiDPI monitor.
    """
    if sys.platform != "win32":
        return 1.0
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except Exception:  # noqa: BLE001
        return 1.0


# QWebEnginePage severities, mapped onto ours.
_JS_LEVELS = {
    QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: logging.INFO,
    QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: logging.WARNING,
    QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: logging.ERROR,
}


class LoggingPage(QWebEnginePage):
    """Page console messages go to the log; otherwise UI errors are invisible in a build."""

    def javaScriptConsoleMessage(self, level, message, line, source) -> None:
        name = str(source).rsplit("/", 1)[-1] or "page"
        _ui_log.log(_JS_LEVELS.get(level, logging.INFO), "%s:%s %s", name, line, message)


@functools.cache
def _qwebchannel_source() -> str | None:
    file = QFile(QWEBCHANNEL_JS)
    if not file.open(QIODevice.OpenModeFlag.ReadOnly):
        return None
    try:
        return bytes(file.readAll().data()).decode("utf-8")
    finally:
        file.close()


def qwebchannel_script() -> QWebEngineScript | None:
    """Qt's qwebchannel.js, run before the page's own scripts so that they find `QWebChannel`.

    None when Qt has no such resource, which only a broken Qt swapped in by hand can cause: the
    page then reports backend.channelFailed rather than the app failing to open a window.
    """
    source = _qwebchannel_source()
    if source is None:
        log.error("%s is missing from Qt WebChannel; the UI cannot reach Python", QWEBCHANNEL_JS)
        return None
    script = QWebEngineScript()
    script.setName("qwebchannel")
    script.setSourceCode(source)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(False)
    return script


def prepare_page(view, background):
    """Give a view a logging page with the settings every window here needs.

    All three windows load the UI over file://, and a file:// page may not read another local
    file unless LocalContentCanAccessFileUrls is set -- which is how the editor reaches map
    tiles. The plaque used to build its page separately and silently lacked the attribute, so
    this exists to keep the three from drifting apart again. The background differs per window,
    so it stays a parameter.
    """
    view.setPage(LoggingPage(view))
    page = view.page()
    page.settings().setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
    )
    page.setBackgroundColor(background)
    script = qwebchannel_script()
    if script is not None:
        page.scripts().insert(script)
    return page


def attach_backend(view, backend):
    """Wire a view to the backend over a channel of its own.

    A QWebChannel belongs to a single page, so every window gets one; the backend object
    itself is shared by all of them.
    """
    page = prepare_page(view, BACKGROUND)
    channel = QWebChannel(page)
    channel.registerObject("backend", backend)
    page.setWebChannel(channel)
    return channel
