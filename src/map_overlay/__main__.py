import logging
import sys

import velopack

# Velopack runs its install, update and uninstall hooks inside this call and may end the process
# there, so it has to precede every side effect, and importing map_overlay.app is already one:
# that sets the Qt scaling variable and claims DPI awareness. It lives here rather than at the
# top of map_overlay.app so that importing that module, as a test may, never runs Velopack.
#
# A build has made the call already, from packaging/rthook_velopack.py: there PyInstaller's own
# PySide6 hook imports Qt before this file runs. The two must stay the same.
if not getattr(sys, "frozen", False):
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

from map_overlay.app import main

sys.exit(main())
