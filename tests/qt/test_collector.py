"""Garbage collection on the GUI thread only: a cycle a worker drops waits for the timer."""

import gc
import threading
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.qt.collector import GuiCollector


class _Cycle:
    """Half of a reference cycle that notes which thread finalised it."""

    def __init__(self, freed_on: list[str]) -> None:
        self.other: _Cycle | None = None
        self._freed_on = freed_on

    def __del__(self) -> None:
        self._freed_on.append(threading.current_thread().name)


def _drop_cycle(freed_on: list[str]) -> None:
    a, b = _Cycle(freed_on), _Cycle(freed_on)
    a.other, b.other = b, a


@pytest.fixture
def collector(qapp: QApplication) -> Iterator[GuiCollector]:
    gc.collect()
    made = GuiCollector()
    try:
        yield made
    finally:
        made.stop()


def test_it_turns_automatic_collection_off_until_stopped(qapp: QApplication) -> None:
    made = GuiCollector()
    assert not gc.isenabled()
    made.stop()
    assert gc.isenabled()


def test_a_cycle_a_worker_drops_is_freed_on_the_thread_that_ticks(
    collector: GuiCollector,
) -> None:
    freed_on: list[str] = []
    kept: list[list[int]] = []

    def work() -> None:
        _drop_cycle(freed_on)
        # Held, not dropped: freeing an object takes it off the count again. Well past the
        # threshold, which with automatic collection on sets off a collection here many times.
        kept.extend([] for _ in range(gc.get_threshold()[0] * 20))

    worker = threading.Thread(target=work, name="worker")
    worker.start()
    worker.join()
    assert freed_on == [], "the worker's allocations started a collection on the worker"

    collector.tick()

    assert freed_on == [threading.current_thread().name] * 2


def test_a_tick_below_the_threshold_collects_nothing(collector: GuiCollector) -> None:
    freed_on: list[str] = []
    _drop_cycle(freed_on)

    collector.tick()

    assert freed_on == []
