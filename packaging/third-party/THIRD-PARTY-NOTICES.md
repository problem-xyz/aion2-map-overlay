# Third-party notices

Aion 2 - Map Overlay is free of charge under its own licence, `map-overlay/LICENSE`; it is not open
source. The packaged app -- the folder with `Aion 2 - Map Overlay.exe`, the installer and the
portable zip -- also contains the software listed below, each under its own licence. The other files
in this folder are their licence and notice files.

This file is generated when the app is built; it is not edited by hand.

## Qt and Qt for Python, under the GNU LGPL version 3

This application uses the Qt 6.11.2 libraries, Qt WebEngine 6.11.2 (with Chromium 140.0.7339.225)
and the PySide6 and Shiboken6 6.11.2 bindings (Qt for Python) under the GNU Lesser General Public
License version 3, `licenses/LGPL-3.0.txt`. The LGPL is a set of additional permissions on top of
the GNU General Public License version 3, `licenses/GPL-3.0.txt`. Parts of Chromium inside Qt
WebEngine are under the GNU LGPL version 2.1, `licenses/LGPL-2.1.txt`.

The Qt, Qt WebEngine and PySide6 files are the unmodified binaries of the PySide6-Essentials,
PySide6-Addons and shiboken6 6.11.2 wheels from PyPI. Their complete corresponding source:

- Qt 6.11.2, every module including Qt WebEngine and its Chromium tree:
  <https://download.qt.io/official_releases/qt/6.11/6.11.2/single/qt-everywhere-src-6.11.2.tar.xz>
  (or `.zip`), or one archive per module under
  <https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/>.
- PySide6 and Shiboken6 6.11.2:
  <https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz>,
  also the tag `v6.11.2` of <https://code.qt.io/cgit/pyside/pyside-setup.git>.

The app's licence lets you modify these libraries, run the app with your modified versions in place
of the ones it ships, and reverse-engineer the app as far as needed to debug such modifications.

Replacing the libraries. The app does not check them, and all of them are separate files loaded at
run time. The Qt libraries are the `Qt6*.dll` files, `QtWebEngineProcess.exe` and the `plugins/`,
`resources/` and `translations/` folders in `_internal/PySide6/`, which `_internal/PySide6/qt.conf`
makes Qt's prefix. To run the app with a modified Qt, build Qt 6.11 with MSVC for x64 and put your
files in place of these, under the same names. The PySide6 and Shiboken6 bindings are the `.pyd` and
`.abi3.dll` files in `_internal/PySide6/` and `_internal/shiboken6/`, and their Python modules the
plain `.py` files beside them; replace them the same way with a build of pyside-setup 6.11.2 against
your Qt. The page script qwebchannel.js is not a file of its own: the app reads it from Qt
WebChannel's resources in `Qt6WebChannel.dll`, so a replaced Qt brings its own.

Qt offers a few modules only under GPL-3.0 (or commercially). Of those, `_internal/PySide6/`
contains files of Qt Charts, Qt Data Visualization, Qt Virtual Keyboard, Qt Quick Timeline and a Qt
Quick 3D profiler plugin, which came with the wheels. The app does not use them and nothing it loads
links to them; their source is part of the Qt source above.

## Components

| Component | Version | Licence | Texts |
| --- | --- | --- | --- |
| Aion 2 - Map Overlay (this application) | -- | Its own, free of charge | `map-overlay/` |
| Maps and object sets (aion2-interactive-map) | -- | CC BY-NC 4.0 | `map-overlay/NOTICE` |
| Qt | 6.11.2 | LGPL-3.0-only (Qt also offers GPL-2.0, GPL-3.0 and commercial terms) | `qt/` |
| Qt WebEngine and Chromium | 6.11.2, Chromium 140.0.7339.225 | Qt WebEngine: LGPL-3.0-only; Chromium: BSD-3-Clause and the licences listed, including LGPL-2.1 | `qt-webengine/` |
| Python (CPython) | 3.14.2 | PSF-2.0, with the licences of the libraries below | `cpython/` |
| Microsoft Visual C++ runtime | 14.x | Microsoft Distributable Code | -- |
| OpenCV, what cv2.pyd links beyond its wheel's notices | 5.0.0 | OFL-1.1, Apache-2.0, BSD-3-Clause, BSD-style (CLAPACK) and Intel Simplified Software License | `opencv/` |
| Velopack | 1.2.158 | MIT, with the licences of the Rust crates and the Rust standard library it is built from | `velopack/` |
| comtypes | 1.4.17 | MIT | `python/comtypes/` |
| dxcam | 0.3.0 | MIT | `python/dxcam/` |
| mss | 10.2.0 | MIT License | `python/mss/` |
| numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | `python/numpy/` |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 (OpenCV), MIT (the opencv-python packaging) | `python/opencv-python-headless/` |
| PySide6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `python/pyside6/` |
| PySide6_Addons | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `python/pyside6-addons/` |
| PySide6_Essentials | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `python/pyside6-essentials/` |
| shiboken6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | `python/shiboken6/` |
| pyinstaller | 6.22.3 | GPL-2.0-or-later with the Bootloader Exception; Apache-2.0 for the run-time hooks | `python/pyinstaller/` |
| typing_extensions | 4.16.0 | PSF-2.0 | `python/typing-extensions/` |
| @react-leaflet/core | 2.1.0 | Hippocratic-2.1 | `npm/@react-leaflet/core/` |
| js-tokens | 4.0.0 | MIT | `npm/js-tokens/` |
| leaflet | 1.9.4 | BSD-2-Clause | `npm/leaflet/` |
| loose-envify | 1.4.0 | MIT | `npm/loose-envify/` |
| react | 18.3.1 | MIT | `npm/react/` |
| react-dom | 18.3.1 | MIT | `npm/react-dom/` |
| react-leaflet | 4.2.1 | Hippocratic-2.1 | `npm/react-leaflet/` |
| scheduler | 0.23.2 | MIT | `npm/scheduler/` |
| uqr | 0.1.3 | MIT | `npm/uqr/` |
| vite | 5.4.21 | MIT | `npm/vite/` |

`licenses/` holds the GNU and Apache texts several components share.

## Notes

- Maps and object sets (aion2-interactive-map): The two maps and their object sets are adapted from
  the aion2-interactive-map project; NOTICE credits it, links the licence and lists what was
  changed. The game art and place names in them belong to NCSOFT Corporation, as NOTICE says.
- Qt: `qt-third-party.txt` is the text of Qt's attribution pages for Qt 6.11 on doc.qt.io: the
  licence of every piece of third-party code in Qt, including modules this build does not contain.
  The Qt libraries come from the PySide6-Essentials and PySide6-Addons wheels.
- Qt WebEngine and Chromium: `chromium-third-party.txt` is Qt's list of the licences in the Chromium
  part of Qt WebEngine. The other files are the licence files of code the build contains that Qt's
  list leaves out (Skia, V8, PDFium's libraries, FreeType, libjpeg-turbo, NSPR, ANGLE, the Khronos
  and DirectX headers, the trace viewer's libraries and others), from the Chromium tree Qt WebEngine
  6.11.2 is built from, qt/qtwebengine-chromium at 5170777d. The most restrictive licence is
  LGPL-2.1 (FFmpeg's decoders, `licenses/LGPL-2.1.txt`); its source is part of the Qt WebEngine
  source named above. This software is based in part on the work of the Independent JPEG Group
  (libjpeg-turbo, here and in cv2.pyd). Qt WebEngine uses the FreeType code (`freetype-FTL.TXT`).
  The NSPR, URL-parser and ISimpleDOM files offer LGPL-2.1 among their licences, and Mozilla's
  Windows certificate code is under the Mozilla Public License 2.0 (`net-mozilla-win-LICENSE`);
  their source is part of the same Qt WebEngine source. The trace viewer's Mann-Whitney U test has
  no licence file; its two notices, copied here, name the MIT License.
- Python (CPython): python.org's Windows build, unmodified. `LICENSE.txt` is the file its installer
  puts next to python.exe, and `license.rst` the licence page of the same version's documentation.
  Compiled in: bzip2, zstd and libffi (`LICENSE.txt`); OpenSSL 3.0, under Apache-2.0
  (`licenses/Apache-2.0.txt`); expat, libffi and libmpdec (`license.rst`); HACL*
  (`hacl-star-notice.txt`); zlib-ng (`zlib-ng-LICENSE.md`); and xz, whose liblzma is in the public
  domain (`xz-COPYING`).
- Microsoft Visual C++ runtime: Microsoft's terms ask for no licence text. The conditions they set
  on redistributing it are summarised in `cpython/LICENSE.txt`, under 'Additional Conditions for
  this Windows binary build'.
- OpenCV, what cv2.pyd links beyond its wheel's notices: cv2.pyd (opencv-python-headless) links
  these statically, and the wheel has no text for them: the Rubik fonts and WenQuanYi Micro Hei (its
  copyright is in its README) that `putText` draws with, CLAPACK, Intel's ittnotify, and the IPP
  2026.0.0 package OpenCV 5.0.0 builds with. The IPP licence allows redistribution only unmodified
  and in binary form.
- Velopack: `velopack.pyd` in the app, and `Setup.exe`, `Update.exe` and the launcher stub that `vpk
  pack` adds: in the install folder and the portable zip they sit one level above the app's folder,
  and `Setup.exe` is downloaded on its own. `LICENSE` is that of Velopack's repository at the tag
  1.2.158; the wheel has none. All of it is Rust: `rust/` is the licence of the Rust standard
  library, and `crates/<crate>-<version>/` holds the licence files of each crates.io crate it is
  built from, from the crate's archive or, where that has none, from its repository at the commit it
  was published from. fs_at 0.2.1 has no licence file anywhere; it is Apache-2.0,
  `licenses/Apache-2.0.txt`.
- numpy: `numpy.libs/` holds OpenBLAS, with LAPACK and the GCC runtime library; their notices, and
  the GCC Runtime Library Exception, are in `LICENSE.txt`.
- opencv-python-headless: `LICENSE.txt` is opencv-python's MIT licence for its packaging. OpenCV
  itself is Apache-2.0 (`licenses/Apache-2.0.txt`), at the top of `LICENSE-3RD-PARTY.txt`, which
  also covers most libraries cv2.pyd links; `opencv/` has the rest. It is written for every
  platform, so some of its sections do not apply here.
- PySide6: The wheel's only licence file is Qt's commercial-licence stub, copied as shipped. This
  app uses the package under LGPL-3.0-only: see the Qt section above.
- PySide6_Addons: The wheel's only licence file is Qt's commercial-licence stub, copied as shipped.
  This app uses the package under LGPL-3.0-only: see the Qt section above.
- PySide6_Essentials: The wheel's only licence file is Qt's commercial-licence stub, copied as
  shipped. This app uses the package under LGPL-3.0-only: see the Qt section above.
- shiboken6: The wheel's only licence file is Qt's commercial-licence stub, copied as shipped. This
  app uses the package under LGPL-3.0-only: see the Qt section above.
- pyinstaller: A build tool: the build contains its bootloader (the exe), its loader and its
  run-time hooks. The Bootloader Exception allows those to be distributed inside a combined
  executable without restriction; `COPYING.txt` has both licences.
- typing_extensions: Not a runtime dependency: mss and numpy import it for type annotations, so
  PyInstaller collects it.
- @react-leaflet/core: Hippocratic License 2.1, with its own copyright line.
- js-tokens: Not in the bundle: a dependency of loose-envify.
- loose-envify: Not in the bundle: a build-time transform react depends on.
- react-leaflet: Hippocratic License 2.1: a licensee must also pass on this text.
- vite: A build tool. It injects two helpers into the bundle, its module-preload polyfill and
  @rollup/plugin-commonjs's interop helper; `LICENSE.md` covers both.
