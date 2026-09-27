"""Keep packaging/third-party/, the licence texts the frozen build ships, true to its dependencies.

    uv run python scripts/collect_licenses.py           # regenerate the generated part
    uv run python scripts/collect_licenses.py --check   # fail if anything is stale; offline

The spec copies packaging/third-party/ next to the exe as THIRD-PARTY-NOTICES/, so the packages,
Setup.exe's install and Portable.zip all carry it. It holds two kinds of folder.

Curated, maintained by hand: licenses/ (the GNU and Apache texts several components share), qt/,
qt-webengine/, cpython/, opencv/ and velopack/. They hold texts no installed package carries,
taken once from each project's own sources; their entries in CURATED say from where. This script
neither writes nor downloads them. It checks that each exists and that the component it
describes is still the version its texts were taken for (CURATED): after an upgrade of Qt,
OpenCV, Velopack or CPython the run fails until the texts are updated by hand.

Generated: python/<package>/ from the dist-info of the runtime closure of `[project]
dependencies` (plus PYTHON_BUILD_EXTRAS), npm/<package>/ from ui/node_modules for the runtime
closure of ui/package-lock.json (plus NPM_BUILD_EXTRAS), map-overlay/LICENSE, and the index
THIRD-PARTY-NOTICES.md. A package in either closure with no licence file and no curated folder
fails the run, so a new dependency cannot reach a release without its notice.

`--check` regenerates in memory and compares with what is committed. It reads the Python
packages from the environment and the UI packages from the lockfile, and takes the npm texts
from their committed copies, so it needs neither the network nor ui/node_modules.
"""

import argparse
import json
import platform
import re
import shutil
import sys
import textwrap
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from map_overlay.core.appinfo import APP_NAME
from map_overlay.core.fileio import atomic_write_bytes

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "packaging" / "third-party"
INDEX = "THIRD-PARTY-NOTICES.md"
LOCKFILE = ROOT / "ui" / "package-lock.json"
NODE_MODULES = ROOT / "ui" / "node_modules"
DIST_FOLDER = "THIRD-PARTY-NOTICES"  # where the spec puts the folder, next to the exe

QT_DOWNLOADS = "https://download.qt.io/official_releases"

# The interpreter the build is made with, python.org's Windows build, whose texts cpython/ holds.
CPYTHON = "3.14.2"
# Qt, and the Chromium inside Qt WebEngine 6.11.2 (chrome/VERSION of the tree it is built from).
QT = "6.11.2"
CHROMIUM = "140.0.7339.225"

LICENCE_NAME = re.compile(r"^(licen[cs]e|copying|notice|copyright)([._-].*)?$", re.IGNORECASE)

SHARED_TEXTS = ("licenses/Apache-2.0.txt", "licenses/GPL-3.0.txt", "licenses/LGPL-2.1.txt")
SHARED_TEXTS += ("licenses/LGPL-3.0.txt",)


class NoticeError(Exception):
    """The notices cannot be made or are not current; the message says what to do."""


@dataclass(frozen=True)
class Component:
    name: str
    version: str
    licence: str
    folder: str = ""  # its texts, relative to packaging/third-party/; empty when it has none
    note: str = ""


@dataclass(frozen=True)
class Curated(Component):
    # The distribution and version the folder's texts were taken for; "python" is the
    # interpreter, which only the build checks.
    pin: tuple[str, str] | None = None


PYSIDE_NOTE = (
    "The wheel's only licence file is Qt's commercial-licence stub, copied as shipped. This app "
    "uses the package under LGPL-3.0-only: see the Qt section above."
)

CURATED = (
    Curated(
        "Qt",
        QT,
        "LGPL-3.0-only (Qt also offers GPL-2.0, GPL-3.0 and commercial terms)",
        "qt/",
        "`qt-third-party.txt` is the text of Qt's attribution pages for Qt 6.11 on doc.qt.io: the "
        "licence of every piece of third-party code in Qt, including modules this build does not "
        "contain. The Qt libraries come from the PySide6-Essentials and PySide6-Addons wheels.",
        pin=("pyside6-essentials", QT),
    ),
    Curated(
        "Qt WebEngine and Chromium",
        f"{QT}, Chromium {CHROMIUM}",
        "Qt WebEngine: LGPL-3.0-only; Chromium: BSD-3-Clause and the licences listed, "
        "including LGPL-2.1",
        "qt-webengine/",
        "`chromium-third-party.txt` is Qt's list of the licences in the Chromium part of Qt "
        "WebEngine. The other files are the licence files of code the build contains that Qt's "
        "list leaves out (Skia, V8, PDFium's libraries, FreeType, libjpeg-turbo, NSPR, ANGLE, "
        "the Khronos and DirectX headers, the trace viewer's libraries and others), from the "
        "Chromium tree Qt WebEngine 6.11.2 is built from, qt/qtwebengine-chromium at 5170777d. "
        "The most restrictive licence is LGPL-2.1 (FFmpeg's decoders, `licenses/LGPL-2.1.txt`); "
        "its source is part of the Qt WebEngine source named above. This software is based in "
        "part on the work of the Independent JPEG Group (libjpeg-turbo, here and in cv2.pyd). "
        "Qt WebEngine uses the FreeType code (`freetype-FTL.TXT`). The NSPR, URL-parser and "
        "ISimpleDOM files offer LGPL-2.1 among their licences, and Mozilla's Windows certificate "
        "code is under the Mozilla Public License 2.0 (`net-mozilla-win-LICENSE`); their source "
        "is part of the same Qt WebEngine source. The trace viewer's Mann-Whitney U test has no "
        "licence file; its two notices, copied here, name the MIT License.",
        pin=("pyside6-addons", QT),
    ),
    Curated(
        "Python (CPython)",
        CPYTHON,
        "PSF-2.0, with the licences of the libraries below",
        "cpython/",
        "python.org's Windows build, unmodified. `LICENSE.txt` is the file its installer puts "
        "next to python.exe, and `license.rst` the licence page of the same version's "
        "documentation. Compiled in: bzip2, zstd and libffi (`LICENSE.txt`); OpenSSL 3.0, under "
        "Apache-2.0 (`licenses/Apache-2.0.txt`); expat, libffi and libmpdec (`license.rst`); "
        "HACL* (`hacl-star-notice.txt`); zlib-ng (`zlib-ng-LICENSE.md`); and xz, whose liblzma "
        "is in the public domain (`xz-COPYING`).",
        pin=("python", CPYTHON),
    ),
    Curated(
        "Microsoft Visual C++ runtime",
        "14.x",
        "Microsoft Distributable Code",
        "",
        "Microsoft's terms ask for no licence text. The conditions they set on redistributing it "
        "are summarised in `cpython/LICENSE.txt`, under 'Additional Conditions for this Windows "
        "binary build'.",
    ),
    Curated(
        "OpenCV, what cv2.pyd links beyond its wheel's notices",
        "5.0.0",
        "OFL-1.1, Apache-2.0, BSD-3-Clause, BSD-style (CLAPACK) and Intel Simplified Software "
        "License",
        "opencv/",
        "cv2.pyd (opencv-python-headless) links these statically, and the wheel has no text for "
        "them: the Rubik fonts and WenQuanYi Micro Hei (its copyright is in its README) that "
        "`putText` draws with, CLAPACK, Intel's ittnotify, and the IPP 2026.0.0 package OpenCV "
        "5.0.0 builds with. The IPP licence allows redistribution only unmodified and in binary "
        "form.",
        pin=("opencv-python-headless", "5.0.0.93"),
    ),
    Curated(
        "Velopack",
        "1.2.158",
        "MIT, with the licences of the Rust crates and the Rust standard library it is built from",
        "velopack/",
        "`velopack.pyd` in the app, and `Setup.exe`, `Update.exe` and the launcher stub that "
        "`vpk pack` adds: in the install folder and the portable zip they sit one level above "
        "the app's folder, and `Setup.exe` is downloaded on its own. `LICENSE` is that of "
        "Velopack's repository at the tag 1.2.158; the wheel has none. All of it is Rust: "
        "`rust/` is the licence of the Rust standard library, and `crates/<crate>-<version>/` "
        "holds the licence files of each crates.io crate it is built from, from the crate's "
        "archive or, where that has none, from its repository at the commit it was published "
        "from. fs_at 0.2.1 has no licence file anywhere; it is Apache-2.0, "
        "`licenses/Apache-2.0.txt`.",
        pin=("velopack", "1.2.158"),
    ),
)

# Packages whose code ends up in the build although they are not runtime dependencies.
PYTHON_BUILD_EXTRAS = ("pyinstaller", "typing-extensions")
NPM_BUILD_EXTRAS = ("vite",)
# Packages whose texts are a curated folder of the same name: no row of their own in the table.
COVERED = frozenset({"velopack"})
# A notice at the top of a file, for a package that has no licence file: name, (file, lines).
NPM_EXCERPTS: dict[str, tuple[str, tuple[int, int]]] = {}

# Licence summaries where the metadata's own is misleading, and notes; keyed by folder.
LICENCES = {
    "python/pyinstaller/": "GPL-2.0-or-later with the Bootloader Exception; Apache-2.0 for the "
    "run-time hooks",
    "python/opencv-python-headless/": "Apache-2.0 (OpenCV), MIT (the opencv-python packaging)",
}
NOTES = {
    "python/numpy/": "`numpy.libs/` holds OpenBLAS, with LAPACK and the GCC runtime library; "
    "their notices, and the GCC Runtime Library Exception, are in `LICENSE.txt`.",
    "python/opencv-python-headless/": "`LICENSE.txt` is opencv-python's MIT licence for its "
    "packaging. OpenCV itself is Apache-2.0 (`licenses/Apache-2.0.txt`), at the top of "
    "`LICENSE-3RD-PARTY.txt`, which also covers most libraries cv2.pyd links; `opencv/` has the "
    "rest. It is written for every platform, so some of its sections do not apply here.",
    "python/pyinstaller/": "A build tool: the build contains its bootloader (the exe), its "
    "loader and its run-time hooks. The Bootloader Exception allows those to be distributed "
    "inside a combined executable without restriction; `COPYING.txt` has both licences.",
    "python/typing-extensions/": "Not a runtime dependency: mss and numpy import it for type "
    "annotations, so PyInstaller collects it.",
    **dict.fromkeys(
        ("python/pyside6/", "python/pyside6-addons/", "python/pyside6-essentials/"), PYSIDE_NOTE
    ),
    "python/shiboken6/": PYSIDE_NOTE,
    "npm/loose-envify/": "Not in the bundle: a build-time transform react depends on.",
    "npm/js-tokens/": "Not in the bundle: a dependency of loose-envify.",
    "npm/vite/": "A build tool. It injects two helpers into the bundle, its module-preload "
    "polyfill and @rollup/plugin-commonjs's interop helper; `LICENSE.md` covers both.",
    "npm/react-leaflet/": "Hippocratic License 2.1: a licensee must also pass on this text.",
    "npm/@react-leaflet/core/": "Hippocratic License 2.1, with its own copyright line.",
}


# --------------------------------------------------------------------------------------------
# Python packages.


def python_closure() -> dict[str, metadata.Distribution]:
    """The installed distributions `[project] dependencies` pull in, keyed by canonical name."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    pending = [(Requirement(r), "") for r in project["dependencies"]]
    found: dict[str, metadata.Distribution] = {}
    walked: set[tuple[str, str]] = set()
    while pending:
        requirement, extra = pending.pop()
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": extra}):
            continue
        key = str(canonicalize_name(requirement.name))
        dist = found.get(key) or installed(requirement.name)
        found[key] = dist
        for wanted in sorted({"", *requirement.extras}):
            if (key, wanted) not in walked:
                walked.add((key, wanted))
                pending.extend((Requirement(r), wanted) for r in dist.requires or [])
    return dict(sorted(found.items()))


def installed(name: str) -> metadata.Distribution:
    try:
        return metadata.distribution(name)
    except metadata.PackageNotFoundError as missing:
        raise NoticeError(f"{name} is needed for the notices but not installed") from missing


def dist_texts(dist: metadata.Distribution, folder: str) -> dict[str, bytes]:
    """The licence files a wheel declares (`License-File`), or failing that, any it carries."""
    files = {
        entry.as_posix(): Path(str(dist.locate_file(entry)))
        for entry in dist.files or []
        if entry.parts and entry.parts[0].endswith(".dist-info")
    }
    info = next(iter(files)).split("/", 1)[0] if files else ""
    declared = dist.metadata.get_all("License-File") or []
    chosen: list[str] = []
    for rel in declared:
        found = [c for c in (f"{info}/licenses/{rel}", f"{info}/{rel}") if c in files]
        if not found:
            raise NoticeError(f"{dist.name} {dist.version} declares {rel}, which is not installed")
        chosen.append(found[0])
    if not declared:
        chosen = [p for p in files if LICENCE_NAME.match(p.rsplit("/", 1)[-1])]
    return {
        folder + p.split("/", 1)[1].removeprefix("licenses/"): files[p].read_bytes()
        for p in sorted(chosen)
    }


def declared_licence(dist: metadata.Distribution) -> str:
    """The licence as the wheel states it, in the shortest form its metadata offers."""
    meta = dist.metadata
    single = (meta.get("License") or "").strip()
    if meta.get("License-Expression"):
        return str(meta["License-Expression"])
    if single and "\n" not in single and len(single) <= 120:
        return single
    classifiers = meta.get_all("Classifier") or []
    names = [c.rsplit(" :: ", 1)[-1] for c in classifiers if c.startswith("License")]
    return " / ".join(names) or "not declared"


# --------------------------------------------------------------------------------------------
# UI packages.


def npm_closure(lock: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """The lockfile entries reachable from the root's `dependencies`, keyed by location."""
    packages: Mapping[str, Any] = lock["packages"]
    root = packages[""]
    optional = root.get("optionalDependencies", {})
    found: dict[str, dict[str, Any]] = {}
    pending = [("", name) for name in (*root.get("dependencies", {}), *optional)]
    while pending:
        origin, name = pending.pop()
        location = _resolve(packages, origin, name)
        if location is None:
            if name in optional:
                continue
            raise NoticeError(f"package-lock.json: {name} (needed by {origin or 'ui'}) is missing")
        if location not in found:
            found[location] = entry = packages[location]
            for kind in ("dependencies", "optionalDependencies", "peerDependencies"):
                pending.extend((location, dep) for dep in entry.get(kind, {}))
    return dict(sorted(found.items()))


def _resolve(packages: Mapping[str, Any], origin: str, name: str) -> str | None:
    """Where node would find `name` when `origin` requires it: nearest node_modules upwards."""
    here = origin
    while True:
        candidate = f"{here}/node_modules/{name}" if here else f"node_modules/{name}"
        if candidate in packages:
            return candidate
        if not here:
            return None
        cut = here.rfind("/node_modules/")
        here = here[:cut] if cut > 0 else ""


def npm_texts(name: str, version: str, *, live: bool) -> dict[str, bytes]:
    """The package's licence files: from ui/node_modules when live, else the committed copy."""
    folder = f"npm/{name}/"
    source = NODE_MODULES / name if live else OUT_DIR / folder
    if not source.is_dir():
        raise NoticeError(
            f"ui/node_modules/{name} is missing; cd ui && npm ci"
            if live
            else f"{folder} is not in packaging/third-party/: run the script without --check, "
            "with ui/node_modules installed (cd ui && npm ci)"
        )
    if live:
        manifest = json.loads((source / "package.json").read_text(encoding="utf-8"))
        if manifest.get("version") != version:
            raise NoticeError(f"ui/node_modules/{name} is not {version}, the lockfile's; npm ci")
    texts = {
        folder + p.name: p.read_bytes()
        for p in sorted(source.iterdir())
        if p.is_file() and LICENCE_NAME.match(p.name)
    }
    if name in NPM_EXCERPTS:
        file, lines = NPM_EXCERPTS[name]
        dest = f"{folder}{file}-notice.txt"
        if live:
            texts[dest] = excerpt((source / file).read_bytes(), lines)
        elif (OUT_DIR / dest).is_file():
            texts[dest] = (OUT_DIR / dest).read_bytes()
    return texts


def excerpt(data: bytes, lines: tuple[int, int]) -> bytes:
    first, last = lines
    kept = data.splitlines(keepends=True)[first - 1 : last]
    if len(kept) != last - first + 1:
        raise NoticeError(f"expected lines {first}-{last}, the file has {len(kept)} of them")
    return b"".join(kept)


# --------------------------------------------------------------------------------------------
# The components and the index.


def version_of(name: str) -> str:
    return platform.python_version() if name == "python" else installed(name).version


def curated_problems(*, interpreter: bool) -> list[str]:
    """Curated folders that are missing, or describe another version than the one installed."""
    problems = [f"missing: {p}" for p in SHARED_TEXTS if not (OUT_DIR / p).is_file()]
    for c in CURATED:
        if c.folder and not any(p.is_file() for p in (OUT_DIR / c.folder).rglob("*")):
            problems.append(f"missing: {c.folder}, a curated folder")
        if c.pin is None or (c.pin[0] == "python" and not interpreter):
            continue
        name, version = c.pin
        found = version_of(name)
        if found != version:
            problems.append(
                f"{name} is {found}, and {c.folder} holds the texts of {version}: update the "
                f"texts in {c.folder} by hand, then the pin in CURATED"
            )
    return problems


def generate(*, live_npm: bool) -> tuple[dict[str, bytes], list[Component]]:
    """The generated files by path, and every component for the index."""
    # NOTICE carries the attribution the bundled maps and object sets (CC BY-NC 4.0) must travel
    # with, so it ships beside the app's own licence.
    files = {
        "map-overlay/LICENSE": (ROOT / "LICENSE").read_bytes(),
        "map-overlay/NOTICE": (ROOT / "NOTICE").read_bytes(),
    }
    found: list[Component] = [
        Component(f"{APP_NAME} (this application)", "", "Its own, free of charge", "map-overlay/"),
        Component(
            "Maps and object sets (aion2-interactive-map)",
            "",
            "CC BY-NC 4.0",
            "map-overlay/NOTICE",
            "The two maps and their object sets are adapted from the aion2-interactive-map "
            "project; NOTICE credits it, links the licence and lists what was changed. The game "
            "art and place names in them belong to NCSOFT Corporation, as NOTICE says.",
        ),
    ]
    found += CURATED

    def add(name: str, version: str, licence: str, folder: str, texts: dict[str, bytes]) -> None:
        files.update(texts)
        note = NOTES.get(folder, "")
        found.append(Component(name, version, licence, folder if texts else "", note))

    python = python_closure()
    python |= {k: installed(k) for k in PYTHON_BUILD_EXTRAS if k not in python}
    for key, dist in python.items():
        if key in COVERED:
            continue
        folder = f"python/{key}/"
        licence = LICENCES.get(folder) or declared_licence(dist)
        add(str(dist.metadata["Name"]), dist.version, licence, folder, dist_texts(dist, folder))
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    closure = npm_closure(lock)
    for extra in NPM_BUILD_EXTRAS:
        location = f"node_modules/{extra}"
        if location not in lock["packages"]:
            raise NoticeError(f"{extra} ships code in the bundle but is not in package-lock.json")
        closure.setdefault(location, lock["packages"][location])
    for location, entry in closure.items():
        name, version = location.rsplit("node_modules/", 1)[1], entry.get("version", "?")
        licence = entry.get("license", "not declared")
        add(name, version, licence, f"npm/{name}/", npm_texts(name, version, live=live_npm))
    require_texts(found)
    files[INDEX] = render_index(found, python["pyside6"].version).encode("utf-8")
    return dict(sorted(files.items())), found


def require_texts(found: Sequence[Component]) -> None:
    """Refuse a component with nothing to show for its licence."""
    missing = [c for c in found if not c.folder and not isinstance(c, Curated)]
    if missing:
        names = ", ".join(f"{c.name} {c.version}" for c in missing)
        raise NoticeError(
            f"no licence text for: {names}. Add a curated folder for it (CURATED, COVERED) or an "
            "excerpt (NPM_EXCERPTS), or drop the dependency"
        )


def para(text: str, indent: str = "") -> list[str]:
    """A paragraph, wrapped so the file reads in Notepad as well as rendered."""
    return textwrap.wrap(
        text,
        width=100,
        initial_indent=indent,
        subsequent_indent=" " * len(indent),
        break_long_words=False,
        break_on_hyphens=False,
    )


def render_index(found: Sequence[Component], pyside: str) -> str:
    out = [
        "# Third-party notices",
        "",
        *para(
            f"{APP_NAME} is free of charge under its own licence, `map-overlay/LICENSE`; it is "
            f"not open source. The packaged app -- the folder with `{APP_NAME}.exe`, the "
            "installer and the portable zip -- also contains the software listed below, each "
            "under its own licence. The other files in this folder are their licence and "
            "notice files."
        ),
        "",
        *para("This file is generated when the app is built; it is not edited by hand."),
        "",
        *lgpl_section(QT, pyside),
        "## Components",
        "",
        "| Component | Version | Licence | Texts |",
        "| --- | --- | --- | --- |",
    ]
    for c in found:
        where = f"`{c.folder}`" if c.folder else "--"
        out.append(f"| {c.name} | {c.version or '--'} | {c.licence} | {where} |")
    out += ["", *para("`licenses/` holds the GNU and Apache texts several components share."), ""]
    out += ["## Notes", ""]
    for c in found:
        if c.note:
            out += para(f"{c.name}: {c.note}", "- ")
    return "\n".join(out) + "\n"


def lgpl_section(qt: str, pyside: str) -> list[str]:
    series = ".".join(qt.split(".")[:2])
    qt_dir = f"{QT_DOWNLOADS}/qt/{series}/{qt}"
    pyside_dir = f"{QT_DOWNLOADS}/QtForPython/pyside6/PySide6-{pyside}-src"
    return [
        "## Qt and Qt for Python, under the GNU LGPL version 3",
        "",
        *para(
            f"This application uses the Qt {qt} libraries, Qt WebEngine {qt} (with Chromium "
            f"{CHROMIUM}) and the PySide6 and Shiboken6 {pyside} bindings (Qt for Python) "
            "under the GNU Lesser General Public License version 3, "
            "`licenses/LGPL-3.0.txt`. The LGPL is a set of additional permissions on top of "
            "the GNU General Public License version 3, `licenses/GPL-3.0.txt`. Parts of "
            "Chromium inside Qt WebEngine are under the GNU LGPL version 2.1, "
            "`licenses/LGPL-2.1.txt`."
        ),
        "",
        *para(
            "The Qt, Qt WebEngine and PySide6 files are the unmodified binaries of the "
            f"PySide6-Essentials, PySide6-Addons and shiboken6 {pyside} wheels from PyPI. "
            "Their complete corresponding source:"
        ),
        "",
        *para(
            f"Qt {qt}, every module including Qt WebEngine and its Chromium tree: "
            f"<{qt_dir}/single/qt-everywhere-src-{qt}.tar.xz> (or `.zip`), or one archive per "
            f"module under <{qt_dir}/submodules/>.",
            "- ",
        ),
        *para(
            f"PySide6 and Shiboken6 {pyside}: "
            f"<{pyside_dir}/pyside-setup-everywhere-src-{pyside}.tar.xz>, also the tag "
            f"`v{pyside}` of <https://code.qt.io/cgit/pyside/pyside-setup.git>.",
            "- ",
        ),
        "",
        *para(
            "The app's licence lets you modify these libraries, run the app with your modified "
            "versions in place of the ones it ships, and reverse-engineer the app as far as "
            "needed to debug such modifications."
        ),
        "",
        *para(
            "Replacing the libraries. The app does not check them, and all of them are separate "
            "files loaded at run time. The Qt libraries are the `Qt6*.dll` files, "
            "`QtWebEngineProcess.exe` and the `plugins/`, `resources/` and `translations/` "
            "folders in `_internal/PySide6/`, which `_internal/PySide6/qt.conf` makes Qt's "
            f"prefix. To run the app with a modified Qt, build Qt {series} with MSVC for x64 and "
            "put your files in place of these, under the same names. The PySide6 and Shiboken6 "
            "bindings are the `.pyd` and `.abi3.dll` files in `_internal/PySide6/` and "
            "`_internal/shiboken6/`, and their Python modules the plain `.py` files beside "
            f"them; replace them the same way with a build of pyside-setup {pyside} against "
            "your Qt. The page script qwebchannel.js is not a file of its own: the app reads it "
            "from Qt WebChannel's resources in `Qt6WebChannel.dll`, so a replaced Qt brings its "
            "own."
        ),
        "",
        *para(
            "Qt offers a few modules only under GPL-3.0 (or commercially). Of those, "
            "`_internal/PySide6/` contains files of Qt Charts, Qt Data Visualization, Qt "
            "Virtual Keyboard, Qt Quick Timeline and a Qt Quick 3D profiler plugin, which came "
            "with the wheels. The app does not use them and nothing it loads links to them; "
            "their source is part of the Qt source above."
        ),
        "",
    ]


# --------------------------------------------------------------------------------------------
# Checking and writing.


def on_disk() -> dict[str, bytes]:
    """The generated part of packaging/third-party/ as committed, and anything unaccounted for."""
    curated = ("licenses/", *(c.folder for c in CURATED if c.folder))
    return {
        rel: p.read_bytes()
        for p in sorted(OUT_DIR.rglob("*"))
        if p.is_file() and not (rel := p.relative_to(OUT_DIR).as_posix()).startswith(curated)
    }


def check(*, interpreter: bool = False) -> list[str]:
    """What stands between packaging/third-party/ and a fresh run. Empty means current.

    `interpreter` also compares the running Python with the one cpython/ describes, which only
    matters to the build: the spec passes it.
    """
    problems = curated_problems(interpreter=interpreter)
    try:
        expected, _found = generate(live_npm=False)
    except NoticeError as error:
        return [*problems, str(error)]
    actual = on_disk()
    problems += [f"missing: {p}" for p in expected if p not in actual]
    problems += [f"not generated by the script: {p}" for p in actual if p not in expected]
    problems += [f"out of date: {p}" for p in expected if p in actual and actual[p] != expected[p]]
    return problems


def write(files: Mapping[str, bytes]) -> None:
    for path, data in files.items():
        target = OUT_DIR / path
        if not target.is_file() or target.read_bytes() != data:
            atomic_write_bytes(target, data)
    for stale in sorted(set(on_disk()) - set(files)):
        (OUT_DIR / stale).unlink()
    for folder in sorted(OUT_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()


def install_notices(app_dir: Path) -> None:
    """Copy packaging/third-party/ into a built app folder, next to the exe."""
    target = app_dir / DIST_FOLDER
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(OUT_DIR, target)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="collect_licenses.py",
        description="Regenerate or check packaging/third-party/, the build's licence notices.",
    )
    parser.add_argument("--check", action="store_true", help="compare, write nothing, offline")
    args = parser.parse_args(argv)
    if args.check:
        problems = check()
        for problem in problems:
            print(f"stale: {problem}", file=sys.stderr)
        return 1 if problems else 0
    try:
        problems = curated_problems(interpreter=False)
        if problems:
            raise NoticeError("; ".join(problems))
        files, _found = generate(live_npm=True)
    except NoticeError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    write(files)
    print(f"packaging/third-party/: {len(files)} generated files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
