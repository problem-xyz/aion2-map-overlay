"""The advertising banner that ships with the app: one image and the page it opens.

It is a bundled file, not something fetched: the app makes no network request to show it, and
a new banner reaches users with a release. With no banner.json, or one that does not check out,
there is simply no banner.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from map_overlay.core.fileio import read_json_or_none
from map_overlay.core.paths import resource_path

log = logging.getLogger(__name__)

MANIFEST = "banner.json"
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
MAX_IMAGE_BYTES = 1024 * 1024  # it is read into the page on every panel start


@dataclass(frozen=True)
class Banner:
    image: Path
    url: str  # https only; openUrl() opens this exact address
    label: str  # what a screen reader says for the image, and its tooltip


def bundled_banner_root() -> Path:
    """The folder holding banner.json and its image. Tests point this elsewhere."""
    return resource_path("assets/banner")


def load_banner(root: Path | None = None) -> Banner | None:
    base = bundled_banner_root() if root is None else Path(root)
    path = base / MANIFEST
    if not path.exists():
        return None
    try:
        return _parse(base, read_json_or_none(path))
    except ValueError as e:
        log.warning("the banner in %s is left out: %s", path, e)
        return None


def _parse(base: Path, raw: object) -> Banner:
    if not isinstance(raw, dict):
        raise ValueError("banner.json is not a JSON object")
    image, url, label = raw.get("image"), raw.get("url"), raw.get("label")
    if not isinstance(image, str) or Path(image).name != image:
        raise ValueError("image is not a file name beside banner.json")
    if Path(image).suffix.lower() not in IMAGE_TYPES:
        raise ValueError(f"image is not one of {', '.join(IMAGE_TYPES)}")
    file = base / image
    if not file.is_file():
        raise ValueError(f"{image} is missing")
    if file.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"{image} is larger than {MAX_IMAGE_BYTES} bytes")
    if not isinstance(url, str) or not _is_https(url):
        raise ValueError("url is not an https address")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label is empty")
    return Banner(image=file, url=url, label=label.strip())


def _is_https(url: str) -> bool:
    if "\\" in url or any(ord(c) < 0x21 for c in url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme == "https" and bool(parts.hostname) and "@" not in parts.netloc
