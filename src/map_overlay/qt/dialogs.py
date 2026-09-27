"""Every modal the app shows, behind one object.

Kept apart from Backend for two reasons: the services below it never have to know about Qt
widgets, and a test or a headless run can hand them something that answers without a screen.

The parent matters. A dialog parented to the wrong window opens behind the editor, and on
Windows that looks like the app has hung.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QWidget

from map_overlay.i18n.catalog import t

log = logging.getLogger(__name__)


class DialogService:
    """Every modal the app can open, behind one object a caller can replace.

    Each of these blocks the GUI thread until the user answers, so none of them may be called
    from a worker. The file and input calls return None for a cancelled dialog rather than
    raising, and that None is the caller's cue to do nothing at all.
    """

    def __init__(self, parent_resolver) -> None:
        # A callable, not a widget: which window should own a dialog changes as the editor
        # opens and closes.
        self._parent_resolver = parent_resolver

    def parent(self) -> QWidget | None:
        return self._parent_resolver()

    # ------------------------------------------------------------------ files
    def open_json(self, caption: str) -> str | None:
        path, _ = QFileDialog.getOpenFileName(
            self.parent(), caption, "", t("native.dialog.jsonFilter")
        )
        return path or None

    def save_json(self, caption: str, suggested: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(
            self.parent(), caption, suggested, t("native.dialog.jsonFilter")
        )
        return path or None

    # ------------------------------------------------------------------ input
    def ask_choice(self, title: str, label: str, items: list[str], current: int = 0) -> str | None:
        value, ok = QInputDialog.getItem(self.parent(), title, label, items, current, False)
        return value if ok else None

    # ------------------------------------------------------------------ clipboard
    @staticmethod
    def copy(text: str) -> None:
        QApplication.clipboard().setText(text)

    @staticmethod
    def paste() -> str:
        return QApplication.clipboard().text()

    # ------------------------------------------------------------------ shell
    @staticmethod
    def open_folder(path: Path | str) -> None:
        path = str(path)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            log.exception("cannot open folder %s", path)

    @staticmethod
    def open_url(url: str) -> bool:
        """Hand a web link to the default browser. The caller has vetted it (core.links)."""
        opened = QDesktopServices.openUrl(QUrl(url, QUrl.ParsingMode.StrictMode))
        if not opened:
            log.warning("the system could not open %s", url)
        return opened
