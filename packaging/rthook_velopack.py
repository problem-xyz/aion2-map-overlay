# PyInstaller runtime hook: Velopack's start-up call, as early as a build can make it.
#
# Velopack runs its install, update and uninstall hooks inside App().run() and may end the process
# there, so the call has to precede everything else. In a build, __main__.py is too late for that:
# PyInstaller's own PySide6 runtime hook imports PySide6.QtCore before the entry script runs.
# Custom runtime hooks run ahead of PyInstaller's own, which makes this the earliest point there is.
#
# A source run makes the same call from src/map_overlay/__main__.py, which skips it in a build.
# The two must stay the same.
#
# Every runtime hook and the entry script execute in the one __main__ namespace. Hence comments
# rather than a docstring, which would become __main__.__doc__, and a function that deletes
# itself, the shape PyInstaller gives its own hooks.


def _velopack_first() -> None:
    import logging  # noqa: PLC0415 -- kept out of the shared __main__ namespace, see above

    import velopack  # noqa: PLC0415

    # Logging is not set up yet, and outside an install run() logs an ERROR (NotInstalled) that
    # logging's last-resort handler would print on every start. The level is for afterwards: the
    # extension fixes a logger's level at that logger's first record, and for some of them this
    # call is it, so inheriting root's WARNING here would filter their INFO records for good.
    velopack_log = logging.getLogger("velopack")
    velopack_log.addHandler(logging.NullHandler())
    velopack_log.setLevel(logging.INFO)
    # No applying at start-up: this runs before the single-instance check, and a second launch
    # that applied a downloaded update would have Update.exe kill the copy already running. The
    # updater applies it when the app closes instead (updater/service.py).
    velopack.App().set_auto_apply_on_startup(False).run()


_velopack_first()
del _velopack_first
