"""Names the app is known by, in one place.

Everything that ends up in a path, a window title, an installer or an update feed reads from
here, so that renaming the app is a single edit rather than a search across the tree.
"""

# The name users see: window titles, the exe, the installer, shortcuts and Apps.
# The two ids below name folders, and were renamed to match it before the first release:
# after one, a new id is a new app beside the old, and its data is left behind.
APP_NAME = "Aion 2 - Map Overlay"
# CompanyName in the exe's version resource: the account the releases come from.
ORG_NAME = "problem-xyz"

# The installer's publisher in Programs and Features (`vpk pack --packAuthors`): the GitHub
# account the releases are published from.
PUBLISHER = "problem-xyz"

# Directory under %LocalAppData% that holds the user's data. Kept free of spaces and punctuation,
# because it also shows up in log paths and in support requests. "Data" says what it is beside
# the program's own folder, PACK_ID.
APP_DIR_NAME = "Aion2MapOverlayData"

# Package id for the installer and the update feed: a NuGet id, so no spaces. It names the
# folder Setup.exe installs into, %LocalAppData%\<packId>, and the release files
# (<packId>-win-Setup.exe). An uninstall deletes that folder whole and a repair or a first
# install over it renames it away, so it must never equal APP_DIR_NAME, not even in letter case
# alone, as Windows paths ignore case: the user's data would then sit inside that folder.
PACK_ID = "Aion2MapOverlay"

# The project's repository: source, releases, issues and the README. openUrl() opens nothing
# outside it bar the two pages below, and the release notes link is built from it.
REPO_URL = "https://github.com/problem-xyz/aion2-map-overlay"

# The two pages beside the repository that the panel's support tiles open: a donation page and
# the players' Discord server. openUrl() opens these exact addresses and nothing else on their
# sites.
DONATE_URL = "https://buymeacoffee.com/problem_xyz"
DISCORD_URL = "https://discord.gg/DV2SNF6PMh"

# The update feed: the files of the newest GitHub release, releases.win.json and the packages,
# which GitHub serves by redirect with no API call and no rate limit. The trailing slash matters,
# since file names are resolved against it. The updater hands it to Velopack as an explicit
# HttpSource: given as a plain string, a github.com URL is taken for a repository and sent to
# GitHub's API, where this path does not exist (measured: 404).
UPDATE_URL = f"{REPO_URL}/releases/latest/download/"
