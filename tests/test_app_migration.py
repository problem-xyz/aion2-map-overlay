"""app.main() over an old layout it cannot move, run in a process of its own.

main() sets up the whole process -- DPI awareness on import, then the root logger's handlers,
the excepthooks and Qt's message handler -- and none of that should leak into the rest of the
suite, so it runs in a child. Everything with a window in it is stood in for there. What is
left is the real order of main() up to the event loop: logging, the dev-layout migration, the
data directories, and the notice queued for the page.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from map_overlay.core.logs import LOG_NAME

SRC = Path(__file__).resolve().parents[1] / "src"

CHILD = """
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import map_overlay.app as app

root, data, out, mode = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
notices = []


class Signal:
    def connect(self, slot):
        pass


class Application:
    aboutToQuit = Signal()

    def __init__(self, argv):
        pass

    @staticmethod
    def setAttribute(attribute, on):
        pass

    def setApplicationName(self, name):
        pass

    def exec(self):
        return 0


class Instance:
    def __init__(self, dirs):
        pass

    def try_acquire(self):
        return True

    def listen(self, callback):
        pass

    def release(self):
        pass


class Backend:
    def __init__(self, dirs, dev=False):
        self._store = SimpleNamespace(flush=lambda: None)

    def queue_notice(self, code, level="info", **params):
        notices.append({"code": code, "level": level, "params": params})

    def setParent(self, parent):
        pass

    def hand_over_update(self):
        pass


class Window:
    def __init__(self, backend, dev):
        pass

    def show(self):
        pass


def migration_bug(root, dirs):
    raise ValueError("a bug in the migration itself")


app.QApplication = Application
app.SingleInstance = Instance
app.Backend = Backend
app.ControlWindow = Window
app.log_screens = lambda: None
app.choose_graphics_api = lambda: "stub"  # it needs the real QApplication replaced above
app.app_root = lambda: root
if mode == "bug":
    app.migrate_dev_layout = migration_bug
sys.argv = ["app.py", "--data-dir", data]
status = app.main()
out.write_text(json.dumps({"status": status, "notices": notices}), encoding="utf-8")
"""


def _dev_layout(root: Path) -> None:
    """The pre-userdata layout: the user's data sitting directly in the app root."""
    (root / "maps" / "alpha").mkdir(parents=True)
    (root / "maps" / "alpha" / "map.json").write_text("{}", encoding="utf-8")
    (root / "routes").mkdir(parents=True)
    (root / "routes" / "gold.json").write_text("{}", encoding="utf-8")
    (root / "legacy_routes" / "old").mkdir(parents=True)
    (root / "legacy_routes" / "old" / "overlay.png").write_bytes(b"arrows on a screenshot")
    (root / "settings.json").write_text("{}", encoding="utf-8")


def _start(root: Path, data: Path, mode: str) -> tuple[dict[str, Any], str]:
    """Run main() in a child; its result, and the log file it left in the data directory."""
    out = root.parent / "result.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(SRC))
    env.pop("MAP_OVERLAY_DATA_DIR", None)
    child = subprocess.run(
        [sys.executable, "-c", CHILD, str(root), str(data), str(out), mode],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=180,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    return json.loads(out.read_text(encoding="utf-8")), (data / "logs" / LOG_NAME).read_text(
        encoding="utf-8"
    )


def test_a_layout_that_moves_is_reported_where_it_went(tmp_path: Path) -> None:
    # The control: the stand-ins in the child are enough for main() to run to the end.
    root, data = tmp_path / "app", tmp_path / "app" / "userdata"
    _dev_layout(root)

    result, _ = _start(root, data, "real")

    assert result == {
        "status": 0,
        "notices": [{"code": "data.migrated", "level": "info", "params": {"path": str(data)}}],
    }
    assert (data / "legacy_routes" / "old" / "overlay.png").is_file()


def test_a_migration_that_raises_anything_does_not_stop_the_app(tmp_path: Path) -> None:
    root, data = tmp_path / "app", tmp_path / "app" / "userdata"
    _dev_layout(root)

    result, log_text = _start(root, data, "bug")

    assert result == {
        "status": 0,
        "notices": [
            {"code": "data.migration_failed", "level": "warning", "params": {"path": str(root)}}
        ],
    }
    # The traceback reached the file, which is why logging is set up before the migration.
    assert "moving the pre-userdata layout failed" in log_text
    assert "ValueError: a bug in the migration itself" in log_text
    assert all(d.is_dir() for d in (data / "maps", data / "routes", data / "logs"))


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows refuses to move an open file")
def test_a_file_held_open_in_the_old_layout_does_not_stop_the_app(tmp_path: Path) -> None:
    root, data = tmp_path / "app", tmp_path / "app" / "userdata"
    _dev_layout(root)
    held = root / "legacy_routes" / "old" / "overlay.png"

    with held.open("rb"):  # another program, from the child's point of view
        result, log_text = _start(root, data, "real")

    assert result["status"] == 0
    assert result["notices"] == [
        {"code": "data.migration_failed", "level": "warning", "params": {"path": str(root)}}
    ]
    assert "moving the pre-userdata layout failed" in log_text
    assert "Traceback" in log_text
    assert held.is_file()  # still where the user can find it, as the notice says
    assert (data / "maps" / "alpha" / "map.json").is_file()  # moved before the failure
    # and after it: the move is not tried again, so settings left behind would never be read
    assert (data / "settings.json").is_file()
    assert not (root / "settings.json").exists()
