"""The editor window's close handshake with its page.

The fallback timer used to run regardless of what the page answered, so a question about
unsaved work that the user took more than a second over was cut short: the window hid with
the question still on it. The timer is now only for a page that does not answer at all.
"""

from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWidgets import QApplication

from map_overlay.qt.editor_window import REQUEST_CLOSE_JS, EditorWindow


@pytest.fixture
def window(qapp: QApplication) -> Iterator[EditorWindow]:
    win = EditorWindow(QObject(), QUrl("about:blank"))
    win._loaded = True
    win.show()
    yield win
    win.force_close()


def answer_with(monkeypatch: pytest.MonkeyPatch, result: object) -> list[str]:
    scripts: list[str] = []

    def run(_page: QWebEnginePage, script: str, callback: Callable[[object], None]) -> None:
        scripts.append(script)
        callback(result)

    monkeypatch.setattr(QWebEnginePage, "runJavaScript", run)
    return scripts


def test_a_page_that_took_the_close_over_is_not_timed_out(
    window: EditorWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts = answer_with(monkeypatch, True)

    window.close()

    assert scripts == [REQUEST_CLOSE_JS]
    assert window.isVisible()
    assert not window._close_timer.isActive()


def test_a_page_that_did_not_answer_is_hidden_when_the_timer_runs_out(
    window: EditorWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer_with(monkeypatch, None)

    window.close()

    assert window._close_timer.isActive()
    window._close_timer.timeout.emit()
    assert not window.isVisible()
