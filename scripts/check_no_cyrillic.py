"""Fail if Cyrillic appears anywhere it is not supposed to.

The language policy is simple: code, comments, docs and commit messages are English, and Russian
lives in exactly two kinds of file -- `locales/ru.json` and `*.ru.md`. This script is what
makes that true rather than aspirational, because a reviewer will not notice one Russian comment
in a large diff.

Ruff's RUF001-003 look like the right tool and are not: they flag "ambiguous unicode", which is a
homoglyph-attack rule, and they know nothing about which of our files are allowed to be Russian.

A line that genuinely needs Cyrillic in an otherwise-English file carries an `allow-cyrillic`
marker in a comment, with the reason. That is deliberately per-line rather than a growing list of
paths in here: the exception then lives next to the thing it excuses, and it shows up in the diff
that introduces it.

Note the pattern below is written with escapes. A Cyrillic detector spelled with Cyrillic letters
reports itself, which happened three times before anyone noticed.
"""

import re
import sys
from pathlib import Path

CYRILLIC = re.compile(r"[\u0400-\u04FF]")
ALLOW_MARKER = "allow-cyrillic"

REPO = Path(__file__).resolve().parents[1]

# Where Russian belongs, and where text is illustrative rather than shipped.
ALLOWED_FILES = {"locales/ru.json"}
ALLOWED_DIRS = (
    "docs/",  # local, git-ignored notes, which may be in any language
    ".claude/",  # local Claude Code configuration and worktrees, git-ignored
)
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "userdata",
    ".pytest_cache",
    ".ruff_cache",
}

# Everything textual we ship or maintain. Binary and generated files are not read.
SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".css",
    ".html",
    ".json",
    ".jsonc",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".cfg",
    ".ini",
    ".bat",
    ".ps1",
    ".txt",
}


def is_allowed(rel: str) -> bool:
    """Whole files that are permitted to be Russian."""
    return (
        rel in ALLOWED_FILES
        or rel.endswith(".ru.md")
        or any(rel.startswith(d) for d in ALLOWED_DIRS)
    )


def walk() -> list[Path]:
    found = []
    for path in REPO.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(REPO).parts):
            continue
        found.append(path)
    return sorted(found)


def offences(path: Path) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return []  # not text we can judge; nothing to police
    out = []
    for number, line in enumerate(text.splitlines(), 1):
        if CYRILLIC.search(line) and ALLOW_MARKER not in line:
            out.append((number, line.strip()))
    return out


def main() -> int:
    # The console on Windows is cp1252, and every line this script reports is Cyrillic by
    # definition -- printing a finding would otherwise raise UnicodeEncodeError and hide the
    # report behind a traceback.
    stream = getattr(sys.stdout, "reconfigure", None)
    if callable(stream):
        stream(encoding="utf-8", errors="backslashreplace")

    bad = []
    for path in walk():
        rel = path.relative_to(REPO).as_posix()
        if is_allowed(rel):
            continue
        for number, line in offences(path):
            bad.append(f"{rel}:{number}: {line[:100]}")
    if not bad:
        return 0
    print(f"Cyrillic outside locales/ru.json and *.ru.md ({len(bad)} lines):")
    for entry in bad:
        print(f"  {entry}")
    print()
    print("Move the text into locales/*.json and call t(), or, if the line genuinely needs")
    print(f"Cyrillic, add an `{ALLOW_MARKER}: <reason>` comment on it.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
