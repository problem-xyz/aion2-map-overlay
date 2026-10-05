# Timers data

The files the app fetches for its event timers, newer than the copies it ships with:

- `timers/schedule.json` -- when each event runs in each server region
- `timers/world-bosses.json` -- the world bosses' respawn times, read off the in-game list

A change here reaches players at their next check (within six hours, or at once with
"Update now"), without a new release. Both files are checked whole before the app uses them;
a broken one is ignored and the app keeps the copy it had. The formats are those of the files
under `assets/timers/` on `main`.
