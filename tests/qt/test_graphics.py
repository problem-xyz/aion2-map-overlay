"""The graphics API decision: OpenGL where a context can be made, and QSG_RHI_BACKEND obeyed.

Qt takes the choice once per process, so the real setGraphicsApi is never called here. Whether
the editor then draws clean is left to a manual check on a build: a fast zoom has to be watched.
"""

import pytest

from map_overlay.qt import graphics
from map_overlay.qt.graphics import BACKEND_ENV, choose_graphics_api


class _Format:
    def __init__(self, major: int) -> None:
        self._major = major

    def majorVersion(self) -> int:  # noqa: N802 -- Qt's name
        return self._major

    def minorVersion(self) -> int:  # noqa: N802 -- Qt's name
        return 1


def _context(created: bool, major: int = 4) -> type:
    class _Context:
        def create(self) -> bool:
            return created

        def format(self) -> _Format:
            return _Format(major)

    return _Context


@pytest.fixture
def chosen(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """What was handed to setGraphicsApi, instead of handing it to Qt."""
    calls: list[object] = []
    monkeypatch.delenv(BACKEND_ENV, raising=False)
    monkeypatch.setattr(graphics.QQuickWindow, "setGraphicsApi", calls.append)
    monkeypatch.setattr(graphics, "_renderer", lambda _context: "a test GPU")
    return calls


def test_opengl_is_chosen_where_a_context_can_be_made(
    chosen: list[object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(graphics, "QOpenGLContext", _context(created=True))

    assert choose_graphics_api() == "opengl"
    assert chosen == [graphics.QSGRendererInterface.GraphicsApi.OpenGL]


@pytest.mark.parametrize(
    ("created", "major"),
    [(False, 4), (True, 1)],  # no context at all; the GDI generic 1.1 implementation
)
def test_direct3d_stays_without_a_usable_opengl(
    chosen: list[object], monkeypatch: pytest.MonkeyPatch, created: bool, major: int
) -> None:
    monkeypatch.setattr(graphics, "QOpenGLContext", _context(created, major))

    assert choose_graphics_api() == "d3d11"
    assert chosen == []


def test_the_environment_variable_wins(
    chosen: list[object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(BACKEND_ENV, "d3d11")
    monkeypatch.setattr(graphics, "QOpenGLContext", _context(created=True))

    assert choose_graphics_api() == "d3d11"
    assert chosen == [], "the variable is Qt's to act on, not ours to repeat"
