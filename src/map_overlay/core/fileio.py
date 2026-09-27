"""Every write the app makes to a file it owns goes through here.

A plain write truncates the file first, so a crash, a power cut or an antivirus stepping in
halfway leaves a zero-length or half-written file where the user's route used to be. Writing a
temporary file next to the target and renaming it over the original makes the swap atomic: a
reader sees either the whole old file or the whole new one, never a mixture.

The temporary file is deliberately created beside the target rather than in the system temp
directory, because os.replace is only atomic within one filesystem.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def atomic_write_bytes(path: Path | str, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            # Without fsync the rename can land before the data does, and a power cut then
            # leaves an intact directory entry pointing at an empty file.
            os.fsync(f.fileno())
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path | str, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(
    path: Path | str, obj: Any, indent: int | None = 2, *, allow_nan: bool = True
) -> None:
    """allow_nan=False raises ValueError for NaN or an infinity instead of writing it: json.dumps
    writes them as bare tokens, which Python reads back but no JSON.parse accepts."""
    text = json.dumps(obj, ensure_ascii=False, indent=indent, allow_nan=allow_nan)
    atomic_write_text(path, text)


def read_json(path: Path | str) -> Any:
    """Parsed JSON. Raises OSError if the file cannot be read, ValueError if it is not JSON.

    For a caller that has to tell a damaged file from one it merely cannot open right now,
    which read_json_or_none folds into the same None.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_json_or_none(path: Path | str) -> Any | None:
    """Parsed JSON, or None if the file is missing, unreadable or not valid JSON."""
    path = Path(path)
    try:
        return read_json(path)
    except FileNotFoundError:
        return None
    except OSError, ValueError:
        log.warning("cannot read %s", path, exc_info=True)
        return None


def backup_corrupt(path: Path | str) -> Path:
    """Move a file aside instead of deleting it, so a broken route can still be recovered."""
    path = Path(path)
    target = path.with_name(f"{path.name}.broken-{datetime.now():%Y%m%d-%H%M%S}")
    path.replace(target)
    log.warning("moved unreadable file aside: %s -> %s", path, target.name)
    return target
