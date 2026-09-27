"""What the built folder is made of, biggest first.

Run after scripts/build.ps1. The table it prints shows where the size goes, and the exit code
makes the size budget enforceable: over budget is a failure, not a line of output nobody reads.

Sizes are reported in MiB, because that is what Windows shows in the properties dialog and what
anyone checking this against their own disk will see.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

# A budget of 250 MiB was the first target, and it cannot be met and never could:
# Qt6WebEngineCore.dll and cv2.pyd are 194.0 and 81.9 MiB, so the two files the app cannot work
# without already come to 275.9. The figure below is the measured build plus about six percent,
# which is enough to catch a regression and not so tight that a Qt patch release trips it.
BUDGET_MIB = 520.0
MIB = 1024 * 1024


def folder_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def entries(root: Path) -> list[tuple[int, str]]:
    """Every file, plus every directory as a rolled-up total.

    Both, because either alone misleads: one enormous DLL hides in a listing of directories,
    and a thousand small files in one directory hide in a listing of files.
    """
    out: list[tuple[int, str]] = []
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            out.append((p.stat().st_size, rel))
        elif p.is_dir():
            out.append((folder_size(p), rel + "/"))
    return sorted(out, reverse=True)


def table(rows: Iterable[tuple[int, str]], total: int) -> str:
    lines = ["| Size (MiB) | Share | Path |", "| ---: | ---: | --- |"]
    for size, name in rows:
        lines.append(f"| {size / MIB:.1f} | {100 * size / total:.1f}% | `{name}` |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dist", type=Path, help="the built folder, e.g. 'dist/Aion 2 - Map Overlay'"
    )
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument(
        "--budget",
        type=float,
        default=BUDGET_MIB,
        help="fail above this many MiB; 0 disables the check",
    )
    args = parser.parse_args()

    root: Path = args.dist
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    total = folder_size(root)
    count = sum(1 for p in root.rglob("*") if p.is_file())
    rows = entries(root)[: args.top]
    print(f"# {root.name}\n")
    print(f"Total: **{total / MIB:.1f} MiB** in {count} files\n")
    print(table(rows, total))

    if args.budget and total / MIB > args.budget:
        over = total / MIB - args.budget
        print(f"\nOver budget by {over:.1f} MiB (budget {args.budget:.0f} MiB).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
