"""Which links openUrl() will hand to the browser."""

import pytest

from map_overlay.core.appinfo import DISCORD_URL, DONATE_URL, REPO_URL
from map_overlay.core.links import is_project_url


@pytest.mark.parametrize(
    "url",
    [
        f"{REPO_URL}/releases/tag/v1.0.0-beta.1",
        f"{REPO_URL}/releases",
        f"{REPO_URL}/issues/new",
        f"{REPO_URL}/blob/main/README.md#privacy",
        REPO_URL,
        DONATE_URL,
        DISCORD_URL,
    ],
)
def test_pages_of_the_repository_are_opened(url: str) -> None:
    assert is_project_url(url)


@pytest.mark.parametrize(
    "url",
    [
        # the donation page and the invite pass as they are, and nothing else on their sites
        f"{DONATE_URL}/extras",
        DONATE_URL.replace("problem_xyz", "someone_else"),
        "https://discord.gg/other",
        DISCORD_URL + "?x=1",
        DISCORD_URL.replace("https:", "http:"),
        # look-alikes of the repository, other repositories and other schemes
        REPO_URL.replace("https:", "http:") + "/releases",
        f"{REPO_URL}-evil/releases",
        "https://github.com/problem-xyz/other/releases",
        REPO_URL.replace("github.com", "gist.github.com") + "/x",
        REPO_URL.replace("github.com", "github.com.evil.example") + "/releases",
        REPO_URL.replace("https://", "https://user@") + "/releases",
        REPO_URL.replace("github.com", "github.com:8443") + "/releases",
        f"{REPO_URL}/../other/releases",
        f"{REPO_URL}/%2e%2e/other/releases",
        f"{REPO_URL}\\..\\other",
        f"{REPO_URL}/releases\n",
        "file:///C:/Windows/System32/calc.exe",
        "javascript:alert(1)",
        "",
    ],
)
def test_anything_else_is_refused(url: str) -> None:
    assert not is_project_url(url)


def test_a_value_that_is_not_a_string_is_refused() -> None:
    # The page sends JSON, not types: a null has to be refused, not crash the check.
    assert not is_project_url(None)  # pyright: ignore[reportArgumentType]
