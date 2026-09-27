"""Lint the modules ruff's exclude list skips, for real breakage only.

An entry there lets a module's pre-existing style findings wait for a cleanup instead of
blocking work. The side effect is that ruff also stops reporting syntax errors and undefined
names in them -- a file can be left unparseable and `ruff check .` will still say everything
passed. This ran in anger: a bad edit shipped an unterminated string that only surfaced when
the app was started.

Style stays excluded; only what would actually fail at runtime is checked here.
"""

import subprocess
import sys
from pathlib import Path

RULES = "F821,F811,F841,E9"
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = sorted(str(p) for p in (ROOT / "src").rglob("*.py"))
    if not files:
        return 0
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-force-exclude",
            "--select",
            RULES,
            "--output-format",
            "concise",
            *files,
        ],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
