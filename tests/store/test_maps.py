"""The bundled map registry: the manifests that ship, what a broken one does, and listing."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from map_overlay.core.errors import MapError
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store.images import image_size, imwrite
from map_overlay.store.maps import (
    BUNDLED_MAP_IDS,
    MapSpec,
    ThumbCache,
    list_maps,
    load_bundled_maps,
    map_dir,
)

REPO_MAPS = Path(__file__).resolve().parents[2] / "assets" / "maps"


# --- the maps that ship ---------------------------------------------------------------------


def test_the_shipped_manifests_describe_the_images_beside_them() -> None:
    """Read from the repository, not from the test registry: this is the installation check."""
    specs = load_bundled_maps(REPO_MAPS)

    assert [s.id for s in specs] == list(BUNDLED_MAP_IDS) == ["altgard", "verteron"]
    assert [s.label for s in specs] == ["Altgard", "Verteron"]
    for spec in specs:
        assert spec.reference.is_file()
        assert image_size(spec.reference) == spec.size
        assert spec.detail is not None
        assert spec.detail_size is not None
        assert image_size(spec.detail) == spec.detail_size
    # The two maps are the same kind of thing: one canvas size, so nothing in the app has to
    # treat one of them as the odd one out.
    assert len({(s.size, s.detail_size) for s in specs}) == 1


def test_the_test_registry_stands_in_for_the_shipped_one(bundled: tuple[MapSpec, ...]) -> None:
    assert [(s.id, s.size) for s in bundled] == [("altgard", (512, 384)), ("verteron", (640, 480))]


# --- a broken installation ------------------------------------------------------------------


def _map_folder(
    root: Path,
    gradient: Callable[..., np.ndarray],
    *,
    manifest: Any = None,
    image: tuple[int, int] | None = (512, 384),
    detail: tuple[int, int] | None = None,
) -> Path:
    """One map folder under `root`, with a sound manifest and image unless told otherwise."""
    folder = root / "altgard"
    folder.mkdir(parents=True)
    if manifest is None:
        manifest = {"id": "altgard", "label": "Altgard", "size": [512, 384]}
    atomic_write_json(folder / "manifest.json", manifest)
    if image is not None:
        imwrite(folder / "reference.webp", gradient(*image))
    if detail is not None:
        imwrite(folder / "detail.webp", gradient(*detail))
    return root


def _sound(**changes: Any) -> dict[str, Any]:
    return {"id": "altgard", "label": "Altgard", "size": [512, 384], **changes}


@pytest.mark.parametrize(
    ("manifest", "image", "reason"),
    [
        pytest.param([], (512, 384), "not a JSON object", id="manifest-is-a-list"),
        pytest.param(_sound(id="verteron"), (512, 384), "says id", id="id-differs-from-folder"),
        pytest.param(_sound(label="  "), (512, 384), "no label", id="label-blank"),
        pytest.param(_sound(size=[512, "384"]), (512, 384), "two positive", id="size-string"),
        pytest.param(_sound(size=[512.0, 384.0]), (512, 384), "two positive", id="size-float"),
        pytest.param(_sound(size=[512, 384, 3]), (512, 384), "two positive", id="size-triple"),
        pytest.param(_sound(size=[0, 384]), (512, 384), "two positive", id="size-zero"),
        pytest.param(_sound(size=[True, 384]), (512, 384), "two positive", id="size-bool"),
        pytest.param(_sound(), None, "is missing", id="image-missing"),
        pytest.param(_sound(), (64, 48), "the image is 64x48", id="size-differs-from-image"),
    ],
)
def test_a_manifest_that_does_not_describe_its_image_is_refused(
    tmp_path: Path,
    gradient: Callable[..., np.ndarray],
    manifest: Any,
    image: tuple[int, int] | None,
    reason: str,
) -> None:
    root = _map_folder(tmp_path, gradient, manifest=manifest, image=image)

    with pytest.raises(MapError) as raised:
        load_bundled_maps(root, ids=("altgard",))

    assert raised.value.code == "map.manifest_invalid"
    assert raised.value.params["id"] == "altgard"
    assert reason in raised.value.params["reason"]


@pytest.mark.parametrize(
    ("detail_size", "detail_image", "reason"),
    [
        pytest.param([1024, "768"], (1024, 768), "detail is not two positive", id="not-ints"),
        pytest.param([768, 576], (768, 576), "doubled", id="one-and-a-half-times"),
        pytest.param([1024, 384], (1024, 384), "doubled", id="stretched-one-way"),
        pytest.param([512, 384], (512, 384), "doubled", id="same-as-the-reference"),
        pytest.param([1024, 768], None, "detail.webp is missing", id="image-missing"),
        pytest.param([1024, 768], (2048, 1536), "the image is 2048x1536", id="size-differs"),
    ],
)
def test_a_detail_image_the_manifest_does_not_describe_is_refused(
    tmp_path: Path,
    gradient: Callable[..., np.ndarray],
    detail_size: Any,
    detail_image: tuple[int, int] | None,
    reason: str,
) -> None:
    root = _map_folder(tmp_path, gradient, manifest=_sound(detail=detail_size), detail=detail_image)

    with pytest.raises(MapError) as raised:
        load_bundled_maps(root, ids=("altgard",))

    assert raised.value.code == "map.manifest_invalid"
    assert reason in raised.value.params["reason"]


def test_a_missing_manifest_is_refused(tmp_path: Path) -> None:
    (tmp_path / "altgard").mkdir()

    with pytest.raises(MapError) as raised:
        load_bundled_maps(tmp_path, ids=("altgard",))

    assert raised.value.code == "map.manifest_invalid"
    assert "manifest.json" in raised.value.params["reason"]


def test_a_sound_manifest_loads_with_its_label_trimmed(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    root = _map_folder(tmp_path, gradient, manifest=_sound(label=" Altgard "))

    (spec,) = load_bundled_maps(root, ids=("altgard",))

    assert spec == MapSpec(
        id="altgard",
        label="Altgard",
        size=(512, 384),
        reference=root / "altgard" / "reference.webp",
    )
    assert spec.tiles_source == spec.reference


def test_a_map_with_a_detail_image_is_tiled_from_it_and_stays_the_reference_s_size(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    """Routes are drawn in reference pixels and the engine matches the reference, so the detail
    image changes only what the editor's tiles are cut from."""
    root = _map_folder(tmp_path, gradient, manifest=_sound(detail=[1024, 768]), detail=(1024, 768))

    (spec,) = load_bundled_maps(root, ids=("altgard",))

    assert spec.size == (512, 384)
    assert spec.reference == root / "altgard" / "reference.webp"
    assert spec.detail == spec.tiles_source == root / "altgard" / "detail.webp"
    assert spec.detail_size == (1024, 768)


# --- listing ----------------------------------------------------------------------------------


def test_list_maps_lists_the_registry_in_order_and_nothing_else(
    dirs: DataDirs, bundled: tuple[MapSpec, ...], gradient: Callable[..., np.ndarray]
) -> None:
    """A folder under userdata/maps/ used to be a map by its presence. It no longer is."""
    imwrite(dirs.maps / "stray" / "reference.png", gradient(64, 48))
    assert not map_dir(dirs, "altgard").exists(), "nothing is created before something is written"

    listed = list_maps(dirs, bundled, ThumbCache())

    assert [m["id"] for m in listed] == ["altgard", "verteron"]
    assert [(m["label"], m["size"]) for m in listed] == [
        ("Altgard", [512, 384]),
        ("Verteron", [640, 480]),
    ]
    assert all(m["thumb"].startswith("data:image/jpeg;base64,") for m in listed)
    assert all(m["tiles"] == {"ready": False, "zMax": 0, "tile": 256} for m in listed)
    assert all(m["objects"] == [] for m in listed)
    # The thumbnail is the first thing written for a map, and it is what creates its folder.
    assert (map_dir(dirs, "altgard") / "thumb.jpg").is_file()
    assert (dirs.maps / "stray" / "reference.png").is_file(), "left alone"


def test_a_pyramid_left_by_an_earlier_image_of_the_map_is_listed_as_not_ready(
    dirs: DataDirs, bundled: tuple[MapSpec, ...]
) -> None:
    """So that start-up queues it for cutting again, instead of the editor drawing the old one."""
    atomic_write_json(
        map_dir(dirs, "altgard") / "tiles" / "done.json",
        {"zMax": 5, "tile": 256, "size": [8192, 8192], "full": 8192},
    )
    atomic_write_json(
        map_dir(dirs, "verteron") / "tiles" / "done.json",
        {"zMax": 2, "tile": 256, "size": [640, 480], "full": 1024},
    )

    listed = {m["id"]: m["tiles"] for m in list_maps(dirs, bundled, ThumbCache())}

    assert listed["altgard"] == {"ready": False, "zMax": 0, "tile": 256}
    assert listed["verteron"] == {"ready": True, "zMax": 2, "tile": 256}


def test_a_map_s_tiles_are_listed_at_its_own_depth_and_the_detail_s(
    tmp_path: Path, dirs: DataDirs, gradient: Callable[..., np.ndarray]
) -> None:
    root = _map_folder(
        tmp_path / "assets", gradient, manifest=_sound(detail=[1024, 768]), detail=(1024, 768)
    )
    specs = load_bundled_maps(root, ids=("altgard",))
    atomic_write_json(
        map_dir(dirs, "altgard") / "tiles" / "done.json",
        {"zMax": 2, "tile": 256, "size": [1024, 768], "full": 1024},
    )

    (listed,) = list_maps(dirs, specs, ThumbCache())

    assert listed["size"] == [512, 384]
    assert listed["tiles"] == {"ready": True, "zMax": 1, "tile": 256, "zNative": 2}


def test_a_thumbnail_is_cut_once_and_read_back_afterwards(
    dirs: DataDirs, bundled: tuple[MapSpec, ...]
) -> None:
    cache = ThumbCache()
    first = list_maps(dirs, bundled, cache)
    thumb = map_dir(dirs, "altgard") / "thumb.jpg"
    written = thumb.stat().st_mtime_ns

    second = list_maps(dirs, bundled, cache)

    assert thumb.stat().st_mtime_ns == written
    assert [m["thumb"] for m in second] == [m["thumb"] for m in first]
