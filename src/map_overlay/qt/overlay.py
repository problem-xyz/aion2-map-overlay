"""The transparent route window drawn over the game.

The route is drawn as vectors in screen pixels, so line thickness, arrow size and the
numbered circles stay constant however far the player has zoomed the game map in.
"""

import contextlib  # noqa: F401
import ctypes
import itertools
import sys
import time

import cv2
import numpy as np
from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

from map_overlay.i18n.catalog import t
from map_overlay.qt.webview import system_dpi_scale
from map_overlay.qt.win32 import (
    GWL_EXSTYLE,
    WS_EX_NOACTIVATE,
    WS_EX_TRANSPARENT,
    set_capture_affinity,
)
from map_overlay.store.resources import resource_svg

LINE_DARK = QColor(15, 17, 22, 200)  # outline under the coloured line, readable on any map
LABEL_TEXT = QColor(18, 20, 26)
END_COLOR = QColor("#4fd1c5")  # the last point of the route
MARKER_R = 11  # radius of the numbered circle, screen pixels
ARROW_L = 14  # arrow length along the segment
ARROW_W = 12  # arrow width across it
MIN_SEGMENT = 2 * ARROW_L  # no arrow is drawn on a very short segment
POINTER_L = 12  # the pointer to a next point off the map area: how far it reaches past the circle
POINTER_W = 14  # and how wide it is at the circle
# Faded is how the part of the route away from the next steps is drawn, where it is drawn at
# all: without arrows, at this share of the overlay's opacity. Drawn whole and alike, a route
# that loops about a village was a tangle nobody could read the way on from.
FADED_OPACITY = 0.3
# The hidden cube as the panel draws it (markIcons.ts): a coral cube from above a corner, the lit
# top palest. CUBE_HALF is half its height in pixels at 100% Windows scale. The cubes, their rings
# and the gathering points are all multiplied by system_dpi_scale(), as the strip's type is: at
# 150% on a 4K screen they were too small to make out over the game.
CUBE_TOP = QColor("#f4a08c")
CUBE_LEFT = QColor("#d9624f")
CUBE_RIGHT = QColor("#a83a2f")
CUBE_INK = QColor("#3a0c08")
CUBE_HALF = 12
CUBE_RING = QColor("#ff7a5c")
# The arrow beside a cube above or below the ground about it: up at its top right corner, down at
# its bottom right. LEVEL_SIDE is the arrow's side and LEVEL_X how far right of the cube's middle
# it starts, in pixels at 100% Windows scale.
LEVEL_SIDE = 11
LEVEL_X = 8
LEVEL_FILL = QColor("#f2f4f8")
# A gathering point: its resource's drawing (assets/marks/resources.json) on a dark disc, which
# keeps it apart from the game's own map. RESOURCE_HALF is half its side at 100% Windows scale.
RESOURCE_HALF = 13.5
RESOURCE_DISC = QColor(15, 17, 22, 130)
# The strip along the bottom of the map area that tells the player what the overlay is doing. A
# map lost for less than NOTICE_DELAY_S goes unannounced: detection drops it for a frame or two all
# the time, and a strip blinking over the map is worse than none. Past HINT_DELAY_S it says what to
# do about it.
NOTICE_DELAY_S = 1.5
HINT_DELAY_S = 6.0
# A line too long for the strip runs along it: it stands MARQUEE_PAUSE_S first, so its start can be
# read, then moves at MARQUEE_SPEED px a second, round and round with MARQUEE_GAP px between runs.
MARQUEE_PAUSE_S = 1.5
MARQUEE_SPEED = 50.0
MARQUEE_GAP = 60
MARQUEE_FRAME_MS = 33
# The strip's type, in pixels at 100% Windows scale; system_dpi_scale() multiplies them, since Qt's
# own scaling is off and nothing else would. At 150% on a 4K screen 13 px could not be read.
NOTICE_TITLE_PX = 15
NOTICE_TEXT_PX = 14
NOTICE_BG = QColor(15, 17, 22, 225)
NOTICE_BORDER = QColor(255, 255, 255, 36)
NOTICE_TITLE = QColor("#f2f4f8")
NOTICE_TEXT = QColor("#aeb6c4")
SEARCH_COLOR = QColor("#f2b544")
ERROR_COLOR = QColor("#ef5b5b")
FAR_COLOR = QColor("#6ea8ff")


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
        self._T = None  # reference map -> capture region, as the engine sent it
        self._M = None  # route coordinates -> capture region: _T after _doc_scale
        self._route_on = True  # the panel's Arrows switch; the cubes have their own
        self._cubes = None  # hidden cubes in reference-map pixels, (N, 1, 2) float32
        self._cube_radius = 0
        self._cube_levels = None  # each cube's level: 1 above the ground, -1 below, 0 neither
        self._cube_sprite = None  # QImage of one cube, drawn once per device pixel ratio
        self._level_sprites: dict[int, QImage] = {}  # the arrow up (1) and down (-1), as the cube's
        # gathering points by resource, in reference-map pixels, (N, 1, 2) float32 each
        self._resources: dict[str, np.ndarray] = {}
        self._resource_sprites: dict[str, QImage | None] = {}  # one per resource, as the cube's
        self._done = 0  # markers already passed, counted from the start of the route
        self._radius = 0.0  # arrival radius in route coordinates; 0 draws no ring
        self._faded = None  # QImage the faded part is drawn into, kept between frames
        self._view = ("steps", 3, 3)  # Settings.route_view, route_ahead, route_past
        self._lost_at = time.monotonic()  # since when there is no transform
        self._error = None  # (title, detail) the run ended with, shown until cleared
        self._far = None  # (title, detail) while the player is far off the route
        self._covered = (
            0  # how much of the bottom a question window takes, which no strip sits under
        )
        self._marquee = None  # (title, detail) the running line is of, and since when it runs
        self._marquee_since = 0.0
        self._ui_scale = system_dpi_scale()
        # Repaints the running line. Only while one runs: an idle overlay draws nothing at all.
        self._marquee_timer = QTimer(self)
        self._marquee_timer.setInterval(MARQUEE_FRAME_MS)
        self._marquee_timer.timeout.connect(self.update)

    def show_error(self, title, detail) -> None:
        """Say why the run ended, in place of the route, until clear_error()."""
        self._error = (str(title), str(detail))
        self.update()

    def clear_error(self) -> None:
        if self._error is not None:
            self._error = None
            self.update()

    def set_far(self, notice) -> None:
        """(title, detail) to say the player is far off the route, or None once they are not."""
        notice = None if notice is None else (str(notice[0]), str(notice[1]))
        if notice != self._far:
            self._far = notice
            self.update()

    def set_covered(self, height) -> None:
        """A question window over the bottom `height` px of the map area; 0 once it is gone.

        The strip it covers is not drawn, nor the pointer under it.
        """
        height = max(0, int(height))
        if height != self._covered:
            self._covered = height
            self.update()

    def has_error(self) -> bool:
        return self._error is not None

    def _map_lost(self) -> None:
        self._lost_at = time.monotonic()
        # The strip is due later: wake up to draw it then, and its hint after it.
        for delay in (NOTICE_DELAY_S, HINT_DELAY_S):
            QTimer.singleShot(int(delay * 1000) + 50, self, self.update)

    def showEvent(self, event) -> None:
        if self._T is None:
            self._map_lost()
        super().showEvent(event)

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

    def set_route_visible(self, visible) -> None:
        """Whether the route is drawn. The cubes and resources are not: they go by their setters."""
        visible = bool(visible)
        if visible != self._route_on:
            self._route_on = visible
            self.update()

    def set_cubes(self, points, radius=0) -> None:
        """The hidden cubes to draw, in reference-map pixels; empty or None draws none.

        A point is (x, y), or (x, y, level) with level 1 for a cube above the ground about it
        and -1 for one below, which gets an arrow beside it. They stay on whatever the
        route does -- finished, off screen, its view cut to the next steps -- because they are
        the map's, not the route's. `radius` is the ring around each in pixels at 100% Windows
        scale, constant at any zoom like the route's circles.
        """
        rows = [tuple(pt) for pt in points] if points is not None else []
        self._cubes = (
            np.array([r[:2] for r in rows], dtype=np.float32).reshape(-1, 1, 2) if rows else None
        )
        self._cube_levels = (
            np.array([r[2] if len(r) > 2 else 0 for r in rows], dtype=np.int8) if rows else None
        )
        self._cube_radius = max(0, int(radius))
        self.update()

    def set_resources(self, groups) -> None:
        """The gathering points to draw: resource id -> points in reference-map pixels.

        The map's, like the cubes, and drawn under them; a resource with no points draws nothing.
        """
        self._resources = {
            rid: np.array(points, dtype=np.float32).reshape(-1, 1, 2)
            for rid, points in (groups or {}).items()
            if len(points)
        }
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
        raw = None if transform is None else np.asarray(transform, dtype=float)
        if raw is None and self._T is None:
            return
        if raw is None:
            self._map_lost()
        self._T = raw
        self._M = None if raw is None else raw @ self._doc_scale
        self.update()

    def hideEvent(self, event) -> None:
        self._marquee_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:
        notice = self._notice()
        if notice is None:
            self._marquee_timer.stop()
        if self._T is None and notice is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._T is not None:
            # Under the route: where a step stands on a cube, its number stays readable.
            self._paint_resources(p)
            self._paint_cubes(p)
            if self._route_on:
                self._paint_route(p)
                # clear of the strip, which would otherwise sit over a pointer at the bottom
                strip = 48 * self._ui_scale if notice is not None else 0
                self._paint_pointer(p, max(strip, self._covered))
        if notice is not None:
            self._draw_notice(p, *notice)
        p.end()

    def _paint_pointer(self, p, bottom) -> None:
        """The next point's number on the edge of the map area, pointing at it, when it is off it.

        Someone lost does not know which way the route is: this says, and how far it turns as
        they walk says how near they are getting. `bottom` is the room the strip takes.
        """
        if self._M is None or self._pts is None or self._done >= len(self._pts):
            return
        target = cv2.perspectiveTransform(
            self._pts[self._done : self._done + 1], self._M.astype(np.float32)
        ).reshape(2)
        w, h = self.width(), self.height() - bottom
        if not np.all(np.isfinite(target)):
            return
        if MARKER_R <= target[0] <= w - MARKER_R and MARKER_R <= target[1] <= h - MARKER_R:
            return  # on the map area: the route itself shows it
        inset = MARKER_R + POINTER_L + 4
        if w <= 2 * inset or h <= 2 * inset:
            return
        centre = np.array([w / 2, h / 2])
        d = target - centre
        # how far along d the inset edge is, the nearer of the two sides it is headed for
        k = min(
            (w / 2 - inset) / abs(d[0]) if d[0] else np.inf,
            (h / 2 - inset) / abs(d[1]) if d[1] else np.inf,
        )
        at = centre + d * k
        u = d / float(np.hypot(*d))
        n = np.array([-u[1], u[0]])
        color = self._color_at(self._done)
        tip = at + u * (MARKER_R + POINTER_L)
        base = at + u * (MARKER_R + 1)
        head = QPainterPath(QPointF(*tip))
        head.lineTo(QPointF(*(base + n * POINTER_W / 2)))
        head.lineTo(QPointF(*(base - n * POINTER_W / 2)))
        head.closeSubpath()
        p.setOpacity(self._opacity)
        p.setPen(QPen(LINE_DARK, 2))
        p.setBrush(color)
        p.drawPath(head)
        self._draw_markers(p, at.reshape(1, 2), self._done)

    def _notice(self):
        """(title, detail, accent) for the strip over the map, or None for no strip."""
        if self._error is not None:
            return (*self._error, ERROR_COLOR)
        if self._T is not None:
            if self._far is None or self._covered:
                return None
            return (*self._far, FAR_COLOR)
        lost = time.monotonic() - self._lost_at
        if lost < NOTICE_DELAY_S:
            return None
        hint = t("native.overlay.searchingHint") if lost >= HINT_DELAY_S else ""
        return t("native.overlay.searching"), hint, SEARCH_COLOR

    def _draw_notice(self, p, title, detail, accent) -> None:
        """A dark strip across the bottom of the map area: a coloured dot, a bold line, a hint.

        At the bottom rather than in the middle: in another instance the map shown there is not
        the one being looked for, and a card in its middle covered it. One line, the hint after
        the title; where the two are longer than the strip they run along it.
        """
        k = self._ui_scale
        pad_x, pad_y, dot, gap = 12 * k, 8 * k, 9 * k, 9 * k
        width = self.width()
        x0 = pad_x + dot + gap
        text_w = width - x0 - pad_x
        if text_w < 40:
            return
        bold = QFont(p.font())
        bold.setBold(True)
        bold.setPixelSize(round(NOTICE_TITLE_PX * k))
        plain = QFont(p.font())
        plain.setPixelSize(round(NOTICE_TEXT_PX * k))
        fb, fp = QFontMetrics(bold), QFontMetrics(plain)
        line_h = max(fb.height(), fp.height())
        height = 2 * pad_y + line_h
        strip = QRectF(0, self.height() - height, width, height)

        p.setOpacity(max(self._opacity, 0.85))  # a strip nobody can read says nothing
        p.fillRect(strip, NOTICE_BG)
        p.setPen(QPen(NOTICE_BORDER, 1))
        p.drawLine(strip.topLeft(), strip.topRight())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent)
        middle = strip.top() + pad_y + line_h / 2
        p.drawEllipse(QPointF(pad_x + dot / 2, middle), dot / 2, dot / 2)

        title_w = fb.horizontalAdvance(title)
        run_w = title_w + (2 * gap + fp.horizontalAdvance(detail) if detail else 0)
        offset = self._marquee_offset((title, detail), run_w, text_w)
        starts = [x0 - offset]
        if offset or run_w > text_w:
            starts.append(x0 - offset + run_w + MARQUEE_GAP)
        p.save()
        p.setClipRect(QRectF(x0, strip.top(), text_w, height))
        for start in starts:
            p.setFont(bold)
            p.setPen(NOTICE_TITLE)
            p.drawText(QPointF(start, middle + (fb.ascent() - fb.descent()) / 2), title)
            if detail:
                p.setFont(plain)
                p.setPen(NOTICE_TEXT)
                baseline = middle + (fp.ascent() - fp.descent()) / 2
                p.drawText(QPointF(start + title_w + 2 * gap, baseline), detail)
        p.restore()
        p.setOpacity(self._opacity)

    def _marquee_offset(self, key, run_w, text_w) -> float:
        """How far the running line has moved; 0 for a line that fits, which stands still."""
        if run_w <= text_w:
            self._marquee = None
            self._marquee_timer.stop()
            return 0.0
        now = time.monotonic()
        if key != self._marquee:
            self._marquee, self._marquee_since = key, now
        if not self._marquee_timer.isActive():
            self._marquee_timer.start()
        moved = max(0.0, now - self._marquee_since - MARQUEE_PAUSE_S) * MARQUEE_SPEED
        return moved % (run_w + MARQUEE_GAP)

    def _on_screen(self, points, margin):
        """`points` (reference-map pixels) through the transform, less those off the window."""
        pts, keep = self._projected(points, margin)
        return pts[keep]

    def _projected(self, points, margin):
        """`points` through the transform, all of them, and which of them are on the window."""
        pts = cv2.perspectiveTransform(points, self._T.astype(np.float32)).reshape(-1, 2)  # pyright: ignore[reportOptionalMemberAccess]
        keep = (
            np.isfinite(pts).all(axis=1)
            & (pts[:, 0] > -margin)
            & (pts[:, 0] < self.width() + margin)
            & (pts[:, 1] > -margin)
            & (pts[:, 1] < self.height() + margin)
        )
        return pts, keep

    def _paint_resources(self, p) -> None:
        if not self._resources:
            return
        p.setOpacity(self._opacity)
        half = RESOURCE_HALF * self._ui_scale
        for rid, points in self._resources.items():
            sprite = self._resource_image(rid)
            if sprite is None:
                continue
            for x, y in self._on_screen(points, half):
                p.drawImage(QPointF(x - half, y - half), sprite)

    def _resource_image(self, rid):
        """One resource's mark on its disc, drawn once per device pixel ratio; None if not drawn."""
        ratio = self.devicePixelRatioF()
        known = self._resource_sprites.get(rid)
        if known is not None and known.devicePixelRatio() == ratio:
            return known
        svg = resource_svg(rid)
        if svg is None:
            return None
        side = RESOURCE_HALF * 2 * self._ui_scale
        image = QImage(
            int(side * ratio), int(side * ratio), QImage.Format.Format_ARGB32_Premultiplied
        )
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        q = QPainter(image)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(RESOURCE_DISC)
        q.drawEllipse(QRectF(0, 0, side, side))
        QSvgRenderer(QByteArray(svg.encode())).render(q, QRectF(1, 1, side - 2, side - 2))
        q.end()
        self._resource_sprites[rid] = image
        return image

    def _paint_cubes(self, p) -> None:
        if self._cubes is None or self._cube_levels is None:
            return
        k = self._ui_scale
        half, r = CUBE_HALF * k, self._cube_radius * k
        pts, keep = self._projected(self._cubes, r + half + LEVEL_SIDE * k)
        pts, levels = pts[keep], self._cube_levels[keep]
        if not len(pts):
            return
        p.setOpacity(self._opacity)
        if r > 0:
            fill = QColor(CUBE_RING)
            fill.setAlpha(40)
            for pen_color, width in ((LINE_DARK, 3.5), (CUBE_RING, 1.5)):
                p.setPen(QPen(pen_color, width))
                p.setBrush(fill if pen_color is CUBE_RING else Qt.BrushStyle.NoBrush)
                for x, y in pts:
                    p.drawEllipse(QPointF(x, y), r, r)
        sprite = self._cube_image()
        for x, y in pts:
            p.drawImage(QPointF(x - half, y - half), sprite)
        side = LEVEL_SIDE * k
        for (x, y), level in zip(pts, levels, strict=True):
            if level:
                top = y - half if level > 0 else y + half - side
                p.drawImage(QPointF(x + LEVEL_X * k, top), self._level_image(int(level)))

    def _level_image(self, level):
        """The arrow up (level 1) or down (-1), drawn once per device pixel ratio like the cube."""
        ratio = self.devicePixelRatioF()
        known = self._level_sprites.get(level)
        if known is not None and known.devicePixelRatio() == ratio:
            return known
        s = LEVEL_SIDE * self._ui_scale
        image = QImage(int(s * ratio), int(s * ratio), QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        # the arrow in elevenths of its side, inside a dark outline
        u = s / LEVEL_SIDE
        tip, base = (1.5 * u, s - 2.0 * u) if level > 0 else (s - 1.5 * u, 2.0 * u)
        path = QPainterPath(QPointF(s / 2, tip))
        path.lineTo(s - u, base)
        path.lineTo(u, base)
        path.closeSubpath()
        q = QPainter(image)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.setPen(
            QPen(
                LINE_DARK,
                1.5 * self._ui_scale,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        q.setBrush(LEVEL_FILL)
        q.drawPath(path)
        q.end()
        self._level_sprites[level] = image
        return image

    def _cube_image(self):
        """One cube, drawn once: a hundred of them a frame are then a hundred blits."""
        ratio = self.devicePixelRatioF()
        if self._cube_sprite is not None and self._cube_sprite.devicePixelRatio() == ratio:
            return self._cube_sprite
        side = CUBE_HALF * 2 * self._ui_scale
        image = QImage(
            int(side * ratio), int(side * ratio), QImage.Format.Format_ARGB32_Premultiplied
        )
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        # the panel's 24px drawing, scaled onto `side`
        k = side / 24
        top, left, right, mid, bottom = (12, 2.5), (3.5, 7.2), (20.5, 7.2), (12, 11.9), (12, 21.5)
        faces = (
            ((top, right, mid, left), CUBE_TOP),
            ((left, mid, bottom, (3.5, 16.8)), CUBE_LEFT),
            ((right, (20.5, 16.8), bottom, mid), CUBE_RIGHT),
        )
        q = QPainter(image)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.setPen(
            QPen(
                CUBE_INK,
                1.2,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        for corners, color in faces:
            path = QPainterPath(QPointF(corners[0][0] * k, corners[0][1] * k))
            for x, y in corners[1:]:
                path.lineTo(x * k, y * k)
            path.closeSubpath()
            q.setBrush(color)
            q.drawPath(path)
        q.end()
        self._cube_sprite = image
        return image

    def _paint_route(self, p) -> None:
        if self._M is None or self._pts is None:
            return
        done = self._done
        total = len(self._pts)
        if done >= total:
            return
        mode, ahead, past = self._view
        if self._far is not None and mode == "steps":
            # Far off the route, the next steps alone do not say where it is: the whole of it,
            # faded, does, and which part of it is nearest.
            mode = "dim"
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
        # A leg with both ends past the same edge cannot cross the window. Zoomed in on a long
        # route, nearly all of them are, and drawing them anyway made a paint 4-8x dearer.
        m = self._width + ARROW_W
        x, y = pts[:, 0], pts[:, 1]
        below_x, above_x = x < -m, x > self.width() + m
        below_y, above_y = y < -m, y > self.height() + m
        off = (
            (below_x[:-1] & below_x[1:])
            | (above_x[:-1] & above_x[1:])
            | (below_y[:-1] & below_y[1:])
            | (above_y[:-1] & above_y[1:])
        )
        legs = list(enumerate(itertools.pairwise(pts)))
        for leg, (a, b) in reversed(legs):
            if off[leg]:
                continue
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
        outline = QPen(LINE_DARK, 2)
        w, h = self.width() + MARKER_R, self.height() + MARKER_R
        for i, (x, y) in reversed(list(enumerate(pts))):
            if not (-MARKER_R < x < w and -MARKER_R < y < h):
                continue  # off the window: nothing of it would show
            p.setPen(outline)
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
