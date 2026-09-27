# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries describe what a user of the app would notice. Internal refactors, tooling and CI
changes are left out unless they change how the app is installed, run or updated.

## [Unreleased]

### Changed

- The app no longer uses the CPU and GPU while you play: the shimmer on the selected tab and
  the Start button pauses while its window is not in focus, and the current step on the checklist
  over the game no longer shimmers at all. An idle panel used about a third of a CPU core on it.

### Added

- When the app crashes inside a graphics driver or other native code, `logs/crash.log` now
  records where it was, so a bug report can say what failed. The log also names the graphics
  card and driver version.

### Fixed

- On AMD graphics cards the app no longer eats memory until it crashes, within a minute of
  starting. It draws its windows through Direct3D 11 there.
- A crash inside the graphics driver no longer repeats. On the next start the app switches the
  part that crashed (screen capture, or how its windows are drawn) to a slower but safer method
  and says so.

## [1.0.0] - 2026-09-27

### Added

- First release.
