# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries describe what a user of the app would notice. Internal refactors, tooling and CI
changes are left out unless they change how the app is installed, run or updated.

## [Unreleased]

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
