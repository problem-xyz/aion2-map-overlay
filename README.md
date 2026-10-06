[Русская версия](README.ru.md) <!-- allow-cyrillic: a reader looking for the Russian README has to recognise this link -->

# Aion 2 - Map Overlay

Aion 2 - Map Overlay draws your own route on top of the Aion 2 map. You place numbered points
once, and the app finds the map on screen and keeps the route on it while you move and zoom
the map. It also counts down the game's events, with a plaque over the game and a sound before
each one starts.

It is a free, unofficial fan project for Windows 10 and 11.

## Download and install

Download links will appear on the
[Releases](https://github.com/problem-xyz/aion2-map-overlay/releases) page with the first
release. There are none yet.

- **Installer (recommended).** Run the `Setup.exe` from the latest release. It installs for your
  Windows account only, needs no administrator rights, and adds Start menu and desktop shortcuts.
- **Portable.** Unzip the `Portable.zip` anywhere and run `Aion 2 - Map Overlay.exe`. Nothing is
  installed, and your routes and settings stay in the same folder.

**"Windows protected your PC".** Windows shows this for programs that are not code-signed, and
this free project is not. Click **More info**, then **Run anyway**. You only need to do this once.

**"Smart App Control blocked an app that may be unsafe".** This is a different check, on some
Windows 11 PCs, and it has no "run anyway" button: it only allows programs that are code-signed.
The only way to run the overlay there is to turn Smart App Control off: **Windows Security** >
**App & browser control** > **Smart App Control settings** > **Off**. Windows does not let you
turn it back on later without reinstalling, so decide for yourself whether that is acceptable.

## Getting started

Put the game in **borderless windowed** mode first. Overlays cannot be drawn over exclusive
fullscreen.

1. **Pick a map.** In the panel, press **New** under Routes. The route editor opens on one of
   the two maps that come with the app, Altgard and Verteron; the map selector switches them.
   The very first time, each map takes a moment to prepare.
2. **Draw a route.** Click the map to place points; they are numbered and joined with arrows.
   Type what to do at each point ("pick up the feather"). Save with **Ctrl+S**.
3. **Select the map area.** Open the map in the game, press **Select area** in the panel and drag
   a box around it.
4. **Start.** Press **Start overlay**. The route appears on the game map and follows it.

## What else it does

- **Map objects.** Each map comes with its teleports, villages and other places; click them to
  build a route, and show or hide them by category.
- **Route progress.** Points you reach are marked on arrival and disappear, so only the way ahead
  stays on screen. You can also tick points off by hand. Progress is kept per route.
- **Checklist over the game.** A small list of the next points, switched on beside Start; its
  arrows mark a point done or take it back. Clicks pass through it; unpin it to move it, or drag
  its right or bottom edge to size it.
- **Sharing.** Export a route to a file, or copy it as a short code you can paste into chat.
- **Recording videos.** The route is hidden from screen recordings by default. Tick **Visible in
  screen recordings** before you record, and use Display Capture in OBS.

## Timers

The panel's second tool, **Timers**, counts down Aion 2's recurring events (Spacetime Rift, Shugo
Festival and the sieges) and the daily and weekly resets, in your own time.

- **Your server.** Choose it under **Settings** in Timers; until you do, it is guessed from your
  clock.
- **Reminders.** Each event can sound a few minutes before it starts, and be shown or left off the
  plaque over the game. With the sound off, the plaque shows itself for a moment instead.
- **Day timeline.** A wide window with one or two days at a glance: every event on its own line.

## Updates

The app checks for updates by itself, downloads them in the background and installs them when
you close it, so a game session is never interrupted. A banner in the panel says when a new
version is ready, with **Restart now** if you do not want to wait. You can turn automatic
checks or downloads off under the gear at the top of the panel.

An update never deletes or changes the routes you made. The routes that come with the app get
the new version only if you never edited them. If you edited one, it stays as you left it, and
one you deleted does not come back.

## Uninstall

Open Windows **Settings → Apps**, find **Aion 2 - Map Overlay** and choose **Uninstall**. Your
maps and routes are kept in `%LocalAppData%\Aion2MapOverlayData`; delete that folder too if
you want them gone.
A portable copy is removed by deleting its folder.

## Is it safe?

- The app only looks at the part of the screen you selected, and draws in its own transparent
  windows. It does not read or change game memory, inject anything into the game or press keys
  for you.
- **The source is open.** Everything the app does is in this repository, and each `Setup.exe` and
  `Portable.zip` on the Releases page is built from it by GitHub Actions, in a public build log.
- Every release links a [VirusTotal](https://www.virustotal.com) report for both files at the
  end of its notes.
- There is no telemetry and no account. It sends two things, both to GitHub: the update check,
  which carries the installed version, the app's name and a random number made once per
  installation, and a request for the latest timers schedule, which carries nothing about you.
  **Fetch new schedules** in Timers' Settings turns the second one off.
- **Use it at your own risk.** Whether the game allows overlays is up to its publisher; check the
  game's Terms of Service.

## Something wrong?

Open an [issue](https://github.com/problem-xyz/aion2-map-overlay/issues) and attach the log from
`%LocalAppData%\Aion2MapOverlayData\logs` (look it over first: it contains your Windows user name).

## License

The app is free, and its source is here for anyone to read, but it is not open source. You may
install and use it as much as you like, read the code and build it for yourself, and share the
link to this page, but not upload copies elsewhere, publish changed versions or sell it without
permission; the full terms are in [LICENSE](LICENSE). The two maps and the map object sets are
adapted from the
[aion2-interactive-map](https://github.com/aion2-interactive-map/aion2-interactive-map) project
and are licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): free for
non-commercial use, with credit. Their credits and the licences of the components inside the app
are in the `THIRD-PARTY-NOTICES` folder next to `Aion 2 - Map Overlay.exe`.

Aion, Aion 2 and NCSOFT are trademarks or registered trademarks of NCSOFT Corporation. The game
and its content, including the map art and place names shown in the app, are the intellectual
property of NCSOFT Corporation. This is an unofficial fan project, not affiliated with, endorsed
or sponsored by NCSOFT; the game is named only to say which game the app works with.
