"""The frozen Backend contract, written out here so that changing it fails loudly.

bridge/backend.py calls itself a frozen contract, and it means it: the panel, the steps page and
the editor bind to these exact slot names, signal names and getState() keys, and a user running a
UI build from before the change still calls them. Nothing in Python or Qt stops a rename, so this
file is the stop. Every name is a literal below and every comparison is set or tuple equality, so
a dropped name and a quietly added one both fail rather than only the first.

A failure here is not a broken test. It is the contract moving, and the answer is to decide that
on purpose: add rather than rename, bump API_VERSION in bridge/state.py, and update this file in
the same commit.
"""

import json
import re
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QMetaMethod, QObject
from PySide6.QtWidgets import QApplication

from map_overlay.bridge import backend as backend_module
from map_overlay.bridge.backend import Backend
from map_overlay.bridge.state import API_VERSION
from map_overlay.core.paths import DataDirs

STATE_KEYS = frozenset(
    {
        "api",
        "banner",
        "captureBackend",
        "captureExclusion",
        "captureVisible",
        "dev",
        "editorOpen",
        "isPortable",
        "links",
        "maps",
        "overlayVisible",
        "platform",
        "progress",
        "region",
        "repoUrl",
        "route",
        "routes",
        "running",
        "settings",
        "settingsSchema",
        "steps",
        "tilesBusy",
        "timers",
        "timersPlaque",
        "update",
        "version",
    }
)

SLOTS = (
    "checkForUpdates",
    "closeEditor",
    "closeTimersTimeline",
    "copyRouteCode",
    "copyText",
    "deleteRoute",
    "downloadUpdate",
    "exportRoute",
    "getEditorRoute",
    "getObjects",
    "getState",
    "importRouteFile",
    "installUpdate",
    "openEditor",
    "openLogsFolder",
    "openMapsFolder",
    "openRoutesFolder",
    "openTimersTimeline",
    "openUrl",
    "pasteRouteCode",
    "previewTimerSignal",
    "refreshRoutes",
    "refreshTimersData",
    "reorderRoutes",
    "resetProgress",
    "resetRegion",
    "resetSettings",
    "saveRoute",
    "selectRegion",
    "setCaptureVisible",
    "setOverlayVisible",
    "setPlayerAnchor",
    "setPreview",
    "setProgress",
    "setRoute",
    "setStepsPinned",
    "setStepsSize",
    "setStepsVisible",
    "setTimerEvent",
    "setTimersPlaquePinned",
    "setTimersPlaqueVisible",
    "setTimersWorldShown",
    "skipUpdate",
    "start",
    "stop",
    "updateSettings",
)

SIGNALS = (
    "editorRequest",
    "notify",
    "previewChanged",
    "progressChanged",
    "stateChanged",
    "statsChanged",
    "stepsChanged",
    "timersChanged",
    "updateChanged",
)

NOTIFY_KEYS = frozenset({"level", "code", "params", "text"})

# Pinned as a number, not just compared against itself: a bump is the one way the UI can tell
# which contract it reached, so it has to be a deliberate edit here rather than a side effect.
EXPECTED_API_VERSION = 33

_DOC_SLOTS = re.compile(r"slots \((\d+)\):\n(.+?)\n\n", re.DOTALL)
_DOC_SIGNALS = re.compile(r"signals:(.+?)\n\n", re.DOTALL)


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    """The real Backend on an empty user-data tree, not a stub of it.

    A stub would be free to drift from the wiring that ships, which is the drift this file is
    here to catch: the payload has to come off the object the UI actually talks to. It is
    affordable -- QtWebEngine warms up once per session and every Backend after that costs a
    few milliseconds -- and it leaves no threads behind once shutdown() has run.
    """
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def _declared_members() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Slot and signal names Qt registered, read off the class without building one.

    Enumeration starts at QObject's own method count so that what every QObject brings
    (deleteLater, objectNameChanged, destroyed) is left out: what remains is exactly what
    Backend declares.
    """
    # Every QObject subclass has staticMetaObject at runtime; PySide6's stubs do not declare it.
    meta = Backend.staticMetaObject  # pyright: ignore[reportAttributeAccessIssue]
    first = QObject.staticMetaObject.methodCount()  # pyright: ignore[reportAttributeAccessIssue]
    slots: list[str] = []
    signals: list[str] = []
    for index in range(first, meta.methodCount()):
        method = meta.method(index)
        name = bytes(method.name()).decode()
        if method.methodType() == QMetaMethod.MethodType.Signal:
            signals.append(name)
        else:
            slots.append(name)
    return tuple(sorted(slots)), tuple(sorted(signals))


def _documented_slots() -> tuple[int, tuple[str, ...]]:
    """The count and the names from the hand-written `slots (N):` block in the module docstring."""
    block = _DOC_SLOTS.search(backend_module.__doc__ or "")
    assert block is not None, "bridge/backend.py no longer documents its slots as `slots (N):`"
    names = re.findall(r"^\s*(\w+)\(", block[2], re.MULTILINE)
    return int(block[1]), tuple(sorted(names))


def _documented_signals() -> tuple[str, ...]:
    """The names from the hand-written `signals:` line in the module docstring."""
    block = _DOC_SIGNALS.search(backend_module.__doc__ or "")
    assert block is not None, "bridge/backend.py no longer documents its signals as `signals:`"
    return tuple(sorted(name for name in re.split(r"[,\s]+", block[1].strip()) if name))


def test_get_state_carries_exactly_the_keys_the_ui_is_built_against(backend: Backend) -> None:
    """Both directions matter: a missing key breaks a page, an extra one is an unannounced bump."""
    assert set(json.loads(backend.getState())) == STATE_KEYS


def test_get_state_reports_the_api_version_the_state_module_declares(backend: Backend) -> None:
    assert json.loads(backend.getState())["api"] == API_VERSION


def test_the_api_version_is_only_ever_moved_on_purpose() -> None:
    """Bumping it is correct when the contract grows -- doing it unnoticed is not."""
    assert API_VERSION == EXPECTED_API_VERSION


def test_the_backend_exposes_exactly_the_slots_the_ui_calls() -> None:
    slots, _ = _declared_members()
    assert slots == SLOTS


def test_the_backend_exposes_exactly_the_signals_the_ui_subscribes_to() -> None:
    _, signals = _declared_members()
    assert signals == SIGNALS


def test_the_module_docstring_lists_the_slots_the_class_actually_has() -> None:
    """Documentation that lies about a frozen contract is worse than none: it is read as truth."""
    counted, documented = _documented_slots()
    slots, _ = _declared_members()
    assert documented == slots
    assert counted == len(slots)


def test_the_module_docstring_lists_the_signals_the_class_actually_has() -> None:
    _, signals = _declared_members()
    assert _documented_signals() == signals


def test_a_notice_reaches_the_ui_as_level_code_params_and_text(backend: Backend) -> None:
    """Provoked through the real notifier, because a hand-built dict would prove nothing.

    queue_notice parks a notice raised before any page has connected; the first getState()
    drains it, which is the path every start-up warning takes.
    """
    payloads: list[dict[str, object]] = []
    backend.notify.connect(lambda raw: payloads.append(json.loads(raw)))

    backend.queue_notice("map.tiles_ready", label="Altgard")
    backend.getState()

    assert len(payloads) == 1
    assert set(payloads[0]) == NOTIFY_KEYS
    assert payloads[0]["level"] == "info"
    assert payloads[0]["code"] == "map.tiles_ready"
    assert payloads[0]["params"] == {"label": "Altgard"}
    # The sentence, not the code: `text` is the fallback a UI without that code still shows.
    assert "Altgard" in str(payloads[0]["text"])
