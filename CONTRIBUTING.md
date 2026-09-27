# Contributing

Thank you for helping. This is a small project run by one maintainer, so the most useful
contribution is often a bug report with the environment fields filled in. Code, documentation
and translations are welcome too; this page covers how to get set up, the checks a pull request
has to pass and the rules the review holds it to, and ends with how a release is cut.

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). **Security problems are
not reported in issues**: see [`SECURITY.md`](SECURITY.md) for the private route.

## Before you start

- **Bug reports and ideas** go in [issues](https://github.com/problem-xyz/aion2-map-overlay/issues),
  through the bug report or feature request form.
- **Small fixes** (a bug, a typo, a wrong sentence in the docs) can go straight to a pull
  request.
- **Anything larger** (a new feature, a new dependency, a change to how a window behaves) needs
  an issue first, so that nobody spends an evening on something that cannot be merged.

## Setup

You need Windows 10 or 11, [Python 3.14](https://www.python.org/downloads/),
[uv](https://docs.astral.sh/uv/) and Node.js: 22.22.2 or later on the 22 line, 24.15 or later
on the 24 line, or 26 and newer. The UI tests run in jsdom, which needs one of those, and CI
uses Node 22.

```bash
git clone https://github.com/<you>/aion2-map-overlay   # your fork
cd aion2-map-overlay
uv sync                                                # Python environment in .venv
cd ui && npm ci && npm run build                       # the interface, into ui/dist/
```

The UI build output (`ui/dist/`) is not stored in git, so that last step is required before the
first run.

## Run

```bash
uv run python app.py         # normal run, UI from ui/dist
scripts\dev.ps1              # dev server + the app against it, with hot reload
```

`scripts\dev.ps1` starts Vite in the background, waits for it, runs the app with `--dev`, and
stops the dev server again on exit. To drive the two halves yourself, run `cd ui && npm run dev`
in one shell and `uv run python app.py --dev` in another.

`--data-dir <folder>` keeps your test maps and routes away from the checkout's own `userdata/`.
The game must be in borderless windowed mode; overlays cannot be drawn on top of exclusive
fullscreen.

## Checks before opening a pull request

These are what CI runs, and a pull request has to pass all of them:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/check_no_cyrillic.py
uv run pytest
cd ui && npm run check && npm run build    # lint, formatting, types, tests, then the bundle
```

`uvx pre-commit install` wires the repository's hooks (ruff, file hygiene and the Cyrillic
check) into `git commit`, and `uvx pre-commit run --all-files` runs them once by hand.

Anything that touches runtime behaviour also needs a manual try of the feature in the running
app. The automated tests deliberately cover none of the screen capture, overlay painting or
QtWebEngine surface, so say in the pull request what you tried and on what setup.

## Opening a pull request

1. Fork the repository and branch from `main`. Name the branch `<type>/<slug>`, for example
   `fix/route-code-paste` or `feat/update-banner`. Types are `feat`, `fix`, `chore`, `docs` and
   `refactor`.
2. Keep one change per pull request. Commits follow
   [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`,
   imperative and lower case, with a body that explains what changed and why.
3. Fill in the pull request template. It carries the checklist the review goes through; strike
   out what does not apply and say why.
4. If a user of the app would notice the change, add an entry under `[Unreleased]` in
   [`CHANGELOG.md`](CHANGELOG.md), in the same pull request. Update any documentation the
   change makes wrong: `README.md` and `README.ru.md`.

`main` is protected, and a pull request can only be merged once both CI jobs, `python` and `ui`,
are green. Pull requests are squash-merged, so write the pull request title as a Conventional
Commits summary too.

## Language

- Everything written in this repository is **English**: code, comments, docstrings, commit
  messages, pull requests and documentation. Russian belongs only in `README.ru.md` and
  `locales/ru.json`. `scripts/check_no_cyrillic.py` enforces this.
- Text the user sees is never written as a literal in code. Python emits a `notify` code, the
  UI calls `t("…")`, and the wording lives in `locales/en.json` and `locales/ru.json`, shared by
  both sides. A new key goes into both files; the tests fail when their keys differ. If you do
  not write Russian, put the English text in `ru.json` too and say so in the pull request.
- A change to user-facing text in `README.md` has a counterpart in `README.ru.md`, with the
  same headings in the same order.

## Project layout

```
app.py                  entry point for a source checkout: python app.py [--dev]
run.bat                 the same, by double-click
src/map_overlay/
  app.py                process setup, single instance, control window
  core/                 settings and state schema, paths, atomic file IO, logging, errors
  store/                maps, routes, tiles, object sets, share codes
  vision/               screen capture, feature matching, optical flow, the engine thread
  qt/                   control, editor, steps and overlay windows; region picker; Win32 calls
  bridge/               the QWebChannel Backend the UI talks to
  i18n/                 catalogue loader for the strings Python emits
ui/
  src/app/              window shell and page selection
  src/features/         panel, editor, steps — one folder each
  src/shared/           backend transport, i18n runtime, shared components, styles
  src/dev/              mock backend for running the UI without Python
  dist/index.html       build output, not in git
locales/                en.json, ru.json — shared by Python and the UI
assets/object-sets/     ready-made points of interest (CC BY-NC 4.0, see NOTICE)
tests/                  pytest suite
scripts/                developer scripts
userdata/               maps, routes, settings and logs in a checkout; git-ignored
```

The pages talk to Python through a `backend` object over QWebChannel; its slots and signals are
a frozen contract, described in the next section.

## Two things that need a decision before you change them

- **The UI contract.** `src/map_overlay/bridge/backend.py` exposes a fixed set of slots and
  signals to the React UI, and the `steps` object a few more. Changing the signature of an
  existing one, or changing the route, map or object-set file formats, breaks saved user data
  or the UI built against it. Add new slots or optional fields instead, and bump `api` in
  `getState()`.
- **Dependencies, telemetry and network access.** A new runtime dependency needs a
  justification in the pull request, and its licence goes into the build's notices:
  `uv run python scripts/collect_licenses.py` regenerates `packaging/third-party/` (it needs
  `ui/node_modules`), and `pytest` fails until it has. Upgrading Qt, OpenCV, Velopack or the
  Python the build uses also means updating their hand-kept texts in `packaging/third-party/`;
  the script says which folder, and the index in that folder where the texts come from. The app does
  not and will not collect telemetry, read or change game memory, inject anything into the game
  or send input to it. The only network access it will ever have is the update check and
  download from GitHub.

## Licence of contributions

The app is under its own licence, [LICENSE](LICENSE): its source is public, but the licence is
not an open-source one. By opening a pull request you agree that the maintainer
may use your contribution under the app's licence as it is then and as it changes, open source
included. The maps and object sets in `assets/` are the exception: they are CC BY-NC 4.0 data
from another project (see [`NOTICE`](NOTICE)), so a change to them stays under that licence and
has to keep the attribution.

## Releasing

From an up-to-date `main` with the release's entries under `## [Unreleased]` in `CHANGELOG.md`,
and with the tags fetched (`git fetch --tags`) -- the script checks the new version against the
tags in your clone, so a missing one lets it cut a release that sorts below one already out:

```bash
uv run python scripts/bump_version.py 1.0.0-beta.1 --dry-run   # read the diffs it prints
uv run python scripts/bump_version.py 1.0.0-beta.1             # commit and tag v1.0.0-beta.1
git push --atomic origin main v1.0.0-beta.1                    # the tag starts the release
```

The script writes the version into `src/map_overlay/__init__.py`, which is its one source, and
into `ui/package.json` and `ui/package-lock.json`; moves the `[Unreleased]` entries into a dated
section for the release, leaving `[Unreleased]` empty above it; commits that as
`chore(release): <version>` and creates the annotated tag `v<version>`. It pushes nothing. The
dry run writes nothing either, and works on a tree with uncommitted changes, so it can be run while
the changelog is still being edited.

The new version must be greater than the highest `v*` tag that is a version. It is not compared
with `__version__`, which between releases is only a placeholder, so the first release, made
while no such tag exists, may be any valid version; the dry run says so when that is the case.

It refuses, changing nothing, when the version is not strict SemVer 2.0.0 that the build can
stamp into the exe (`MAJOR.MINOR.PATCH[-PRERELEASE]`: ASCII, no leading zeros, no empty
identifiers, no `+build`, no leading `v`), is not a tag name git accepts, is not greater than the
highest release tag, or already has a tag; when `[Unreleased]` is empty or repeats a `###`
subsection (merge a second `### Added` into the first); when the repository has no git identity
of its own; and, on a real run only, when the working tree is not clean. `git config --local
user.name` and `user.email` must both be set: a release is never committed or tagged with your
global identity.

The release commit is the one commit that goes to `main` without a pull request. A squash merge
would put a different commit on `main` from the one the tag names. The tag is what the release
workflow builds from, and `scripts/check_version.py` fails that build if the tag and
`__version__` disagree.

### What the tag starts

`.github/workflows/release.yml` runs on the pushed tag, one release at a time, and publishes to
this repository, the one `REPO_URL` in `src/map_overlay/core/appinfo.py` names and installed apps
take updates from; in a fork it refuses to publish and only dry-runs. Before anything slow it
refuses a version that already has a release. Then it runs what CI runs (`npm run check`,
`pytest`) and `collect_licenses.py --check`, builds with `scripts/build.ps1 -SkipUi -NoPack`,
downloads the newest release's full package with `vpk download github` so the pack can make a
delta (the first release has none to download), and packs with `scripts/pack.ps1`. A second job,
the only one with write access, publishes with `vpk upload github --publish` and the workflow's
own token: a normal release, never a pre-release, named `<APP_NAME> <version>`, whose body is
`scripts/release_notes.py`'s output -- the version's CHANGELOG section and how to install. The
run's summary lists the SHA-256 of `Setup.exe`, `Portable.zip` and the packages.

A third job announces the published release in the Discord server's two download channels,
English and Russian, each seen only by its language role: the version's CHANGELOG section as
text, with buttons for `Setup.exe`, `Portable.zip` and the release page, which
`scripts/discord_announce.py` writes and posts. It posts to the webhooks in the secrets
`DISCORD_RELEASES_WEBHOOK_EN` and `DISCORD_RELEASES_WEBHOOK_RU` (in Discord: the channel's *Edit
Channel > Integrations > Webhooks*, *Copy Webhook URL*; then `gh secret set <name>`). A channel
whose secret is not set is skipped with a note. The optional repository variables
`DISCORD_RELEASES_ROLE_EN` and `DISCORD_RELEASES_ROLE_RU`, role ids, ping that role and no other
(`gh variable set <name>`). With the secret `DISCORD_BOT_TOKEN`, the token of a bot on the
server that may pin messages in both channels, each post is pinned and the previous release's
pin is taken down; without it, or when the pin is refused, the post goes out unpinned. To see
the message before a release, write a dry run (`--output announce.json`), or post one with the
webhook in `DISCORD_WEBHOOK` (and the token in `DISCORD_BOT_TOKEN` to pin it):

```bash
uv run python scripts/discord_announce.py 1.0.0-beta.1 --dry-run --post
```

A failed run leaves the tag in place. When the cause is in the tagged code, fix it on `main` and
cut the next version. When it was not (a runner or network failure) and nothing was published,
delete any draft release the run left and re-run it on the tag: *Actions > Release > Run
workflow*, the tag as the ref, its version, `dry_run` off. GitHub keeps one waiting run per
concurrency group and cancels an older waiting one, so a third tag pushed while a release runs
cancels the second tag's run; re-run that one the same way. Dry runs wait in a group of their
own and cannot cancel a release.

To try the whole pipeline without publishing, run it on a branch with `dry_run` on and the
version equal to that branch's `__version__`; the output is kept as the run's artifact for five
days. `__version__` stays at the last release until the next bump, so a dry run of a version
that is not newer than the latest release packs without a delta. GitHub runs a manual dispatch
only for a workflow that is on `main`; `--ref` then picks the branch whose copy runs:

```bash
gh workflow run release.yml --ref main -f version=1.0.0-beta.0 -f dry_run=true
```

The same pack works locally: `scripts/build.ps1` builds and then packs into `Releases/`, which
it empties first, so a local pack has no delta.
Packing needs the .NET SDK (8 or later) and `vpk` at the version of the `velopack` wheel in
`uv.lock`, which `pack.ps1` checks: `dotnet tool install -g vpk --version 1.2.158`.
