"""scripts/collect_licenses.py, which keeps the licence notices the build carries current.

The first test is the reason the file exists: when uv.lock or ui/package-lock.json changes and
packaging/third-party/ is not regenerated, or a curated folder is left behind by an upgrade, CI
fails here instead of a release shipping a package without its licence. The check reads the
installed packages and the lockfile only, so it needs no network and no ui/node_modules.

The script is a command-line tool rather than a module of the app, so it is loaded by path, as
test_release_scripts.py loads its scripts.
"""

import importlib.util
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collect = load_script(REPO / "scripts" / "collect_licenses.py", "collect_licenses")


def test_the_committed_notices_match_the_locked_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def offline(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the check must not reach the network")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    problems = collect.check()
    advice = "regenerate: uv run python scripts/collect_licenses.py"
    assert problems == [], "\n".join([*problems, advice])


def test_a_component_with_no_licence_text_stops_the_run() -> None:
    """How a new dependency without a licence file is kept out of a release."""
    bare = collect.Component(name="left-pad", version="1.3.0", licence="?")
    with pytest.raises(collect.NoticeError, match=r"left-pad 1\.3\.0"):
        collect.require_texts([bare])
    collect.require_texts(collect.CURATED)  # the runtime without a text says why instead


def test_a_curated_folder_left_at_an_older_version_asks_for_new_texts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collect, "version_of", lambda name: "0.0.1")
    problems = collect.curated_problems(interpreter=False)
    assert "update the texts in velopack/ by hand" in "\n".join(problems)
    assert not any("cpython/" in p for p in problems), "only the build checks the interpreter"
    assert any("cpython/" in p for p in collect.curated_problems(interpreter=True))


def test_the_ui_closure_is_what_node_would_load_at_run_time() -> None:
    """Nested copies win over hoisted ones, peers are followed, dev-only packages are not."""
    lock = {
        "packages": {
            "": {"dependencies": {"a": "^1"}, "devDependencies": {"tool": "^1"}},
            "node_modules/a": {"version": "1.0.0", "dependencies": {"b": "^2"}},
            "node_modules/b": {"version": "1.0.0"},
            "node_modules/a/node_modules/b": {"version": "2.0.0", "peerDependencies": {"c": "*"}},
            "node_modules/c": {"version": "3.0.0"},
            "node_modules/tool": {"version": "1.0.0", "dev": True},
        }
    }
    assert list(collect.npm_closure(lock)) == [
        "node_modules/a",
        "node_modules/a/node_modules/b",
        "node_modules/c",
    ]


def test_a_ui_package_new_to_the_lockfile_asks_for_a_full_run() -> None:
    """The check has no ui/node_modules to read the new licence from, and says so."""
    with pytest.raises(collect.NoticeError, match="npm/left-pad/ is not in packaging/third-party"):
        collect.npm_texts("left-pad", "1.3.0", live=False)


def test_a_missing_runtime_package_in_the_lockfile_is_an_error() -> None:
    lock = {"packages": {"": {"dependencies": {"gone": "^1"}}}}
    with pytest.raises(collect.NoticeError, match="gone"):
        collect.npm_closure(lock)


def test_an_excerpt_is_the_exact_lines_asked_for() -> None:
    data = b"/* one\r\n two */\r\ncode\n"
    assert collect.excerpt(data, (1, 2)) == b"/* one\r\n two */\r\n"
    with pytest.raises(collect.NoticeError):
        collect.excerpt(data, (2, 9))
