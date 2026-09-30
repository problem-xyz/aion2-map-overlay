"""The bundled advertising banner: shown when banner.json checks out, left out when it does not."""

import json
from pathlib import Path
from typing import Any

import pytest

from map_overlay.store.banner import MAX_IMAGE_BYTES, Banner, load_banner

REPO_BANNER = Path(__file__).resolve().parents[2] / "assets" / "banner"


def folder(tmp_path: Path, image_bytes: int = 64, **manifest: Any) -> Path:
    doc = {"image": "banner.webp", "url": "https://example.com/", "label": " Example "}
    doc.update(manifest)
    (tmp_path / "banner.webp").write_bytes(b"\0" * image_bytes)
    (tmp_path / "banner.json").write_text(json.dumps(doc), encoding="utf-8")
    return tmp_path


def test_the_shipped_banner_folder_loads_or_has_no_banner() -> None:
    """Whatever is in the repository must not be a banner the app silently drops."""
    if (REPO_BANNER / "banner.json").exists():
        assert load_banner(REPO_BANNER) is not None
    else:
        assert load_banner(REPO_BANNER) is None


def test_a_sound_banner_loads_with_its_label_trimmed(tmp_path: Path) -> None:
    root = folder(tmp_path)

    assert load_banner(root) == Banner(
        image=root / "banner.webp", url="https://example.com/", label="Example"
    )


def test_no_banner_json_is_no_banner(tmp_path: Path) -> None:
    assert load_banner(tmp_path) is None


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param({"image": "../banner.webp"}, id="image-outside-the-folder"),
        pytest.param({"image": "banner.gif"}, id="image-type"),
        pytest.param({"image": "missing.webp"}, id="image-missing"),
        pytest.param({"url": "http://example.com/"}, id="not-https"),
        pytest.param({"url": "https://user@example.com/"}, id="credentials"),
        pytest.param({"url": "javascript:alert(1)"}, id="script"),
        pytest.param({"label": "  "}, id="label-blank"),
    ],
)
def test_a_banner_that_does_not_check_out_is_left_out(
    tmp_path: Path, manifest: dict[str, Any]
) -> None:
    assert load_banner(folder(tmp_path, **manifest)) is None


def test_an_image_too_large_is_left_out(tmp_path: Path) -> None:
    assert load_banner(folder(tmp_path, image_bytes=MAX_IMAGE_BYTES + 1)) is None


def test_a_banner_json_that_is_not_json_is_left_out(tmp_path: Path) -> None:
    (tmp_path / "banner.json").write_text("{", encoding="utf-8")
    assert load_banner(tmp_path) is None
