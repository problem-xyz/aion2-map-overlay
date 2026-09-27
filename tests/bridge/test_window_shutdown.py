"""WindowManager's second lifetime rule, for the steps plaque: its page goes with its bridge object.

The plaque used to be detached from its QWebChannel and then left to the garbage collector.
Detaching a page that is still loading crashed QtWebEngine on the next processEvents (an access
violation in Qt6WebEngineCore.dll), and the collector took the window apart whenever it ran,
often while the next Backend's page was loading. The suite builds a Backend per test, so it died
one run in four or so, but only when ui/dist was built, the one case where the page loads at
all. What can be pinned without a build is the rule itself: the page keeps its channel, and
the window is deleted.
"""

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs


def test_shutdown_deletes_the_plaque_with_its_page_still_on_its_channel(
    qapp: QApplication, dirs: DataDirs
) -> None:
    backend = Backend(dirs)
    window = backend.steps
    page = window.view.page()

    backend.shutdown()

    assert page.webChannel() is not None
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(window)
    assert not isValid(page)
