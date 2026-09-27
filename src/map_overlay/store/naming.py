"""Turning user-supplied labels into unique file and directory names.

Shared by routes and object sets, which is why it does not live in either of them.
"""

import re
from collections.abc import Callable
from typing import Any

from map_overlay.core.paths import DataDirs


def slugify(name: Any) -> str:
    """A file or directory name built from a user-supplied label: letters, digits, hyphens.

    Letters means Unicode letters, Cyrillic included -- ids are deliberately not ASCII, which
    is why every image read and write goes through `store.images` instead of OpenCV.
    """
    s = re.sub(r"[^\w\-]+", "_", str(name), flags=re.UNICODE).strip("_")
    return s or "route"


def _unique(exists: Callable[[str], bool], slug: str) -> str:
    name, i = slug, 2
    while exists(name):
        name = f"{slug}_{i}"
        i += 1
    return name


def unique_route_id(dirs: DataDirs, name: Any) -> str:
    # A .bak without its route is the last copy of one deleted by hand. A new route on that id
    # would overwrite it with its own previous version on its second save.
    def taken(n: str) -> bool:
        return (dirs.routes / f"{n}.json").exists() or (dirs.routes / f"{n}.json.bak").exists()

    return _unique(taken, slugify(name))
