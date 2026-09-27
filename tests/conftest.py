"""Test setup shared by the whole suite.

Qt must never try to reach a real display here: CI has no desktop session, and a stray
QWidget would hang the run instead of failing it. The platform plugin is therefore pinned
before anything imports PySide6 -- which is why the imports below sit under a statement.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gc
import struct
import zlib
from collections.abc import Callable, Iterator
from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store import maps as maps_store
from map_overlay.store import routes as routes_store
from map_overlay.store.images import imwrite
from map_overlay.store.maps import MapSpec


@pytest.fixture
def png_header() -> Callable[[int, int], bytes]:
    """Build a PNG that is only a signature and an IHDR chunk: a size, and no pixels.

    Enough for anything that reads the size from the header, and nothing that decodes can
    succeed on it -- so a test built on one proves which of the two happened.
    """

    def make(width: int, height: int) -> bytes:
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
        return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + crc

    return make


@pytest.fixture
def jpeg_header() -> Callable[[int, int], bytes]:
    """Build a JPEG that is SOI, an APP0 segment to walk past, and SOF0 -- and no pixels."""

    def make(width: int, height: int) -> bytes:
        app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + bytes(9)
        sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
        return b"\xff\xd8" + app0 + sof0

    return make


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None) -> Iterator[None]:
    """Free what a test left behind here, before the next test builds anything of its own.

    A collection can run on whichever thread happens to allocate, and a Qt object freed on a
    thread that does not own it takes the process down (0x80000003 in CI, on an updater
    worker). Worse, a Backend freed late takes its plaque's QWebEngineView with it while the
    next Backend's page is loading, and QtWebEngine answers with an access violation on
    CrBrowserMain inside processEvents.

    This is a hook and not an autouse fixture because pytest releases a test's fixture values
    only after every teardown hook has run: a fixture's teardown could never free the Backend
    the test's own fixtures built, and each one went at the next test's first collection --
    usually inside the next Backend's constructor, with its page half loaded.
    """
    try:
        return (yield)
    finally:
        app = QApplication.instance()
        if app is not None:
            # A deleteLater() the test posted (Backend.shutdown() posts one for every window)
            # never runs without an event loop: deliver it while the objects around it are
            # still intact.
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
        if app is not None:
            app.processEvents()  # what the destruction queued, before the next test starts


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """The one QApplication the whole session shares.

    Qt permits exactly one per process and does not take kindly to it being destroyed while
    widgets from it are still alive, so this is never torn down: the process exiting is the
    teardown. Session scope is also what keeps it cheap -- the first QtWebEngine-backed window
    costs about a tenth of a second, every one after it a few milliseconds.
    """
    existing = QApplication.instance()
    yield existing if isinstance(existing, QApplication) else QApplication([])


@pytest.fixture
def dirs(tmp_path: Path) -> DataDirs:
    """An empty user-data tree, the way the app expects to find one."""
    made = DataDirs.from_root(tmp_path)
    made.ensure()
    made.legacy.mkdir(parents=True, exist_ok=True)
    return made


@pytest.fixture
def gradient() -> Callable[..., np.ndarray]:
    """Build a deterministic BGR image with enough texture for feature matching to bite.

    A flat fill would be a fair image and a useless one: a detector finds no corners in it, so
    a test using it would pass for the wrong reason.
    """

    def make(width: int = 512, height: int = 384) -> np.ndarray:
        ys, xs = np.mgrid[0:height, 0:width]
        blue = (xs * 255 // max(width - 1, 1)).astype(np.uint8)
        green = (ys * 255 // max(height - 1, 1)).astype(np.uint8)
        red = ((xs ^ ys) % 256).astype(np.uint8)  # texture, not a smooth ramp
        return np.dstack([blue, green, red])

    return make


# The maps the registry holds under test: the shipped ids, at sizes a test can cut and match
# in milliseconds. Two different sizes, so that a route moved between them has to be rescaled.
TEST_MAPS = (("altgard", "Altgard", 512, 384), ("verteron", "Verteron", 640, 480))


@pytest.fixture(autouse=True)
def test_maps_root(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    gradient: Callable[..., np.ndarray],
) -> Callable[[], Path]:
    """Point the bundled-map registry at two small maps instead of the shipped 4096 px ones.

    Autouse, because every Backend loads the registry and cuts each map it finds into tiles:
    with the real references that is two 341-tile pyramids per test. The folder is built on
    first use only, so a test that never touches maps pays nothing. Tests of the manifests
    that ship read them from the repository with an explicit root.
    """
    built: dict[str, Path] = {}

    def root() -> Path:
        if "root" not in built:
            base = tmp_path_factory.mktemp("bundled-maps")
            for map_id, label, width, height in TEST_MAPS:
                folder = base / map_id
                imwrite(
                    folder / "reference.webp",
                    gradient(width, height),
                    [cv2.IMWRITE_WEBP_QUALITY, 101],  # over 100 means lossless
                )
                atomic_write_json(
                    folder / "manifest.json",
                    {"id": map_id, "label": label, "size": [width, height]},
                )
            built["root"] = base
        return built["root"]

    monkeypatch.setattr(maps_store, "bundled_maps_root", root)
    # And no shipped object sets: a test that wants one writes it into this folder.
    monkeypatch.setattr(maps_store, "bundled_objects_root", lambda: root().parent / "object-sets")
    # Nor the shipped starter routes, which every Backend would copy into the test's routes/.
    monkeypatch.setattr(routes_store, "bundled_routes_root", lambda: root().parent / "routes")
    return root


@pytest.fixture
def bundled(test_maps_root: Callable[[], Path]) -> tuple[MapSpec, ...]:
    """The test registry, loaded: altgard at 512x384, then verteron at 640x480."""
    return maps_store.load_bundled_maps()


def prebuild_test_tiles(dirs: DataDirs) -> None:
    """Write the marker a finished tile build leaves, for each map of the test registry."""
    for map_id, _label, width, height in TEST_MAPS:
        z_max = 1 if max(width, height) <= 512 else 2
        atomic_write_json(
            dirs.maps / map_id / "tiles" / "done.json",
            {"zMax": z_max, "tile": 256, "size": [width, height], "full": 256 * 2**z_max},
            indent=None,
        )


@pytest.fixture(autouse=True)
def _tiles_already_cut(request: pytest.FixtureRequest) -> None:
    """Backends under tests/bridge and tests/updater start on maps whose tiles are already cut.

    Backend queues a tile build for every bundled map without a pyramid, and the worker's
    mapDone re-emits the whole state at some point during the test. A test that counts state
    emissions or notices while pumping the event loop would then see one more than it caused,
    at a moment that depends on the machine. So under those two folders the pyramid marker is
    written before the Backend is built; a test about the build itself opts out with the
    `builds_tiles` marker.
    """
    folder = Path(str(request.node.fspath)).parent.name
    if folder not in {"bridge", "updater"} or "dirs" not in request.fixturenames:
        return
    if request.node.get_closest_marker("builds_tiles") is None:
        prebuild_test_tiles(request.getfixturevalue("dirs"))
