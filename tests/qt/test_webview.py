"""Every page gets Qt's own qwebchannel.js before its scripts run.

The UI no longer bundles a copy: it finds `QWebChannel` on the page, put there by
prepare_page from Qt WebChannel's resources. A page without it cannot reach Python at all, so
the test loads a real page and asks it.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtWebEngineCore import QWebEngineScript
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from map_overlay.qt.webview import BACKGROUND, prepare_page, qwebchannel_script


@pytest.fixture
def view(qapp: QApplication) -> Iterator[QWebEngineView]:
    view = QWebEngineView()
    yield view
    view.deleteLater()


def test_the_script_is_qts_own_and_runs_before_the_page() -> None:
    script = qwebchannel_script()

    assert script is not None
    assert "var QWebChannel = function" in script.sourceCode()
    assert script.injectionPoint() == QWebEngineScript.InjectionPoint.DocumentCreation
    assert script.worldId() == QWebEngineScript.ScriptWorldId.MainWorld


def test_a_prepared_page_defines_qwebchannel(view: QWebEngineView, qtbot: QtBot) -> None:
    page = prepare_page(view, BACKGROUND)
    with qtbot.waitSignal(page.loadFinished, timeout=10_000):
        page.setHtml("<!doctype html><title>t</title>")

    result: list[object] = []
    page.runJavaScript("typeof window.QWebChannel", 0, result.append)
    qtbot.waitUntil(lambda: bool(result), timeout=10_000)

    assert result == ["function"]
