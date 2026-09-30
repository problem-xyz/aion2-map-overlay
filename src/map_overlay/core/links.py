"""Which web links the app will open for the page.

The page can ask Python to open a URL in the user's browser (release notes). A page is
code that could one day be tricked into asking for something else, so the check is Python's:
only https pages inside this project's own repository pass, and anything that could step out
of it -- another host, credentials, a port, a dot segment, a backslash -- is refused. The
repository itself, the donation page and the two Discord invites pass as exact addresses only.
"""

from urllib.parse import unquote, urlsplit

from map_overlay.core.appinfo import DISCORD_URL, DONATE_URL, PARTNER_DISCORD_URL, REPO_URL

_EXACT = frozenset({REPO_URL, DONATE_URL, DISCORD_URL, PARTNER_DISCORD_URL})


def is_project_url(url: str) -> bool:
    """True for an https URL on the repository's own pages, or one of the project's links."""
    if not isinstance(url, str) or "\\" in url or any(ord(c) < 0x21 for c in url):
        return False
    if url in _EXACT:
        return True
    base = urlsplit(REPO_URL)
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.netloc != base.netloc or port is not None:
        return False
    path = unquote(parts.path)
    if not path.startswith(base.path + "/"):
        return False
    return ".." not in path.split("/")
