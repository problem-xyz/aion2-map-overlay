"""What the overlay shows a player who lost the route: where it is, and which way the next point is.

Far off the route the "steps" view draws the whole route, faded, as "dim" does: the next steps
alone say nothing about where it runs. A next point off the map area gets its number on the edge
of it, pointing its way. And the question asked over the game goes across the bottom of the map
area, and answers with a click.
"""

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from map_overlay.qt.overlay import OverlayWindow
from map_overlay.qt.prompt import PromptWindow

W, H = 400, 300
WHITE = "#ffffff"


def route(overlay: OverlayWindow, points: list[tuple[float, float]]) -> None:
    markers = [{"x": x, "y": y, "text": "", "color": WHITE} for x, y in points]
    overlay.set_route(
        {"markers": markers, "style": {"color": WHITE, "width": 3}, "mapSize": [W, H]}, (W, H)
    )
    overlay.set_transform(np.eye(3))


@pytest.fixture
def overlay(qapp: QApplication) -> Iterator[OverlayWindow]:
    window = OverlayWindow()
    window.resize(W, H)
    window.set_opacity(1.0)
    try:
        yield window
    finally:
        window.deleteLater()


def frame(overlay: OverlayWindow) -> QImage:
    image = QImage(W, H, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0))
    painter = QPainter(image)
    overlay.render(painter, QPoint(0, 0))
    painter.end()
    return image


def lit(image: QImage, x: float, y: float) -> int:
    return image.pixelColor(int(x), int(y)).red()


def test_far_off_the_route_the_steps_view_draws_all_of_it_faded(overlay: OverlayWindow) -> None:
    # ten points down the left side; with one passed, "steps" draws the next three only
    route(overlay, [(40.0, 20.0 + i * 28) for i in range(10)])
    overlay.set_progress(1)
    overlay.set_view("steps", 3, 0)
    leg_far_ahead = (40, 20 + 7.5 * 28)
    assert lit(frame(overlay), *leg_far_ahead) == 0

    overlay.set_far(("Off the route", "Point 2 is to the north."))

    assert 0 < lit(frame(overlay), *leg_far_ahead) < 180  # drawn, and faded


def test_a_next_point_off_the_map_area_is_pointed_at_from_its_edge(overlay: OverlayWindow) -> None:
    route(overlay, [(200.0, 150.0), (900.0, 150.0)])  # the next point is far to the east
    overlay.set_progress(1)
    image = frame(overlay)

    # its circle on the right edge, level with the centre, pointing east
    edge = [lit(image, x, 150) for x in range(W - 60, W)]
    assert max(edge) > 180
    assert lit(image, 60, 150) == 0  # nothing on the far side


def test_a_next_point_on_the_map_area_needs_no_pointer(overlay: OverlayWindow) -> None:
    route(overlay, [(100.0, 150.0), (300.0, 150.0)])
    overlay.set_progress(1)
    image = frame(overlay)

    assert max(lit(image, x, 150) for x in range(W - 20, W)) == 0


# ------------------------------------------------------------------ the question


@pytest.fixture
def prompt(qapp: QApplication) -> Iterator[PromptWindow]:
    window = PromptWindow()
    try:
        yield window
    finally:
        window.close()
        window.deleteLater()


def test_the_question_goes_across_the_bottom_of_the_map_area(prompt: PromptWindow) -> None:
    prompt.ask(
        {"left": 100, "top": 50, "width": 600, "height": 500}, "You are at point 4", "Go on?"
    )

    geometry = prompt.geometry()
    assert prompt.asking()
    assert (geometry.left(), geometry.width()) == (100, 600)
    assert geometry.bottom() + 1 == 550


def test_a_click_answers_and_puts_the_question_away(prompt: PromptWindow) -> None:
    answers: list[bool] = []
    prompt.answered.connect(answers.append)
    prompt.ask({"left": 0, "top": 0, "width": 600, "height": 400}, "You are at point 4", "Go on?")

    prompt._no.click()

    assert answers == [False]
    assert not prompt.asking()
