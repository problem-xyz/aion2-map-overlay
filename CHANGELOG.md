# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries describe what a user of the app would notice. Internal refactors, tooling and CI
changes are left out unless they change how the app is installed, run or updated.

## [Unreleased]

### Added

- A Resources button beside Cubes shows the map's gathering points over the game: odyle, ore,
  gems, wood, herbs and the rest, each with a mark of its own. The arrow beside it opens the list
  of the map's resources; tick the ones to show. Like the cubes, they stay on whatever the route
  does, and with them on the overlay starts without a route.

### Changed

- Started without a route, the overlay no longer asks which map to show the cubes and resources
  on: it finds the map you have open, and when you open another, it follows within a few seconds.
- The route editor lists the gathering points under a Gathering category, one entry per
  resource. They start hidden there; the eye shows them, and a point dropped on one snaps to it.

## [1.4.0] - 2026-10-01

### Added

- A Cubes button beside Arrows shows every hidden cube of the map over the game, each in a ring.
  The cubes stay on whatever the route does, finished or not, and with the arrows off. The
  ring's size is a slider under Route over the game, 20 pixels to start with.
- With Cubes on, the overlay starts without a route: it asks which map to show the cubes on.
- The overlay says what it is doing over the map itself: that it is looking for the map, and
  what to try when it cannot find it, and why it stopped when it stops with an error.
- Far off the route, the overlay says so, with the number of the next point and which way it
  lies. It draws the whole route, faded, so you can see where it runs, and a next point off the
  map gets its number on the edge, pointing its way. Standing at a later point of the route, you
  are asked whether to go on from there, with a Yes and a No to click.
- A Feathers button leaves the route's points on Empyrean Traces out of the map, the checklist
  and the step count, and a Dungeons button does the same for sealed dungeons. Turned back on,
  they return with your progress kept. Both sit with Cubes in a row of their own under Start.

### Fixed

- Selecting the map area again while the overlay runs no longer stops it with an error.
- The map is found at closer zoom levels than before, where it used to be lost every few
  seconds. The first start on each map takes a few seconds longer, once; every start after it
  is faster than before.

## [1.3.0] - 2026-09-30

### Added

- Five routes for Elyos in Verteron, from the start village to level 45.
- The route list can show only Asmodian or only Elyos routes, once it has routes for both. A
  route counts for the side whose map it is drawn on.
- The routes that come with the app carry an Official tag. A route you edited no longer does.
- A link to the Discord server of Aion 2 Global, a community the project works with, beside the
  project's own Discord in the panel.
- A banner for LagoFast, the game booster, with a 30% discount code under it that a click
  copies.

### Changed

- The Asmodian routes are numbered in the order you play them, like the Elyos ones. Your progress
  on them is kept. A route you edited keeps its old name.
- The checklist over the game is on from the first start. If you turned it off, it stays off.
- A route you copy into the routes folder, or delete from it, shows in the list at once, with no
  need to restart the app. A route you edit there by hand is redrawn on the map.
- At the foot of the panel, the ways to support the project and the community links are two
  groups, each under its own heading. Between them is a place for an advertising banner.

## [1.2.0] - 2026-09-29

### Added

- A new route for Asmodians: levels 35-45 through Kromede and Zikel.

## [1.1.0] - 2026-09-29

### Added

- Two new routes for Asmodians: levels 22-30 through Urugugu, and levels 30-35 with the main
  story and side quests.

### Changed

- The routes that come with the app now get their new version with an update, as long as you
  never edited them. Routes you made, edited or deleted are left as they are.

### Fixed

- With HDR turned on in Windows, the overlay finds the map again. The app used to see a
  washed-out picture of the game and could not recognise the map in it.
- The app no longer crashes now and then after a few hours with the overlay on.

## [1.0.1] - 2026-09-28

### Added

- After a crash, `crash.log` in the app's `logs` folder records what happened. Send it along
  with `map-overlay.log` when you report a problem.

### Changed

- The app barely uses the CPU and graphics card while you play. The shimmer on the menu and the
  Start button pauses while the window is not in focus, and the current step on the checklist no
  longer shimmers.

### Fixed

- On AMD graphics cards the app no longer fills up memory and crashes within a minute of
  starting.
- If the app crashes inside the graphics driver, it recovers by itself: on the next start it
  switches the part that failed to a safer mode and tells you so.

## [1.0.0] - 2026-09-27

### Added

- First release.
