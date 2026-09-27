# Starter routes

The routes in this folder ship with the app. On start, each one is copied into the user's
`routes/` folder, next to the routes they made themselves. This README stays in the repository
and is not part of the build.

## What an update does to a user's routes

| In the user's `routes/`                           | What happens                                                      |
| ------------------------------------------------- | ----------------------------------------------------------------- |
| A route of their own                              | Nothing. The app never deletes or rewrites it.                    |
| A starter route they never changed                | It is replaced by the new version; the old one becomes `<id>.json.bak`. |
| A starter route they edited                       | Nothing. Their edits win.                                         |
| A starter route they deleted                      | Nothing. It does not come back.                                   |
| No such route yet (a starter new in this release) | It is copied in.                                                  |

A route's id is its file name without `.json`. If a user already has a route of their own under
the same id, the starter route with that id is never given to them. Their route is not touched.

"Never changed" means the file's bytes are exactly those of a version a release shipped.
`shipped.sha256` lists the SHA-256 of each of those versions. When the app finds a digest from
that list on the user's copy, it knows the user never edited it, so replacing it loses nothing.
After a replacement, the panel shows a notice with the names of the routes that were updated.

## Adding a starter route

1. Draw the route in the editor and save it. Then copy its file from `userdata/routes/` in your
   checkout into this folder. The file name is the id, so pick one users are unlikely to have,
   for example `Asmodians_-_Level_22-25.json`.
2. Run `uv run pytest tests/bridge/test_starter_routes.py`. It checks that the file is a valid
   route on a bundled map and is saved in the app's own format.
3. Add an entry to `CHANGELOG.md` under `[Unreleased]`.

## Updating a starter route that has shipped

1. Change the file in place and keep its name. A new name makes it a separate route, and users
   who have the old one end up with both.
2. Leave `shipped.sha256` alone. The line for the version users have now is already there,
   because the release that shipped it added that line.
3. Add a `CHANGELOG.md` entry, for example "Starter route X: fixed step 12".

On the next release, `scripts/bump_version.py` adds the new version's digest to `shipped.sha256`
and commits it with the release. Never remove a line for a route that still ships. Without it,
users who still have that version would stop getting updates for the route.

## Renaming or removing a starter route

Renaming a starter route amounts to removing it and adding a new one, so avoid it: users who had
the old one end up with both. After a rename or a removal, users keep the old file as a route of
their own. Delete the old id's lines from `shipped.sha256`. A test fails while that file names a
route that is not in this folder.
