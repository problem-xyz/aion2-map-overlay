"""The card at the top of the map area that says what the overlay is doing when it shows no route.

While the map is not found it says the overlay is looking for it -- not at once, since detection
drops the map for a frame or two all the time, and later with what to do about it. When a run
ends with an error it says so in its place, and the route is not drawn under it.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.bridge.engine_controller import Phase
from map_overlay.core.paths import DataDirs
from map_overlay.qt import overlay as overlay_module
from map_overlay.qt.overlay import HINT_DELAY_S, NOTICE_DELAY_S, OverlayWindow

WIDTH, HEIGHT = 400, 300
CARD = (WIDTH // 2, 14)  # in the card's top padding, above its text


@pytest.fixture
def overlay(qapp: QApplication) -> Iterator[OverlayWindow]:
    window = OverlayWindow()
    window.resize(WIDTH, HEIGHT)
    try:
        yield window
    finally:
        window.deleteLater()


def frame(overlay: OverlayWindow) -> QImage:
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    overlay.render(painter, QPoint(0, 0))
    painter.end()
    return image


def card(image: QImage) -> bool:
    """The card is dark on the white frame."""
    return image.pixelColor(*CARD).lightness() < 100


def lost_for(overlay: OverlayWindow, seconds: float) -> None:
    overlay._lost_at -= seconds


def test_a_map_just_lost_is_not_announced(overlay: OverlayWindow) -> None:
    overlay.set_transform(np.eye(3))
    overlay.set_transform(None)

    assert overlay._notice() is None
    assert not card(frame(overlay))


def test_a_map_not_found_for_a_while_puts_the_card_up(overlay: OverlayWindow) -> None:
    lost_for(overlay, NOTICE_DELAY_S + 0.1)

    title, hint, _accent = overlay._notice()  # pyright: ignore[reportGeneralTypeIssues]
    assert title
    assert hint == ""  # not yet
    assert card(frame(overlay))

    lost_for(overlay, HINT_DELAY_S)
    _title, hint, _accent = overlay._notice()  # pyright: ignore[reportGeneralTypeIssues]
    assert hint


def test_the_card_goes_once_the_map_is_found(overlay: OverlayWindow) -> None:
    lost_for(overlay, HINT_DELAY_S + 1)
    overlay.set_transform(np.eye(3))

    assert overlay._notice() is None
    assert not card(frame(overlay))


def test_an_error_is_shown_at_once_and_stays_until_cleared(overlay: OverlayWindow) -> None:
    overlay.set_transform(np.eye(3))
    overlay.show_error("Stopped", "Press Start again.")

    assert overlay._notice() == ("Stopped", "Press Start again.", overlay_module.ERROR_COLOR)
    assert card(frame(overlay))

    overlay.clear_error()
    assert overlay._notice() is None


# ------------------------------------------------------------------ the backend's part


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def test_a_crash_says_what_to_do_not_what_opencv_said(backend: Backend) -> None:
    backend._on_engine_failed("OpenCV(5.0.0) lkpyramid.cpp:1185: error: (-215:Assertion failed)")

    title, detail, _accent = backend.overlay._notice()  # pyright: ignore[reportGeneralTypeIssues]
    en = json.loads(Path("locales/en.json").read_text(encoding="utf-8"))["native"]["overlay"]
    assert (title, detail) == (en["stopped"], en["crashedHint"])


def test_a_known_error_is_told_in_its_own_words(backend: Backend) -> None:
    backend._on_engine_failed("vision.detector_broken")

    _title, detail, _accent = backend.overlay._notice()  # pyright: ignore[reportGeneralTypeIssues]
    assert "did not recover" in detail


def test_the_error_outlasts_the_end_of_the_run_and_a_new_start_clears_it(backend: Backend) -> None:
    backend.overlay.show()
    backend._on_engine_failed("boom")
    backend._on_engine_phase(Phase.IDLE)

    assert backend.overlay.isVisible()
    assert backend.overlay.has_error()

    backend._on_engine_phase(Phase.STARTING)
    assert not backend.overlay.has_error()


def test_the_error_goes_with_the_window_when_its_time_is_up(backend: Backend) -> None:
    backend.overlay.show()
    backend._on_engine_failed("boom")
    backend._on_engine_phase(Phase.IDLE)

    backend._overlay_error_expired(backend._overlay_error_shown)

    assert not backend.overlay.has_error()
    assert not backend.overlay.isVisible()


def test_the_time_of_an_error_already_cleared_does_not_end_the_next(backend: Backend) -> None:
    backend._on_engine_failed("boom")
    first = backend._overlay_error_shown
    backend._clear_overlay_error()
    backend._on_engine_failed("boom again")

    backend._overlay_error_expired(first)

    assert backend.overlay.has_error()
