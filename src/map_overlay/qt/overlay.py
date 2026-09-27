"""The transparent route window drawn over the game.

The route is drawn as vectors in screen pixels, so line thickness, arrow size and the
numbered circles stay constant however far the player has zoomed the game map in.
"""

import contextlib  # noqa: F401
import ctypes
import itertools
import sys

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

from map_overlay.i18n.catalog import t
from map_overlay.qt.win32 import (
    GWL_EXSTYLE,
    WS_EX_NOACTIVATE,
    WS_EX_TRANSPARENT,
    set_capture_affinity,
)

LINE_DARK = QColor(15, 17, 22, 200)  # outline under the coloured line, readable on any map
LABEL_TEXT = QColor(18, 20, 26)
END_COLOR = QColor("#4fd1c5")  # the last point of the route
MARKER_R = 11  # radius of the numbered circle, screen pixels
ARROW_L = 14  # arrow length along the segment
ARROW_W = 12  # arrow width across it
MIN_SEGMENT = 2 * ARROW_L  # no arrow is drawn on a very short segment
# Faded is how the part of the route away from the next steps is drawn, where it is drawn at
# all: without arrows, at this share of the overlay's opacity. Drawn whole and alike, a route
# that loops about a village was a tangle nobody could read the way on from.
FADED_OPACITY = 0.3


def marker_color(marker, route_color, index, total):
    own = marker.get("color")
    if own:
        return own
    return END_COLOR.name() if index == total - 1 and total > 1 else route_color


class ClickThroughWindow(QWidget):
    """Base for the windows drawn over the game: frameless, always on top, never focused.

    A fresh instance is click-through, so every mouse event still reaches the game. The two
    Windows-level modes it manages -- exclusion from screen capture, and input transparency --
    live on the HWND rather than on the QWidget, and Qt drops them whenever it rebuilds the
    HWND; a caller must therefore call `apply_capture_mode()` after every `show()`.

    Widgets: GUI thread only. The engine reaches these windows through queued signals.
    """

    def __init__(self) -> None:
        super().__init__()
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        if sys.platform != "win32":
            # Without WS_EX_TRANSPARENT the Qt flag is the only click-through there is.
            flags |= Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._opacity = 0.85
        self._recordable = False
        self._click_through = True

    def set_region(self, region) -> None:
        self.setGeometry(region["left"], region["top"], region["width"], region["height"])

    def set_opacity(self, value) -> None:
        self._opacity = float(max(0.0, min(1.0, value)))
        self.update()

    def set_recordable(self, recordable) -> None:
        self._recordable = bool(recordable)
        if self.isVisible():
            self.apply_capture_mode()

    def apply_capture_mode(self):
        """Re-apply both native modes; call after every `show()`, they do not survive it."""
        ok = set_capture_affinity(self, self._recordable)
        self.apply_input_mode()
        return ok

    def set_click_through(self, on) -> None:
        """Whether the mouse passes through the window.

        Switched through the native window style rather than `setWindowFlags`: on a visible
        window Qt hides it and builds a new HWND, and the capture affinity goes with the old
        one -- for a frame or two the engine would then see its own plaque on the map.
        """
        self._click_through = bool(on)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, self._click_through)
        if self.isVisible():
            self.apply_input_mode()
        self.update()

    def apply_input_mode(self):
        """Lives on the HWND like the capture affinity: call after every `show()`."""
        if sys.platform != "win32":
            self.setWindowFlag(Qt.WindowTransparentForInput, self._click_through)
            return False
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.restype = ctypes.c_long
        hwnd = int(self.winId())
        # NOACTIVATE stays on always: clicking an unpinned plaque must not pull the player
        # out of the game.
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_NOACTIVATE
        if self._click_through:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        return bool(user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style))


class OverlayWindow(ClickThroughWindow):
    """Draws the active route over the game map.

    Route points are held in reference-map pixels and run through the homography last given
    to `set_transform()` on every repaint, which is what makes the route follow the map as the
    player pans and zooms. Nothing is drawn until both a route and a transform have arrived.

    The engine delivers transforms from a worker thread through a queued signal; every setter
    here runs on the GUI thread and must not be called from a worker directly.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("native.window.overlay"))
        self._pts = None  # route points in reference-map pixels, (N, 1, 2) float32
        self._color = QColor("#f2b544")
        self._colors = []  # one colour per marker, indexed over the whole route
        self._width = 3
        self._doc_scale = np.eye(3)
        self._M = None  # reference map -> capture region
        self._done = 0  # markers already passed, counted from the start of the route
        self._radius = 0.0  # arrival radius in route coordinates; 0 draws no ring
        self._faded = None  # QImage the faded part is drawn into, kept between frames
        self._view = ("steps", 3, 3)  # Settings.route_view, route_ahead, route_past

    def set_progress(self, done) -> None:
        done = max(0, int(done))
        if done != self._done:
            self._done = done
            self.update()

    def set_view(self, mode, ahead, past) -> None:
        """How much of the route to draw; see Settings.route_view."""
        view = (mode, max(1, int(ahead)), max(0, int(past)))
        if view != self._view:
            self._view = view
            self.update()

    def set_route(self, doc, ref_size=None, arrive_radius=0.0) -> None:
        """Replace the drawn route.

        Args:
            doc: route document (see `store.routes`); empty or without markers clears it.
            ref_size: reference map size as (w, h).
            arrive_radius: arrival radius as a fraction of the map width.
        """
        if not doc or not doc.get("markers"):
            self._pts = None
            self._colors = []
        else:
            markers = doc["markers"]
            base = doc["style"]["color"]
            points = [[m["x"], m["y"]] for m in markers]
            self._pts = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
            self._color = QColor(base)
            self._width = int(doc["style"]["width"])
            self._colors = [
                QColor(marker_color(m, base, i, len(markers))) for i, m in enumerate(markers)
            ]
        # The route may have been drawn on a map image of another resolution: bring its
        # coordinates up to the reference size before anything else uses them.
        self._doc_scale = np.eye(3)
        mw = (doc.get("mapSize") or [0, 0])[0] if doc else 0
        if doc and ref_size:
            mh = doc["mapSize"][1]
            if mw > 0 and mh > 0:
                self._doc_scale = np.diag([ref_size[0] / mw, ref_size[1] / mh, 1.0])
        # The radius arrives as a fraction of the map; convert it into the same coordinates
        # the route points use.
        self._radius = float(arrive_radius) * mw
        self.update()

    def set_transform(self, transform) -> None:
        """transform: reference -> region matrix (numpy 3x3), or None."""
        new = None if transform is None else np.asarray(transform, dtype=float) @ self._doc_scale
        if new is None and self._M is None:
            return
        self._M = new
        self.update()

    def paintEvent(self, _event) -> None:
        if self._M is None or self._pts is None:
            return
        done = self._done
        total = len(self._pts)
        if done >= total:
            return
        mode, ahead, past = self._view
        bright = total if mode == "all" else min(total, done + ahead)  # past the last bright one
        first, last = (max(0, done - past), bright) if mode == "steps" else (0, total)
        window = self._pts[first:last]
        pts = cv2.perspectiveTransform(window, self._M.astype(np.float32)).reshape(-1, 2)
        if not np.all(np.isfinite(pts)):
            return
        margin = 100
        inside = (
            (pts[:, 0] > -margin)
            & (pts[:, 0] < self.width() + margin)
            & (pts[:, 1] > -margin)
            & (pts[:, 1] < self.height() + margin)
        )
        # A route just past the edge still draws lines and arrows across the region, so give
        # up only once every point is well outside it.
        if not inside.any():
            return

        k = done - first  # where the next point is in `pts`
        b = bright - first
        # (points, the route index of the first, how many of them go without a circle): what
        # lies beyond the bright steps goes on from the last of them, whose circle is bright
        faded = []
        if b < len(pts):
            faded.append((pts[b - 1 :], bright - 1, 1))
        if k > 0:
            faded.append((pts[:k], first, 0))  # after, so the steps passed lie on top
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if faded:
            p.setOpacity(self._opacity * FADED_OPACITY)
            p.drawImage(0, 0, self._draw_faded(faded))
        p.setOpacity(self._opacity)
        self._draw_target(p, pts[k])
        # The way on starts at the last point passed: the leg being walked is the first step.
        # It leaves that point's faded circle from the edge, not from under it.
        ahead = max(k - 1, 0)
        way = pts[ahead:b].copy()
        if k > 0:
            d = way[1] - way[0]
            length = float(np.hypot(*d))
            if length > MARKER_R:
                way[0] += d / length * MARKER_R
        self._draw_legs(p, way, first + ahead - done)
        self._draw_markers(p, pts[k:b], done)
        p.end()

    def _draw_faded(self, parts):
        """The faded runs of the route, drawn in full into a layer of their own, without arrows.

        The layer is then laid on the window faded as a whole. Faded leg by leg instead, every
        outline showed through the colour over it and every crossing came out darker.
        """
        ratio = self.devicePixelRatioF()
        size = self.size() * ratio
        if self._faded is None or self._faded.size() != size:
            self._faded = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
            self._faded.setDevicePixelRatio(ratio)
        self._faded.fill(Qt.GlobalColor.transparent)
        p = QPainter(self._faded)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for pts, first, bare in parts:
            self._draw_legs(p, pts, first - self._done, arrows=False)
            self._draw_markers(p, pts[bare:], first + bare)
        p.end()
        return self._faded

    def _color_at(self, index):
        """Colour by the marker's place in the whole route, not in the remaining tail."""
        if 0 <= index < len(self._colors):
            return self._colors[index]
        return self._color

    def leg_color(self, leg):
        """The colour of the remaining route's `leg`-th leg: that of the point it leads to.

        The way to a side quest is green as the point is, the way to the end teal: running a
        leg, the line and its arrow say what waits at the end of it.
        """
        return self._color_at(self._done + leg + 1)

    def _draw_target(self, p, point) -> None:
        """Ring around the nearest marker: stepping inside it is what marks that marker done."""
        if self._radius <= 0:
            return
        # Only paintEvent calls this, and it has returned already when there is no transform.
        scale = float(np.hypot(self._M[0, 0], self._M[1, 0]))  # pyright: ignore[reportOptionalSubscript]
        r = self._radius * scale
        # Too small to read, or the map is zoomed out so far the ring says nothing.
        if not (MARKER_R * 1.5 < r < 4000):
            return
        pen = QPen(self._color_at(self._done), 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 4])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setOpacity(self._opacity * 0.65)
        p.drawEllipse(QPointF(*point), r, r)
        p.setOpacity(self._opacity)

    def _draw_legs(self, p, pts, first_leg=0, arrows=True) -> None:
        """Each leg in the colour of the point it leads to, with a chevron in its middle.

        `pts` begins where the remaining route's `first_leg`-th leg does, which is what the
        colours are counted from; the leg into the next point is -1, a leg passed is lower.

        Legs go down from the end of the route back to the next point, each in its own dark
        outline with its chevron, so where the route crosses itself the leg the player walks
        first lies on top and its outline cuts through the later one. Drawn in route order, a
        leg for later hid the one being walked.
        """
        p.setBrush(Qt.BrushStyle.NoBrush)
        legs = list(enumerate(itertools.pairwise(pts)))
        for leg, (a, b) in reversed(legs):
            color = self.leg_color(first_leg + leg)
            line = QPainterPath(QPointF(*a))
            line.lineTo(QPointF(*b))
            self._stroke(p, line, color)
            arrow = self._arrow(a, b) if arrows else None
            if arrow is not None:
                self._stroke(p, arrow, color)

    def _stroke(self, p, path, color) -> None:
        """The dark outline, then the colour over it."""
        for pen_color, width in ((LINE_DARK, self._width + 3), (color, self._width)):
            p.setPen(self._line_pen(pen_color, width))
            p.drawPath(path)

    @staticmethod
    def _line_pen(color, width):
        return QPen(
            color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        )

    @staticmethod
    def _arrow(a, b):
        """The chevron in the middle of a leg, so the direction of travel is visible: an open V
        drawn as the line is, a dark outline under the colour. None on a leg too short for it."""
        d = b - a
        length = float(np.hypot(*d))
        if length < MIN_SEGMENT:
            return None
        d = d / length
        n = np.array([-d[1], d[0]])
        mid = (a + b) / 2
        tip = mid + d * (ARROW_L / 2)
        back = mid - d * (ARROW_L / 2)
        path = QPainterPath(QPointF(*(back + n * (ARROW_W / 2))))
        path.lineTo(QPointF(*tip))
        path.lineTo(QPointF(*(back - n * (ARROW_W / 2))))
        return path

    def _draw_markers(self, p, pts, offset=0) -> None:
        # The application font rather than one named outright: the numbers must not turn into
        # boxes on a system without Segoe UI.
        font = QFont(p.font())
        font.setBold(True)
        # Last to first, like the legs: of two points on one spot -- a teleport the route comes
        # back to -- the one due first is on top.
        for i, (x, y) in reversed(list(enumerate(pts))):
            p.setPen(QPen(LINE_DARK, 2))
            p.setBrush(self._color_at(offset + i))
            p.drawEllipse(QPointF(x, y), MARKER_R, MARKER_R)
            # Numbering does not shift as the route shortens: the fifth marker stays "5".
            label = str(offset + i + 1)
            font.setPixelSize(15 if len(label) < 2 else (12 if len(label) == 2 else 9))
            p.setFont(font)
            p.setPen(LABEL_TEXT)
            p.drawText(
                QRectF(x - MARKER_R, y - MARKER_R, MARKER_R * 2, MARKER_R * 2),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

    def retitle(self) -> None:
        """Re-read the title after a language change; see WindowManager.retitle."""
        self.setWindowTitle(t("native.window.overlay"))


def primary_screen_geometry():
    return QApplication.primaryScreen().geometry()
