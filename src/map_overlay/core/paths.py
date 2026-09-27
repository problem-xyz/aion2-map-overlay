"""Where the app reads its own resources and where it writes the user's data.

These are two different places and must never be the same one. Bundled resources live next to
the executable and are read-only once installed; user data lives under %LocalAppData% so that
an update, an uninstall or a non-admin account cannot lose it. In a source checkout both sides
stay inside the repository, because having to look in %LocalAppData% while developing is worse
than a gitignored folder.
"""

import logging
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from map_overlay.core.appinfo import APP_DIR_NAME

log = logging.getLogger(__name__)

# Moved into userdata/ on first run of a checkout that predates this layout.
_DEV_LAYOUT_ENTRIES = ("maps", "routes", "legacy_routes", "settings.json", "state.json")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """The directory the app was started from: the exe's folder, or the repository root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def resource_path(rel: str) -> Path:
    """A bundled, read-only resource. Under PyInstaller these are unpacked to _MEIPASS."""
    base = getattr(sys, "_MEIPASS", None)
    return (Path(base) if base else app_root()) / rel


def install_root() -> Path:
    """Where the install begins, which is not always the exe's own folder.

    Velopack keeps the app in <root>/current/ beside <root>/Update.exe and replaces current/
    wholesale on every update, so anything the app keeps has to sit beside current/ rather than
    inside it: a portable userdata/ under current/ would be deleted by the first update. A plain
    copy of dist/ has no such split, and there the install is simply the exe's folder.

    Deliberately separate from app_root(), which still means the exe's folder: resource_path()
    and the dev-layout migration both depend on that meaning.
    """
    root = app_root()
    if is_frozen() and root.name.lower() == "current" and (root.parent / "Update.exe").is_file():
        return root.parent
    return root


def portable_marker() -> Path:
    """Its presence at the install root keeps all user data beside the app as well."""
    return install_root() / "portable.txt"


def _has_portable_marker() -> bool:
    """portable.txt, or the empty .portable that Velopack's portable zip carries at its root.

    Velopack reads a copy as portable by .portable alone, and the release's portable zip is
    made by vpk, which knows nothing of portable.txt. Honouring only ours would send that zip's
    data to %LocalAppData%, while Velopack itself treated the copy as portable.
    """
    return portable_marker().exists() or (install_root() / ".portable").exists()


def is_portable() -> bool:
    """A build told by a marker file to leave nothing behind outside its own folder.

    A property of builds only: a source checkout keeps its data in the repository whether or
    not the marker is there, and nothing about it needs to behave differently.
    """
    return is_frozen() and _has_portable_marker()


def user_data_dir(override: str | None = None) -> Path:
    if override:
        return Path(override)
    if _has_portable_marker() or not is_frozen():
        return install_root() / "userdata"
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME


@dataclass(frozen=True)
class DataDirs:
    """Every directory the app writes to. Nothing outside these is ever written."""

    root: Path
    maps: Path
    routes: Path
    legacy: Path
    logs: Path

    @classmethod
    def from_root(cls, root: Path | str) -> DataDirs:
        root = Path(root)
        return cls(
            root=root,
            maps=root / "maps",
            routes=root / "routes",
            legacy=root / "legacy_routes",
            logs=root / "logs",
        )

    @property
    def settings(self) -> Path:
        return self.root / "settings.json"

    @property
    def state(self) -> Path:
        return self.root / "state.json"

    def ensure(self) -> None:
        for path in (self.root, self.maps, self.routes, self.logs):
            path.mkdir(parents=True, exist_ok=True)


def migrate_dev_layout(root: Path, dirs: DataDirs) -> list[str]:
    """Move pre-userdata data out of the app root, once.

    Only ever finds anything in a source checkout or a portable install, where the two
    directories sit on the same volume -- so this is a rename, and the 1716 tile files of a
    single 8192x8192 map move instantly rather than being copied.

    Returns the paths that were moved, for the caller to turn into a notice. An entry that
    cannot be moved does not stop the others: once maps/ has moved this never runs again, so
    an entry left untried would stay in the app root for good. Every such failure is raised
    together, as one ExceptionGroup, after the last entry.
    """
    root = Path(root)
    if root == dirs.root or (dirs.maps.exists() and any(dirs.maps.iterdir())):
        return []

    moved: list[str] = []
    failed: list[OSError] = []
    for name in _DEV_LAYOUT_ENTRIES:
        src = root / name
        if not src.exists():
            continue
        dst = dirs.root / name
        if dst.is_dir() and not any(dst.iterdir()):
            # ensure() may have created the destination already; an empty one is not data.
            dst.rmdir()
        elif dst.exists():
            continue
        dirs.root.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
        except OSError as e:
            failed.append(e)
            continue
        moved.append(name)
    if failed:
        raise ExceptionGroup("some of the pre-userdata layout could not be moved", failed)
    return moved


def run_migration(what: str, migrate: Callable[[], list[str]]) -> list[str] | None:
    """Run a start-up migration so that no failure of it can cost the start-up.

    Returns what `migrate` reports it moved, or None when it raised. Anything at all is
    caught: damaged data surfaces as whatever the move or the reader of the file happened to
    raise, and none of it is worth a user's app not starting. The traceback goes to the log;
    turning None into data.migration_failed is left to the caller, which knows the path.
    """
    try:
        return migrate()
    except Exception:
        log.exception("%s failed", what)
        return None
