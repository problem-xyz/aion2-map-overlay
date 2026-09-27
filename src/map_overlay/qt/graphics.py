"""The graphics API every window draws through."""

import logging
import os

from PySide6.QtGui import QOffscreenSurface, QOpenGLContext
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

log = logging.getLogger(__name__)

# Qt's own switch. Set, it wins over the choice made here.
BACKEND_ENV = "QSG_RHI_BACKEND"

GL_RENDERER = 0x1F01
GL_VERSION = 0x1F02


def choose_graphics_api(allow_opengl: bool = True) -> str:
    """Draw the web views through OpenGL rather than Qt's Windows default, Direct3D 11.

    On Direct3D 11, Qt WebEngine hands each frame Chromium draws to Qt as a shared texture, and
    Qt can put it on screen before Chromium has finished drawing it. A fast zoom in the editor
    tore the map into black staircases and blinked the whole page, and it lagged. The page's
    own frames were clean, at a steady 60 fps. Through OpenGL the same page shows neither.

    Runs after the QApplication, which the test context needs, and before the first window,
    after which Qt no longer takes a choice. QSG_RHI_BACKEND stays in charge when it is set, so
    a machine can be put back on d3d11 to compare. Where no OpenGL 2 context can be made at
    all, Direct3D 11 stays: a map that flickers beats a window that draws nothing.

    allow_opengl=False keeps Direct3D 11 as well, for a machine whose driver crashed the app on
    OpenGL (see core/crash_guard.py).

    Returns what was chosen, as QSG_RHI_BACKEND spells it.
    """
    forced = os.environ.get(BACKEND_ENV)
    if forced:
        log.info("graphics: %s, from %s", forced, BACKEND_ENV)
        return forced
    if not allow_opengl:
        log.warning("graphics: d3d11, after a crash in the graphics driver on opengl")
        return "d3d11"
    probe = QOpenGLContext()
    if not probe.create() or probe.format().majorVersion() < 2:
        log.warning("graphics: no usable OpenGL context, staying on Direct3D 11")
        return "d3d11"
    fmt = probe.format()
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    log.info(
        "graphics: opengl %d.%d on %s", fmt.majorVersion(), fmt.minorVersion(), _renderer(probe)
    )
    return "opengl"


def _renderer(context: QOpenGLContext) -> str:
    """The GPU and its driver version, as the driver names them.

    A crash inside a graphics driver is reported by the DLL's name alone, and the driver
    version is what decides whether it is ours to work around.
    """
    surface = QOffscreenSurface()
    surface.create()
    if not context.makeCurrent(surface):
        return "an unnamed renderer"
    try:
        gl = context.functions()
        return f"{gl.glGetString(GL_RENDERER)}, {gl.glGetString(GL_VERSION)}"
    finally:
        context.doneCurrent()
