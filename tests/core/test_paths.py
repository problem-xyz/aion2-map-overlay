"""Where the app reads its resources from and where it writes the user's data.

Every test drives the real precedence logic and fakes only its inputs -- `sys.frozen`,
`sys.executable`, `sys._MEIPASS`, `LOCALAPPDATA` and the home directory. Patching `app_root()`
or `portable_marker()` themselves would leave the branch order in `user_data_dir()` untested,
and that order is the whole point of the function.
"""

import logging
import shutil
import sys
from pathlib import Path

import pytest

from map_overlay.core import paths as paths_module
from map_overlay.core.appinfo import APP_DIR_NAME, PACK_ID
from map_overlay.core.paths import (
    DataDirs,
    app_root,
    install_root,
    is_frozen,
    is_portable,
    migrate_dev_layout,
    portable_marker,
    resource_path,
    run_migration,
    user_data_dir,
)


def _freeze_at(monkeypatch: pytest.MonkeyPatch, exe_dir: Path) -> Path:
    """Make the process look like a PyInstaller build started from `exe_dir`.

    Returns the directory `app_root()` is expected to report. It is resolved, because
    `app_root()` resolves `sys.executable` and a temp directory can be a short name.
    """
    exe_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "MapOverlay.exe"))
    return exe_dir.resolve()


def _unfreeze(monkeypatch: pytest.MonkeyPatch) -> None:
    """A source checkout, where `sys.frozen` is absent rather than False."""
    monkeypatch.delattr(sys, "frozen", raising=False)


def _within(path: Path, folder: Path) -> bool:
    """`path` is `folder` or somewhere below it, ignoring case as Windows paths do."""
    inner = [part.casefold() for part in path.resolve().parts]
    outer = [part.casefold() for part in folder.resolve().parts]
    return inner[: len(outer)] == outer


def _dev_layout(root: Path) -> None:
    """The pre-userdata layout: the user's data sitting directly in the app root."""
    (root / "maps" / "alpha").mkdir(parents=True)
    (root / "maps" / "alpha" / "meta.json").write_text("{}", encoding="utf-8")
    (root / "routes").mkdir(parents=True)
    (root / "routes" / "r1.json").write_text("{}", encoding="utf-8")
    (root / "legacy_routes").mkdir(parents=True)
    (root / "settings.json").write_text("{}", encoding="utf-8")
    (root / "state.json").write_text("{}", encoding="utf-8")


# --- is_frozen / app_root ---------------------------------------------------------------


def test_is_frozen_is_false_in_a_source_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    _unfreeze(monkeypatch)
    assert is_frozen() is False


def test_is_frozen_follows_the_pyinstaller_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert is_frozen() is True


def test_app_root_is_the_repository_root_in_a_source_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _unfreeze(monkeypatch)

    root = app_root()

    # paths.py lives at <root>/src/map_overlay/core/paths.py, which is the parents[3] the
    # function counts back through; one level off and this assertion fails.
    module = root / "src" / "map_overlay" / "core" / "paths.py"
    assert Path(paths_module.__file__).resolve() == module
    assert (root / "pyproject.toml").is_file()


def test_app_root_is_the_executable_folder_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    expected = _freeze_at(monkeypatch, tmp_path / "install")
    assert app_root() == expected


# --- resource_path ----------------------------------------------------------------------


def test_resource_path_reads_from_the_pyinstaller_unpack_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_at(monkeypatch, tmp_path / "install")
    unpacked = tmp_path / "_MEI12345"
    # _MEIPASS does not exist outside a bundle, so it has to be created, not replaced.
    monkeypatch.setattr(sys, "_MEIPASS", str(unpacked), raising=False)

    assert resource_path("locales/en.json") == unpacked / "locales" / "en.json"


def test_resource_path_falls_back_to_the_app_root_without_meipass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _freeze_at(monkeypatch, tmp_path / "install")
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert resource_path("ui/dist/index.html") == root / "ui" / "dist" / "index.html"


# --- portable_marker --------------------------------------------------------------------


def test_portable_marker_sits_next_to_the_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _freeze_at(monkeypatch, tmp_path / "install")
    assert portable_marker() == root / "portable.txt"


# --- user_data_dir: the four branches, in precedence order ------------------------------


def test_user_data_dir_override_beats_every_other_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _freeze_at(monkeypatch, tmp_path / "install")
    (root / "portable.txt").write_text("", encoding="utf-8")  # the next-strongest signal
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert user_data_dir(str(tmp_path / "chosen")) == tmp_path / "chosen"


def test_user_data_dir_stays_in_the_checkout_when_not_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _unfreeze(monkeypatch)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    # A dev run keeps its data in a gitignored folder instead of %LocalAppData%.
    assert user_data_dir() == app_root() / "userdata"


def test_user_data_dir_prefers_the_portable_marker_over_localappdata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _freeze_at(monkeypatch, tmp_path / "install")
    (root / "portable.txt").write_text("", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert user_data_dir() == root / "userdata"


def test_user_data_dir_uses_localappdata_when_frozen_without_the_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_at(monkeypatch, tmp_path / "install")
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    assert user_data_dir() == local / APP_DIR_NAME


def test_user_data_dir_treats_an_empty_localappdata_as_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_at(monkeypatch, tmp_path / "install")
    monkeypatch.setenv("LOCALAPPDATA", "")
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert user_data_dir() == home / "AppData" / "Local" / APP_DIR_NAME


def test_user_data_dir_falls_back_under_the_home_directory_without_localappdata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_at(monkeypatch, tmp_path / "install")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    assert user_data_dir() == home / "AppData" / "Local" / APP_DIR_NAME


# --- DataDirs ---------------------------------------------------------------------------


def test_from_root_derives_every_directory_from_the_root(tmp_path: Path) -> None:
    dirs = DataDirs.from_root(tmp_path)

    assert dirs.root == tmp_path
    assert dirs.maps == tmp_path / "maps"
    assert dirs.routes == tmp_path / "routes"
    assert dirs.legacy == tmp_path / "legacy_routes"
    assert dirs.logs == tmp_path / "logs"


def test_from_root_accepts_a_string(tmp_path: Path) -> None:
    dirs = DataDirs.from_root(str(tmp_path))
    assert dirs.root == tmp_path


def test_settings_and_state_are_files_directly_under_the_root(tmp_path: Path) -> None:
    dirs = DataDirs.from_root(tmp_path)

    assert dirs.settings == tmp_path / "settings.json"
    assert dirs.state == tmp_path / "state.json"


def test_ensure_creates_the_data_directories(tmp_path: Path) -> None:
    dirs = DataDirs.from_root(tmp_path / "userdata")

    dirs.ensure()

    assert dirs.root.is_dir()
    assert dirs.maps.is_dir()
    assert dirs.routes.is_dir()
    assert dirs.logs.is_dir()


def test_ensure_is_idempotent_and_keeps_existing_content(tmp_path: Path) -> None:
    dirs = DataDirs.from_root(tmp_path / "userdata")
    dirs.ensure()
    kept = dirs.maps / "alpha"
    kept.mkdir()

    dirs.ensure()

    assert kept.is_dir()


# --- migrate_dev_layout -----------------------------------------------------------------


def test_migrate_moves_the_pre_userdata_entries_out_of_the_app_root(tmp_path: Path) -> None:
    root = tmp_path / "app"
    _dev_layout(root)
    dirs = DataDirs.from_root(root / "userdata")

    moved = migrate_dev_layout(root, dirs)

    # The order mirrors _DEV_LAYOUT_ENTRIES in core/paths.py.
    assert moved == ["maps", "routes", "legacy_routes", "settings.json", "state.json"]
    assert (dirs.maps / "alpha" / "meta.json").is_file()
    assert (dirs.routes / "r1.json").is_file()
    assert dirs.legacy.is_dir()
    assert dirs.settings.is_file()
    assert dirs.state.is_file()
    assert not (root / "maps").exists()
    assert not (root / "settings.json").exists()


def test_migrate_is_a_no_op_on_a_second_call(tmp_path: Path) -> None:
    root = tmp_path / "app"
    _dev_layout(root)
    dirs = DataDirs.from_root(root / "userdata")
    migrate_dev_layout(root, dirs)

    assert migrate_dev_layout(root, dirs) == []
    assert (dirs.maps / "alpha" / "meta.json").is_file()


def test_migrate_does_nothing_when_the_root_is_already_the_data_dir(tmp_path: Path) -> None:
    dirs = DataDirs.from_root(tmp_path)
    dirs.ensure()  # an empty maps/, so only the root check itself can stop the function
    (dirs.routes / "r1.json").write_text("{}", encoding="utf-8")
    dirs.settings.write_text("{}", encoding="utf-8")

    assert migrate_dev_layout(tmp_path, dirs) == []
    # Without the guard every entry would be moved onto itself, and the empty maps/ would be
    # deleted first by the "an empty destination is not data" branch.
    assert dirs.maps.is_dir()
    assert (dirs.routes / "r1.json").is_file()
    assert dirs.settings.is_file()


def test_migrate_does_nothing_when_the_destination_maps_already_holds_data(
    tmp_path: Path,
) -> None:
    root = tmp_path / "app"
    _dev_layout(root)
    dirs = DataDirs.from_root(root / "userdata")
    (dirs.maps / "beta").mkdir(parents=True)

    assert migrate_dev_layout(root, dirs) == []
    assert (root / "maps" / "alpha" / "meta.json").is_file()
    assert not (dirs.maps / "alpha").exists()


def test_migrate_removes_an_empty_destination_directory_so_the_move_can_proceed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "app"
    _dev_layout(root)
    dirs = DataDirs.from_root(root / "userdata")
    dirs.ensure()  # leaves maps/, routes/ and logs/ empty, which is not data

    moved = migrate_dev_layout(root, dirs)

    assert "maps" in moved
    assert (dirs.maps / "alpha" / "meta.json").is_file()
    assert not (root / "maps").exists()


def test_migrate_skips_an_entry_whose_destination_already_holds_data(tmp_path: Path) -> None:
    root = tmp_path / "app"
    _dev_layout(root)
    dirs = DataDirs.from_root(root / "userdata")
    dirs.routes.mkdir(parents=True)
    (dirs.routes / "keep.json").write_text("{}", encoding="utf-8")

    moved = migrate_dev_layout(root, dirs)

    assert "routes" not in moved
    assert "maps" in moved
    assert (root / "routes" / "r1.json").is_file()  # left where it was, not merged
    assert (dirs.routes / "keep.json").is_file()
    assert not (dirs.routes / "r1.json").exists()


# --- run_migration: a failed migration never costs the start-up ---------------------------


def _failure_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == paths_module.__name__ and r.exc_info]


def test_run_migration_hands_back_what_the_migration_moved(tmp_path: Path) -> None:
    root = tmp_path / "app"
    _dev_layout(root)
    dirs = DataDirs.from_root(root / "userdata")

    moved = run_migration("moving", lambda: migrate_dev_layout(root, dirs))

    assert moved == ["maps", "routes", "legacy_routes", "settings.json", "state.json"]


def test_a_data_directory_that_is_a_file_fails_the_migration_without_raising(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # A file where the data directory is expected: migrate_dev_layout has nowhere to move to,
    # and on its own raises FileExistsError. The simplest move failure to build on every OS;
    # the app itself is covered with a held file in tests/test_app_migration.py.
    root = tmp_path / "app"
    _dev_layout(root)
    (root / "userdata").write_text("not a directory", encoding="utf-8")
    dirs = DataDirs.from_root(root / "userdata")
    with pytest.raises(OSError):
        migrate_dev_layout(root, dirs)

    with caplog.at_level(logging.ERROR):
        moved = run_migration("moving the old layout", lambda: migrate_dev_layout(root, dirs))

    assert moved is None
    [record] = _failure_records(caplog)
    assert record.getMessage() == "moving the old layout failed"
    assert (root / "maps" / "alpha" / "meta.json").is_file()  # nothing was lost on the way


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows refuses to move an open file")
def test_a_file_held_open_by_another_program_fails_the_migration_without_raising(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The unreadable-file case: antivirus or an editor holding one of the files open."""
    root = tmp_path / "app"
    _dev_layout(root)
    locked = root / "legacy_routes" / "old" / "overlay.png"
    locked.parent.mkdir(parents=True)
    locked.write_bytes(b"png")
    dirs = DataDirs.from_root(root / "userdata")

    with locked.open("rb"), caplog.at_level(logging.ERROR):
        moved = run_migration("moving the old layout", lambda: migrate_dev_layout(root, dirs))

    assert moved is None
    assert len(_failure_records(caplog)) == 1
    assert locked.is_file()
    assert dirs.settings.is_file()  # the entries after the held one were still moved
    assert dirs.state.is_file()


def test_an_entry_that_cannot_be_moved_does_not_keep_the_rest_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Once maps/ has moved this never looks at the app root again, so an entry left untried
    # behind a failed one would stay there for good: settings.json there is settings the app
    # never reads.
    root = tmp_path / "app"
    _dev_layout(root)
    dirs = DataDirs.from_root(root / "userdata")
    real_move = shutil.move

    def move(src: str, dst: str) -> object:
        if Path(src).name == "legacy_routes":
            raise PermissionError(13, "held open by another program", src)
        return real_move(src, dst)

    monkeypatch.setattr(shutil, "move", move)

    with pytest.raises(ExceptionGroup) as failed:
        migrate_dev_layout(root, dirs)

    assert [type(e) for e in failed.value.exceptions] == [PermissionError]
    assert (dirs.maps / "alpha" / "meta.json").is_file()
    assert dirs.settings.is_file()
    assert dirs.state.is_file()
    assert (root / "legacy_routes").is_dir()
    assert not dirs.legacy.exists()


def test_run_migration_lets_an_interrupt_through() -> None:
    # Exception, not BaseException: Ctrl+C during start-up still stops the app.
    def interrupted() -> list[str]:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_migration("moving", interrupted)


# --- install_root: the Velopack layout -----------------------------------------------------


def _velopack_at(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    """A Velopack install: the exe in <root>/current/, Update.exe beside current/.

    Returns the resolved install root, for the same short-name reason as `_freeze_at`.
    """
    _freeze_at(monkeypatch, root / "current")
    (root / "Update.exe").write_bytes(b"")
    return root.resolve()


def test_install_root_is_the_executable_folder_for_a_plain_copy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _freeze_at(monkeypatch, tmp_path / "usb" / "Map Overlay")
    assert install_root() == root


def test_install_root_steps_out_of_current_when_velopack_owns_the_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _velopack_at(monkeypatch, tmp_path / "app")
    assert install_root() == root
    assert app_root() == root / "current"  # unchanged: resources and migration rely on it


def test_a_folder_named_current_without_update_exe_is_not_a_velopack_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Someone may well unpack a portable copy into a folder called "current". Without
    # Update.exe beside it, stepping out would put userdata/ one level above their copy.
    exe_dir = _freeze_at(monkeypatch, tmp_path / "somewhere" / "current")
    assert install_root() == exe_dir


def test_portable_userdata_sits_beside_current_so_an_update_cannot_delete_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Velopack replaces current/ wholesale, so data inside it would not survive an update."""
    root = _velopack_at(monkeypatch, tmp_path / "app")
    (root / "portable.txt").write_text("", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert user_data_dir() == root / "userdata"
    assert is_portable() is True


def test_a_marker_left_inside_current_does_not_make_a_velopack_install_portable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The first update would delete a marker kept there, and the data would move to
    # %LocalAppData% without warning. Only the root counts, so that cannot happen silently.
    root = _velopack_at(monkeypatch, tmp_path / "app")
    (root / "current" / "portable.txt").write_text("", encoding="utf-8")
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    assert is_portable() is False
    assert user_data_dir() == local / APP_DIR_NAME


def test_velopacks_own_marker_makes_its_portable_zip_portable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """vpk's Portable.zip has an empty .portable at its root, beside Update.exe, and no
    portable.txt; Velopack reads the copy as portable by that file alone."""
    root = _velopack_at(monkeypatch, tmp_path / "app")
    (root / ".portable").write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert is_portable() is True
    assert user_data_dir() == root / "userdata"


def test_a_velopack_marker_inside_current_does_not_make_the_copy_portable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Velopack looks for .portable at the root only, and the first update would delete one kept
    # in current\ -- the same reason portable.txt counts only at the root.
    root = _velopack_at(monkeypatch, tmp_path / "app")
    (root / "current" / ".portable").write_bytes(b"")
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    assert is_portable() is False
    assert user_data_dir() == local / APP_DIR_NAME


# Velopack installs to %LocalAppData%\<packId>\ and removes that whole folder on an uninstall. A
# repair, a reinstall, or a first install over a non-empty folder of that name renames it away and
# deletes it once the install succeeds. A PACK_ID equal to APP_DIR_NAME would make it the folder an
# installed copy keeps its maps, routes and settings in.
def test_an_installed_copy_keeps_its_data_outside_the_folder_velopack_owns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    # Where Setup.exe installs: %LocalAppData%\<packId>\current\, with no portable marker.
    _velopack_at(monkeypatch, local / PACK_ID)

    data, owned = user_data_dir(), install_root()
    assert not _within(data, owned), f"user data {data} is inside the install folder {owned}"


# --- is_portable ---------------------------------------------------------------------------


def test_a_build_without_the_marker_is_not_portable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_at(monkeypatch, tmp_path / "install")
    assert is_portable() is False


def test_a_build_with_the_marker_beside_it_is_portable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _freeze_at(monkeypatch, tmp_path / "usb" / "Map Overlay")
    (root / "portable.txt").write_text("", encoding="utf-8")
    assert is_portable() is True


def test_a_source_checkout_is_never_portable_even_with_the_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Portable changes how a build behaves on someone else's machine; a checkout has no such
    machine. Faked through the module's own location, the one input app_root() reads when
    unfrozen, so the marker can exist without touching the real repository."""
    _unfreeze(monkeypatch)
    repo = tmp_path / "repo"
    fake = repo / "src" / "map_overlay" / "core" / "paths.py"
    fake.parent.mkdir(parents=True)
    monkeypatch.setattr(paths_module, "__file__", str(fake))
    (repo / "portable.txt").write_text("", encoding="utf-8")
    assert portable_marker().exists()  # the marker really is where the check looks

    assert is_portable() is False
