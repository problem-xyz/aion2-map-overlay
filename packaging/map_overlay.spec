# PyInstaller spec. Run it through scripts/build.ps1, not by hand.
#
# Paths here are built from SPECPATH rather than written relative, because a spec is executed
# with the working directory of whoever invoked PyInstaller, not with its own directory. A
# literal "../src/..." resolves outside the repository as soon as the build is started from the
# root -- which is exactly how build.ps1 starts it.

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 -- SPECPATH is injected by PyInstaller
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import collect_licenses  # noqa: E402 -- needs the sys.path lines above
from map_overlay.core.appinfo import APP_NAME  # noqa: E402

# The third-party notices ship with the build, so they must describe this environment: the
# locked packages and the interpreter building it. Checked before Analysis, which takes a
# minute to reach a failure this cheap to find.
_stale = collect_licenses.check(interpreter=True)
if _stale:
    raise SystemExit(
        "packaging/third-party/ does not match this environment:\n  "
        + "\n  ".join(_stale)
        + "\nRun scripts/collect_licenses.py; its docstring says which folders are kept by hand."
    )

a = Analysis(  # noqa: F821
    [str(ROOT / "src" / "map_overlay" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    datas=[
        (str(ROOT / "ui" / "dist" / "index.html"), "ui/dist"),
        (str(ROOT / "locales"), "locales"),
        (str(ROOT / "assets" / "icon.png"), "assets"),
        (str(ROOT / "assets" / "maps"), "assets/maps"),  # the two bundled maps, ~11 MB
        # their object sets, ~360 KB; the README in that folder is for the repository only
        *((str(p), "assets/object-sets") for p in (ROOT / "assets" / "object-sets").glob("*.json")),
        # the starter routes, copied into a new user's routes/ on first run
        *((str(p), "assets/routes") for p in (ROOT / "assets" / "routes").glob("*.json")),
    ],
    # Reached only through a runtime import or a platform backend, so the analyser cannot see
    # them: dxcam pulls comtypes, and mss picks its backend by platform.
    #
    # dxcam.processor._numpy_kernels is the one that bites. dxcam reaches it through
    # import_module(), which the analyser cannot follow, and its absence is not an error: dxcam
    # logs one warning and falls back to the slower cv2 processor. So a build without it looks
    # healthy and is simply slower, for as long as nobody reads the log.
    hiddenimports=[
        "dxcam",
        "dxcam.processor._numpy_kernels",
        "comtypes",
        "comtypes.client",
        "mss",
        "mss.windows",
    ],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtTextToSpeech",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtUiTools",
        "PySide6.QtLocation",
        "PySide6.QtPositioning",
        "PySide6.QtWebSockets",
        "PySide6.QtQuick3D",
        "PySide6.QtGraphs",
        # QtQuick and QtQml are deliberately absent from this list: QtWebEngineCore depends on
        # them, and excluding them produces a build that starts and then shows three blank
        # windows.
    ],
    # The Python half of PySide6 and Shiboken6 is LGPL, and a user may replace it: so it ships as
    # plain .py files in _internal/, where it can be swapped like the DLLs beside it, and not
    # compiled into the exe's archive, where only a rebuild from this app's source reaches it.
    module_collection_mode={"PySide6": "py", "shiboken6": "py"},
    # Runs before PyInstaller's own runtime hooks, one of which imports PySide6.QtCore, and so
    # before anything of the app's: see the top of the hook.
    runtime_hooks=[str(ROOT / "packaging" / "rthook_velopack.py")],
    noarchive=False,
)

def _unwanted(dest: str) -> bool:
    """Payload PyInstaller collects that this app can never reach.

    `excludes` above only filters Python modules; Qt's DLLs, .pak resources and translations
    arrive as binaries and datas, so they have to be dropped here. Every rule below is a whole
    file the app has no code path to -- nothing is trimmed on a guess about what Qt might load.
    """
    p = dest.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]

    # Chromium's developer-tools payload. There is no way to open devtools in this app, and the
    # .debug variants are the same resources again with symbols.
    if name.endswith(".debug.pak") or name == "qtwebengine_devtools_resources.pak":
        return True
    # Video decoding. The app never opens a video; VideoCapture appears nowhere in src/.
    if name.startswith("opencv_videoio_ffmpeg"):
        return True
    # OpenSSL found on PATH. PyInstaller's Qt hook asks QtNetwork which OpenSSL it expects and
    # then searches PATH, which on a machine with Git for Windows finds Git's MinGW build. Only
    # Qt's OpenSSL TLS backend would load these, and the app makes no TLS connection through
    # Qt. What shipped would depend on the build machine, and so would the notices. Python's
    # own libssl-3.dll and libcrypto-3.dll have other names and are not affected.
    if name in ("libssl-3-x64.dll", "libcrypto-3-x64.dll"):
        return True
    # The Universal C Runtime found on PATH. A machine with the Windows SDK on PATH (the CI
    # runner) hands PyInstaller its app-local copy -- ucrtbase.dll and 43 api-ms-win-*.dll
    # forwarders -- where a plain machine does not. It is part of Windows 10 and 11, which the
    # app requires, so the system copy is what loads either way; shipping it would only make the
    # build depend on the build machine and carry Microsoft binaries the notices do not cover.
    if name == "ucrtbase.dll" or (name.startswith("api-ms-win-") and name.endswith(".dll")):
        return True
    # Chromium's own UI strings. The app ships two languages and forces one of them.
    if "qtwebengine_locales/" in p:
        return not (name.startswith("en") or name.startswith("ru"))
    # Qt's widget translations: every string the user sees comes from locales/*.json instead.
    if "/translations/" in p and name.endswith(".qm"):
        return True
    # Modules already excluded above still drag their DLLs in as dependencies.
    if name.startswith(("Qt6Quick3D", "Qt6Graphs", "Qt6Pdf")):
        return True
    # QML plugins, for applications written in QML. All three windows here are QtWidgets holding
    # a QWebEngineView, and none of them imports a QML module. WebEngine's own rendering uses the
    # scene graph from C++, not these plugin files -- which is why QtQuick and QtQml stay in the
    # module graph above while their 2500-odd .qml/.qmltypes files do not ship. Verified by
    # running a build without them: panel and plaque both render, and the plaque still reports
    # its height back through the channel.
    if p.startswith("PySide6/qml/") or "/PySide6/qml/" in p:
        return True
    return False


a.binaries = [e for e in a.binaries if not _unwanted(e[0])]  # noqa: F821
a.datas = [e for e in a.datas if not _unwanted(e[0])]  # noqa: F821

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    console=False,  # a GUI app: a console window would flash up on every launch
    icon=str(ROOT / "packaging" / "icon.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
    upx=False,  # UPX-packed exes are a reliable way to be flagged by antivirus
)

coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)  # noqa: F821

# The notices go next to the exe, where someone looking for them looks; PyInstaller would put
# datas under _internal/. COLLECT has assembled the folder by the time it returns.
collect_licenses.install_notices(Path(DISTPATH) / APP_NAME)  # noqa: F821
