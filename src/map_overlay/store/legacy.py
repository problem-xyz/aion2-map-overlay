"""Migration from the version 2 on-disk layout."""

import shutil
from pathlib import Path

from map_overlay.core.fileio import read_json_or_none
from map_overlay.core.paths import DataDirs


def migrate_v2_layout(dirs: DataDirs) -> list[str]:
    """Move version 2 routes (a folder of reference.png + overlay.png) out of routes/.

    They go to legacy_routes/ whole. There is nothing to convert them into: the route is a
    PNG with arrows painted on it, and the screenshot beside it is not a map this version can
    use, since the maps the app ships with are the only ones. Deleting a user's files is not
    ours to do, so they stay where the user can find them. Returns the labels of the routes
    it moved.
    """
    routes_dir, legacy_dir = dirs.routes, dirs.legacy
    moved = []

    for d in sorted(routes_dir.iterdir()) if routes_dir.exists() else []:
        if not d.is_dir() or not (d / "reference.png").exists():
            continue
        label = _route_label(d)
        # Before anything moves, so that a file named legacy_routes stops this folder whole
        # and the next start moves it once that file is out of the way.
        legacy_dir.mkdir(exist_ok=True)
        _move_folder(d, legacy_dir / d.name)
        moved.append(label)

    routes_dir.mkdir(exist_ok=True)
    return moved


def _move_folder(src: Path, dst: Path) -> None:
    """Move a route folder into legacy_routes/, on top of what an earlier try left there.

    Entry by entry, not the folder whole: a screenshot another program holds open then stops
    only itself. shutil.move on the whole folder copies everything, fails to delete the open
    file, and leaves the rest deleted at the source and present only in the copy -- which the
    next start would have to remove to move the folder again. Here the next start finds only
    the file that would not move, and the copy of it is what gets replaced.
    """
    dst.mkdir(exist_ok=True)  # a file where the folder should go raises, and nothing moves
    for entry in sorted(src.iterdir()):
        target = dst / entry.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        shutil.move(str(entry), str(target))
    src.rmdir()


def _route_label(folder: Path) -> str:
    """The route's name from its route.json, else the folder name.

    Only a real name: a number or null here would reach the start-up notice as one, where
    joining the names raised TypeError out of Backend() itself.
    """
    old = read_json_or_none(folder / "route.json")
    if isinstance(old, dict) and isinstance(old.get("label"), str) and old["label"].strip():
        return old["label"]
    return folder.name
