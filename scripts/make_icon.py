"""Scale `assets/icon-master.png` into the raster icons the app and the installer need.

The master is a 1024 px render made by `scripts/icon/icon.html`, which runs in Chrome: its pin is
ray-marched in WebGL and its wings are painted feather by feather, neither of which an SVG
renderer can draw. Re-render the master there when the design changes, then run this script.

Every `.ico` frame is scaled from the master on its own, with Lanczos, rather than each from the
next size up. The small frames, 48 px and below, get a light unsharp mask: a downscale that far
softens the edges of the wings and the pin until they blur into the plate.
"""

import sys
from pathlib import Path

from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parents[1]
MASTER = REPO / "assets" / "icon-master.png"
PNG = REPO / "assets" / "icon.png"
ICO = REPO / "packaging" / "icon.ico"

MASTER_SIZE = 1024
PNG_SIZE = 256
# What Windows asks for: the taskbar and Alt+Tab at 16-32, Explorer views up to 256.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
SHARPEN_AT_OR_BELOW = 48


def scaled(master: Image.Image, size: int) -> Image.Image:
    """The master brought down to `size` square, sharpened back a little when it is small."""
    image = master.resize((size, size), Image.Resampling.LANCZOS)
    if size <= SHARPEN_AT_OR_BELOW:
        image = image.filter(ImageFilter.UnsharpMask(radius=0.8, percent=60, threshold=0))
    return image


def embedded_sizes(path: Path) -> list[int]:
    """The frame sizes an `.ico` really holds, read back from its directory rather than assumed."""
    blob = path.read_bytes()
    count = int.from_bytes(blob[4:6], "little")
    return sorted(blob[6 + index * 16] or 256 for index in range(count))  # 0 in the entry is 256


def main() -> int:
    with Image.open(MASTER) as opened:
        master = opened.convert("RGBA")
    if master.size != (MASTER_SIZE, MASTER_SIZE):
        name = MASTER.relative_to(REPO).as_posix()
        print(f"{name} is {master.size[0]}x{master.size[1]}, expected {MASTER_SIZE} square")
        return 1

    scaled(master, PNG_SIZE).save(PNG)
    print(f"{PNG.relative_to(REPO).as_posix()}  {PNG_SIZE}x{PNG_SIZE}")

    # Largest first: Pillow's ICO writer skips any requested size bigger than the base image, and
    # falls back to downscaling the base for every size it was not handed a frame for.
    ICO.parent.mkdir(parents=True, exist_ok=True)
    frames = [scaled(master, size) for size in sorted(ICO_SIZES, reverse=True)]
    frames[0].save(
        ICO, format="ICO", sizes=[(size, size) for size in ICO_SIZES], append_images=frames[1:]
    )

    written = embedded_sizes(ICO)
    print(f"{ICO.relative_to(REPO).as_posix()}  {written}")
    if written != sorted(ICO_SIZES):
        print(f"expected {sorted(ICO_SIZES)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
