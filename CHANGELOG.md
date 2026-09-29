# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries describe what a user of the app would notice. Internal refactors, tooling and CI
changes are left out unless they change how the app is installed, run or updated.

## [Unreleased]

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
