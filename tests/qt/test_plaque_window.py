"""The plaque base: what the steps plaque's page relies on survives the move into PlaqueWindow.

The `steps` object's six slots and one signal are frozen: the page calls them by name. Moving
five of them into PlaqueBridge must not change what the channel publishes.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QMetaMethod
from PySide6.QtWidgets import QApplication

from map_overlay.qt.plaque_window import PlaqueBridge, PlaqueWindow
from map_overlay.qt.steps_window import StepsBridge, WebStepsWindow


def published(obj: object) -> dict[str, QMetaMethod.MethodType]:
    """Every method the object's meta-object carries past QObject's own, as the channel sees it."""
    meta = obj.metaObject()  # pyright: ignore[reportAttributeAccessIssue] -- a QObject
    out = {}
    for i in range(meta.methodCount()):
        m = meta.method(i)
        name = bytes(m.name().data()).decode()
        if m.enclosingMetaObject().className() != "QObject":
            out[name] = m.methodType()
    return out


@pytest.fixture
def steps(qapp: QApplication) -> Iterator[WebStepsWindow]:
    window = WebStepsWindow()
    try:
        yield window
    finally:
        window.deleteLater()


def test_the_steps_object_publishes_its_frozen_names(steps: WebStepsWindow) -> None:
    methods = published(steps._bridge)
    slots = {n for n, t in methods.items() if t == QMetaMethod.MethodType.Slot}
    signals = {n for n, t in methods.items() if t == QMetaMethod.MethodType.Signal}
    assert slots == {"getData", "dragStart", "dragEnd", "action", "setHeight", "setHotspot"}
    assert signals == {"dataChanged"}
    assert isinstance(steps._bridge, StepsBridge)


def test_a_plain_plaque_bridge_has_all_but_the_steps_relic() -> None:
    names = set(published(PlaqueBridge(None))) - {"dataChanged"}  # pyright: ignore[reportArgumentType]
    assert names == {"getData", "dragStart", "dragEnd", "action", "setHotspot"}


def test_the_steps_plaque_keeps_its_sizes_and_starts_pinned(steps: WebStepsWindow) -> None:
    assert isinstance(steps, PlaqueWindow)
    assert (steps.BASE_WIDTH, steps.BASE_HEIGHT, steps.GRIP) == (430, 300, 8)
    region = steps.default_region()
    assert (region["left"], region["top"]) == (60, 140)
    assert steps._pinned


def test_a_plaque_without_content_says_so() -> None:
    with pytest.raises(NotImplementedError):
        PlaqueWindow.data_json(object())  # pyright: ignore[reportArgumentType]
