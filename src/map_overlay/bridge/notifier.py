"""Builds the payloads for the `notify` signal, and holds the ones that arrived too early.

Callers pass a code and parameters, never a sentence. The payload still carries `text`, so the
existing UI keeps working unchanged, but the code and params travel with it -- which is what
lets the UI translate the message and special-case one without string matching.

A notice raised during start-up has no listener yet: the React page connects its QWebChannel
only after the window has loaded. Those are queued and drained on the first getState(). That
is the first moment somebody is listening only because the page makes it so: QWebChannel
forwards a signal to a page only once the page has connected to it, and BackendProvider
connects `notify` before it calls getState and holds what arrives until a toast list mounts.
"""

import json
import logging
from collections.abc import Callable
from typing import Any

from map_overlay.i18n.catalog import format_code

log = logging.getLogger(__name__)


class Notifier:
    """Turns a code and its params into the JSON payload the `notify` signal carries.

    Callers pass a dotted, stable code -- never a sentence. `text` in the payload is only the
    English fallback from the catalog, for a UI that has no translation for that code yet;
    the code and params are what the UI is meant to key off.

    This holds no Qt object of its own, only the emit callable it was handed, so it can be
    used before any page is listening: queue() parks such a notice and drain() releases it,
    and post() parks one only while nobody has drained yet.
    """

    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit = emit
        self._pending: list[tuple[str, str, dict]] = []
        self._heard = False

    def info(self, code: str, **params: Any) -> None:
        self.emit("info", code, **params)

    def warning(self, code: str, **params: Any) -> None:
        self.emit("warning", code, **params)

    def error(self, code: str, **params: Any) -> None:
        self.emit("error", code, **params)

    def from_error(self, err, level: str = "error") -> None:
        """Send an AppError as the code and params it already carries."""
        self.emit(level, err.code, **err.params)

    def queue(self, code: str, level: str = "info", **params: Any) -> None:
        """For a notice raised before the page can hear it."""
        self._pending.append((level, code, params))

    def post(self, level: str, code: str, **params: Any) -> None:
        """For a notice that can come up both before and after the page connects."""
        if self._heard:
            self.emit(level, code, **params)
        else:
            self.queue(code, level, **params)

    def drain(self) -> None:
        self._heard = True
        while self._pending:
            level, code, params = self._pending.pop(0)
            self.emit(level, code, **params)

    def emit(self, level: str, code: str, **params: Any) -> None:
        text = format_code(code, params)
        if level == "error":
            log.error("notify %s: %s %s", level, code, params or "")
        elif level == "warning":
            log.warning("notify %s: %s %s", level, code, params or "")
        self._emit(
            json.dumps(
                {"level": level, "code": code, "params": params, "text": text},
                ensure_ascii=False,
            )
        )
