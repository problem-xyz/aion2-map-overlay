"""Entry point for running from a source checkout: python app.py [--dev]."""

import runpy

if __name__ == "__main__":
    # The module the build starts from, so that a checkout starts up in the same order, the
    # Velopack call first, and the two entry points cannot drift apart.
    runpy.run_module("map_overlay", run_name="__main__")
