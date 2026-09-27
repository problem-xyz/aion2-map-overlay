# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries describe what a user of the app would notice. Internal refactors, tooling and CI
changes are left out unless they change how the app is installed, run or updated.

## [Unreleased]

### Added

- Under every section of the panel: Buy me a coffee and Donate in crypto, and links to the
  Discord server and the releases on GitHub. Donate in crypto lists the Ethereum, Bitcoin,
  Solana and TRON wallets, each with a QR code, a line on what it takes, and a button that
  copies the address.
- The points list over the game is called the checklist, and it is switched on and off from a
  slot beside Start overlay, next to Arrows. Its pin and its size moved to a Checklist card in
  Settings. Unpinned, the checklist can be sized by dragging its right or bottom edge, or its
  corner; it shows as many points as fit and says how many are left. The size slider is now
  Zoom: it scales the text and the size you dragged it to together. Where the panel is too
  narrow for Start overlay beside three slots, the slots show their icons alone.

- Routes can be put in any order: drag a tile up or down the list, or press Alt+Up or Alt+Down
  on it. The order is kept between runs.
- A new install, or a freshly unpacked portable copy, starts with three ready routes for
  Asmodians in Altgard: levels 10-17, 17-20 and 20-22 (Krao Cave). They are ordinary routes, to
  edit or delete; a deleted one does not come back.
- The map area in the settings has a Reset button that forgets the selected area. A running
  overlay stops, since it has nothing left to follow.
- The steps list keeps the last steps passed above the next one, faded and one line each, as
  many as "Steps passed" in the settings says -- the same count the map keeps behind you. The
  setting is offered in every route view now, since it always changes the list.
- The route editor has a route view of its own, behind a gear under the points and objects
  icons: the arrows' opacity, and whether a selected point fades the rest of the route away
  from itself and how many steps it keeps bright, or the whole route is drawn in full. It has
  no "steps" choice: the editor always draws every point.
- The settings are grouped by what they are about: General (language, frame rate), Route over
  the game (opacity and how much of the route is drawn), and, under Advanced, how the overlay
  moves and how the map is found. Every setting has an "i" beside its name with a fuller
  explanation of what it does and what changing it costs.
- A route can come back to a point it has already been to -- a teleport taken two or three
  times. Shift+click a point on the editor's map and the same point goes to the end of the
  route again. Points on one spot sit side by side, "3 7 12", instead of hiding each other.
- The editor's points list has a button to delete every point at once. It asks first, and one
  Ctrl+Z brings them all back.
- The points list over the game has arrows beside its pin, pinned or not: the right one marks
  the next point done, the left one takes the last point back, for a point skipped on purpose or
  ticked off by walking past it.
- Start with no map area chosen asks for one: drag a box round the game's map and the overlay
  comes up straight away. A new user no longer has to find the area button first; Esc starts
  nothing.
- The progress list shows the route's points the way the editor lists them: the number, the
  quest star or the icon of the object the point sits on -- a feather, a teleport, a seal, a
  cube -- and the label. The route card shows the next point's icon too.
- The selected section tab and every gold button -- Start, the editor's Save, the main answer in
  a dialog -- come alive, like the game's: ribbons of light drift across them, a few motes come
  and go, and a glint runs along the tab's glow lines every few seconds. The gold buttons catch
  a soft glow on hover, and their lettering is white with a thin dark outline. With
  "reduce motion" on in Windows they stay still.
- A route point can be marked as a main quest or a side quest in the editor's inspector. It
  gets a yellow or a green star beside its number in the points list and on the steps plaque,
  and turns yellow or green itself; one undo takes both back. The icon is saved with the route
  and travels in share codes; a version without it opens the route and leaves the icon out.
- Verteron's teleports, the Elyos ones, are drawn as the blue winged figure the game uses for
  them.
- The interface moves, the way the game's own menus do. The gold Start and Save buttons glow
  softly as the pointer arrives; a picked row's glow lines draw out from the middle;
  menus, the keys card, the points drawer and the inspector come in from where they are
  anchored; toasts slide in and fade out; the advanced settings fold open; the progress ring
  runs on to its new share; every button gives a little under the press; and on the steps plaque
  the next step's row glows once as the point before it is passed. It is all short, and with
  "reduce motion" on in Windows every change lands at once.
- The app has an icon of its own -- a gunmetal map pin with a gold rim on white feathered
  wings -- instead of the blank default, in the window, the taskbar and on the executable.
- The interface speaks English as well as Russian, and follows the system language by default.
  The panel, the route editor and the steps plaque all change language without a restart, and
  so do the notices already on screen and the window titles. A new language is a single JSON
  file in `locales/`.
- A language setting in Settings: System, English or Russian. Each language is offered in its
  own name, so a language you can read is one you can find.
- The editor window shows the engine's messages -- an import error, a rescaled route, "route
  saved" -- instead of swallowing them.
- The two maps come with the app: Altgard and Verteron, as the continent overviews of the
  aion2-interactive-map project (CC BY-NC 4.0, see `NOTICE`). The editor opens on the first
  one; the map selector switches between them. On the first start each is cut into tiles once,
  and a map whose image changed with an update is cut again rather than shown from the old
  tiles.
- An empty `.portable` file beside `Map Overlay.exe` now makes a copy portable, just as
  `portable.txt` does: the copy keeps its maps, routes, settings and logs in a `userdata` folder
  beside it rather than in `%LocalAppData%`.
- Each release on GitHub comes as an installer, `Aion2MapOverlay-win-Setup.exe`, which
  installs for your Windows account without administrator rights, and as a portable zip. The
  portable copy keeps its data beside it; only its launcher writes a log to
  `%LocalAppData%\velopack`. The release notes say how to get past the SmartScreen warning.
- Saving a route keeps the version it replaced as `<route>.json.bak` in the routes folder, so
  a save you regret can be undone by hand. There is one backup per route, the previous save;
  saving twice without a change does not overwrite it, and deleting the route deletes it too.
- Route files larger than 5 MB are refused on their size, without being read. An import says
  so, and a file that large in the routes folder is left out of the list with a message that
  names it. The app will not save or export a route that large either, so every route it
  writes is one it can open again; it takes thousands of characters of text on each of
  hundreds of points to get there.
- The packaged app carries the licences of the third-party software inside it -- Qt and PySide6
  (under the GNU LGPL version 3), Chromium, OpenCV, Python and the rest -- in a
  `THIRD-PARTY-NOTICES` folder next to `Map Overlay.exe`, with where to get the source of Qt and
  PySide6 and how to run the app with your own build of them.
- An installed copy keeps itself up to date. It checks GitHub Releases 10 seconds after it
  starts and every 6 hours, downloads a new version in the background and installs it when you
  close the app, so an update never interrupts a game. A notice says when a version is ready,
  and when a check or a download fails.
- A banner at the top of the panel follows an update from "available" through the download to
  "ready": Restart now (it asks first if the route editor is open), Later, Skip this version and
  Release notes, which opens the release's page on GitHub. An Updates block under Settings has
  switches for checking and downloading automatically, Check now, the version you run, and a way
  to be offered a skipped version again.
- A "Get started" checklist at the top of a new panel: draw a route, select the map area, start.
  Each step has its button and ticks itself off, and the list goes once a route and an area
  exist, with a reminder that the game has to run in borderless windowed mode.
- Altgard and Verteron come with their object sets: the teleports, villages and other places
  are in the editor's Map objects from the start, without importing a file.
- While the maps are prepared on the first start, the editor says which of them is ready.
- The packaged app carries NOTICE, the credit and licence note for the maps and object sets,
  in its `THIRD-PARTY-NOTICES` folder.
- "Reset to defaults" at the bottom of Settings puts every setting back, after asking first.
  Routes, maps, the map area, route progress and your choices about updates are kept.
- An "Advanced" section in Settings, closed by default, holds the detection and tracking
  settings, so the everyday ones -- language, opacity, frame rate -- are not lost among them.
- A map area saved on a monitor that is no longer connected is noticed at start and whenever
  monitors change: the app says so, clears the area and stops a running overlay, instead of
  capturing a rectangle that is on no screen. A steps plaque left off-screen is moved back.
- On Windows older than 10 version 2004 the app says once that it cannot hide the overlay from
  screen capture, and greys out "Visible in screen recordings" with an explanation.
- When the map has not been found for a few seconds, the panel reminds you under the Stop
  button that the game has to run in borderless windowed mode.
- The route editor shows its keys: a Shortcuts card in the corner of the map lists what a
  click, a drag, Delete, 1-8, 9, Escape, Ctrl+Z/Y and Ctrl+S do, and the Undo, Redo and Save
  buttons carry their keycaps. `?` shows and hides the card; once closed it stays closed.

### Removed

- The **Take the category colour** switch under the editor's map objects. It started off, so a
  point placed on a feather or a teleport kept the route's amber and its leg with it; now such a
  point is always white or purple, and so is the leg leading to it. The inspector still picks
  another colour.
- Adding and removing object sets in the route editor. Each map shows the set that comes with
  it and no other; there is no **Add a set** button and no remove button beside a set. A set
  you imported with an earlier version stays in its folder but is no longer shown.
- Adding and deleting maps. There is no "+" or "x" beside the map selector, no map image
  dialog, and a folder placed under `maps/` in the data directory by hand is no longer a map.
  A route that names a map other than the two is opened without one, and the editor asks you
  to choose.

### Fixed

- The checklist can be dragged while the game is in front. It used to follow the mouse only
  while the app's own panel was the active window: with the game running as administrator,
  Windows told the app the mouse button was already up.
- The play and stop icons on Start overlay and Stop sit level with the word; they were a
  little low. Stop is drawn in a dark red with a lit square, so it no longer looks disabled.
- A map area drawn with "Select area" shows up in the settings at once. It used to be saved
  but not shown until something else changed.
- Points are ticked off strictly in their order. Running past a later point no longer ticks it
  off along with the ones before it -- with one step ahead shown, by a point that was not even
  on screen. A point skipped on purpose is ticked off by hand.
- Over the game, only a stretch of the route is drawn: the next three steps in full, with their
  arrows, and the last three passed faded, without them; nothing further either way. Settings,
  "Route over the game" changes that: how many steps ahead and passed, the whole route faded
  away from the next steps, or the whole route ahead in full. In the editor, selecting a point
  shows the route the same way from there: the leg into it and the two after it. With nothing
  selected the whole route is drawn as before. A route that loops about a village is no longer a tangle.
- Where a route crosses itself, the leg walked first is drawn on top, with its dark outline
  cutting through the later one, in the editor and over the game. The later leg used to cover
  the one being walked. Of two points on one spot, the one due first is on top.
- Standing on a teleport the route comes back to a step or two later no longer ticks off that
  return visit, and the points before it, at once.
- Closing the route editor with unsaved changes waits for your answer. The question used to be
  cut short after a second: the editor closed anyway, with the question still on screen.
- Pressing a route tile in the panel no longer makes its map picture jump.
- The first switch to Progress or Settings after a launch no longer freezes the panel for a
  fraction of a second.
- A very fast zoom in the route editor, and switching back and forth between points, no longer
  brings the black staircases and the blinking back. The zoom moved the map a little every frame
  from script, and so did the flight to a picked point; every such frame redrew the tiles and
  the whole canvas, and under that load the frames reached the screen half drawn. Both now run
  as the map's own zoom animation, which the browser plays by itself. No wheel notch is lost,
  and none waits: one that comes while the map zooms sends the running animation on to the new
  target, and the map lands about a fifth of a second after the last notch. While the map zooms
  the objects and the route line step aside rather than swell with it, and fade back in drawn
  at their size; the numbered points stay and move with the map.
- In the point inspector the cross on "Same as the route" sits in the middle of its circle, and
  the chosen colour is ringed outside the swatch, where a border inside it vanished on the
  white swatch and barely showed on the pale ones.
- The steps plaque stays readable over a bright scene. Its counter was in the panel's grey and
  fell to about 2:1; the next step was told apart by light blue text, and is now marked by a
  band with a blue edge and bold white text; the opacity setting no longer thins the plaque's
  backing below 0.85; and the pin that unpins a pinned plaque is no longer dimmed. A long route
  shows the next eight rows and how many points are left, where the list used to run off the
  bottom of the window unannounced. The plaque's buttons are at least 24 px at every size, rows
  of wrapped labels stand further apart, and a cut-off route name shows in full on hover.
- The route editor's point inspector no longer looks broken at its foot: "Show on map" and
  "Delete point" wrapped onto two lines beside the smaller move buttons. The moves and "Show
  on map" now share one row and "Delete point" has its own, all one height, and the position
  reads "x 1,390 · y 600" rather than "1,390, 600 px".
- The route editor's map picker opens from anywhere on its chip and lists the maps in the
  editor's own style, the current one ticked, and it now comes before the route's name. It was
  a native list that QtWebEngine drew in system blue at the width of the map's name, and only a
  click on the name itself opened it.
- The route editor's wheel zoom goes about five times as far per notch: half a zoom level, the
  same as a press of the zoom buttons. A quick spin used to lose most of its notches, dropped
  while each step's animation played, and the map lurched; now every notch counts, and the
  point under the cursor stays under it. Quick presses of the zoom buttons add up the same way.
- A fast zoom in the route editor no longer tears the map into black staircases or blinks the
  whole window, and no longer lags. Qt put each frame on screen before Chromium had finished
  drawing it; the app now draws its windows through OpenGL instead of Direct3D 11. Setting
  `QSG_RHI_BACKEND=d3d11` goes back to Direct3D 11, and so does a machine where no OpenGL
  context can be made.
- The route editor no longer lags on long routes. Typing a point's label, dragging a point,
  moving the mouse over the map and any change sent from the panel used to redraw every row
  of the points list, the object panel and the whole map canvas; now only what changed is
  redrawn. On a 96-point route with 832 objects a keystroke went from about 48 ms to 15 ms
  of work at a 4x CPU slowdown, and a panel change from 21 ms to 5 ms.
- In the route editor, a map whose tiles address changed while it was open no longer turns
  blank: Leaflet asked for tiles at a fractional zoom level that does not exist.
- A damaged route file no longer vanishes from the list without a word. The app now says which
  file it was and moves it aside as `<name>.json.broken-<date>`, as it already did with a
  damaged settings file, so the route can still be recovered. A route file it can read but not
  use, such as one from a newer version, is left where it is and reported the same way. Each is
  mentioned once, instead of with a full error report in the log every time the panel refreshed.
- Starting the app while it is already running now brings the open window to the front. Before,
  Windows could refuse it that and only flash its taskbar button. The second launch also no
  longer writes a start-up header of its own into the log or touches your data before it sees
  the first copy.
- Starting the app twice in quick succession, as when a double-click on the shortcut is taken
  for two, no longer opens two copies that fight over the same settings, progress and map area.
  The second launch used to give up on a first copy that was still opening its window and start
  beside it. Now it waits up to 5 seconds for that copy, brings it to the front and exits; if
  the first copy closes in the meantime, the second one starts in its place.
- The notice after "Import" or "Paste code" is translated in full. It ended in the English word
  "file" or "clipboard" whatever the language, so a Russian notice finished in English; it now
  says "added from a file" or "added from the clipboard" in your own language.
- The crosshair in "What detection sees" is red, as the hint under it says. It was drawn
  blue-violet, so the hint pointed at a colour that was nowhere in the picture.
- The advice that the steps plaque can be dragged once unpinned comes only the first time you
  show the list, as the troubleshooting guide says, and not on every switch.
- Screen positions are written without a thousands separator. The map area read "from 1,280, 0"
  and the plaque "at 1,280, 0", which looks like three numbers rather than two.
- On Windows older than 10 version 2004, the overlay no longer blanks out the map it is drawn
  over. Hiding it from capture there paints it black in every screenshot, the app's own
  included, so the map could never be found; the overlay now stays visible to capture instead.
- A settings change made after moving other sliders no longer re-sends their old values. It
  was harmless until something else changed those settings, and would have undone part of a
  reset to defaults.
- Notices raised while the app starts now reach the panel: a damaged settings file, settings
  that had to be corrected, maps carried over from an older version. They were written to the
  log, but the panel was not listening yet and never showed them.
- `NaN` or `Infinity` in a hand-edited `settings.json` or `state.json` no longer stops the app
  from starting, or leaves the panel blank. Such a value is replaced by its default.
- Stopping the overlay while it is still starting stops it. The panel used to show it running
  for a moment, with a notice about the capture method, before it went idle.
- Adding a map from the editor works again. After "Map … added" the app stopped with an internal
  error, so the map was never cut into tiles and the editor stayed on "Preparing the map…" until
  the app was restarted.
- Choosing a route on another map while the overlay is running switches the overlay to that map.
  It used to stop with an internal error and keep following the old map until it was restarted.
- Damaged data from an older version no longer stops the app from starting. If moving it into
  the current layout fails -- a file held open by another program, or a file where a folder
  should be -- the app starts anyway, says which folder still holds what was not moved, and
  writes the details to the log. A version 2 route whose `route.json` gave its name as a number
  used to stop the app before any window appeared.
- A route file whose version, map size or points hold the wrong kind of value -- a version of
  `null`, say -- is reported as not a valid route. Imported, it used to fail without a word; in
  the routes folder, it stopped the panel from loading its list at all.
- A portable copy -- one with a `portable.txt` beside it -- now leaves nothing on the machine it
  ran on. It used to create `%LocalAppData%\Map Overlay\cache` on first start, a shader cache
  Qt writes on its own, so running it from a USB stick left a folder behind.
- Screen capture in a packaged build uses the fast path again. The accelerated part of the
  capture library was reached through an import the packager could not see, so it was left
  out of every build; capture then fell back to a slower route and said so only in the log.
  If the fast path still cannot start, the app now says which method it is using instead.
- Progress you ticked off by hand is no longer overwritten while the feature is switched off.
  With progress off, walking back past the start of the route still ran the arrival test from
  the first point and wrote the answer down, so 40 of 60 points could quietly become 1 -- a
  loss you only saw when you switched progress back on.
- A window that the app stops answering now says so instead of waiting forever. If a request
  to the app goes unanswered for fifteen seconds, the window shows the same error card it
  shows when there is no app behind it at all -- before, it sat on “Connecting…” for the rest
  of the session, with nothing in the log and no way to tell a slow start from a dead one.
  Importing a map or an object set is exempt: those wait on the file dialog, which is you.
- The interface can now be used without a mouse, and says what it is doing to a screen
  reader. Every icon button is named in words rather than relying on its tooltip, which
  several screen readers never read aloud. Settings that offer a choice announce which
  option is currently selected -- before, they were three buttons with no way to tell them
  apart. Sliders read out "66 px of map" or "60 fps" instead of a raw fraction, and their
  name is no longer glued to their value. The route list no longer puts buttons inside
  buttons, and the active route is announced as the current one.
- The route point list can be worked entirely from the keyboard: arrows move between
  points, Enter selects one and Delete removes it. Deleting a point this way used to be
  able to remove two at once.
- A map whose name is not written in the Latin alphabet now starts the overlay. The map
  itself imported and drew correctly; only the tracker read its reference image in a way
  that spells the path through the Windows ANSI codepage, so the file would not open and
  the app asked you to pick the map again -- advice that could never help, because the map
  was never the problem.
- Starting the overlay without a screen area or a route now explains what is missing. It used
  to show the raw code `vision.not_configured`, because no message had ever been written for
  it.
- Copying a route code now says "1 character" rather than "1 characters".
- Dragging a route point that was not already selected no longer stops after the first frame.
  Selecting it mid-drag made Leaflet rebuild the marker and abandon the drag, so the point
  barely moved and Ctrl+Z could not undo it.
- Undo now covers a drag and a caption edit. Both were recorded in a way that development
  builds threw away.
- Ctrl+S saves the route while you are typing a point's label or the route name. It used to
  do nothing until you left the field, so a label typed and "saved" that way was not.
- The dashed arrival ring is no longer drawn over the map while "Route progress" is off. With
  progress off no point ticks itself off, so the ring marked nothing -- the crosshair in "What
  detection sees" was already hidden in that state.
- Importing a route whose map you do not have, and choosing one of yours instead, now tells you
  when its points were rescaled to fit. Only a route whose own map was there at another size
  used to say so.
- Import and Paste code in the route editor now open the route they add. The editor stayed on
  the route it had open, while the panel and the overlay had already moved to the new one.
  Unsaved changes are still asked about before the editor switches.

### Changed

- The panel opens at 600 × 940 and cannot be made smaller than that, where it opened at 440 × 780
  and could shrink to 380 × 520. On a screen smaller than that it takes the whole screen.
- A new route is added at the bottom of the routes list, not wherever its name sorted.
- Each route tile shows the part of the map its route crosses, with the route drawn on it,
  instead of the same blurred middle of the whole map for every route on it. The tile no longer
  counts the points that have text.
- The pencil and bin on the route tiles are drawn solid, in the gold of the menu's icons.
- A new app icon: a gunmetal map pin with a gold rim, carried on white feathered wings, on a
  dark plate with a bronze edge. The installer puts it on the desktop and in the Start menu, and
  the taskbar shows it too.
- Route progress is always on: its switch is gone, since there was nothing to gain from turning
  it off. Marking points on arrival has a card of its own in Progress, with the arrival radius
  under its switch, from 8 to 32 map pixels in steps of one (8 to start with; a radius past 32
  from before comes down to 32); with it off, points are ticked off by hand. If you had progress
  off, points are now marked as you reach them -- switch "Mark points on arrival" off to keep
  ticking them yourself.
- The steps list is called the points list over the game, and its card comes first in Progress,
  above the list of points, where it used to be easy to miss under a long route.
- The app is free of charge under its own licence instead of the MIT License. Its source is
  public, to read and to build for yourself, at
  [aion2-map-overlay](https://github.com/problem-xyz/aion2-map-overlay), together with the
  releases and bug reports; the app takes its updates from there.
- The seals on both maps are called Sealed Dungeons, in the editor's objects list and in the
  title a point takes when it snaps to one.
- A point snapped to an Empyrean Trace is called just "Empyrean Trace", without the region's
  name after it.
- The selected point in the editor's points list lives as the current step of the steps plaque
  does: light drifts across its band and a glint runs along its edges.
- Deleting the point open in the editor's inspector opens the next one in its place, or the one
  before it when the last point goes, instead of closing the inspector.
- Questions such as "Change the map?" and "Delete route?" come up in the app's own dialog
  instead of the grey system box. The buttons name what they do -- "Change the map", "Delete
  route" -- and the cross in the corner, Esc or a click outside the dialog cancels. The cross
  is the game's own glinting close, and the steps plaque's close is drawn the same way now.
- Closing the route editor with unsaved changes offers "Save and close" beside "Close without
  saving". If the save fails, the editor stays open with the route in it.
- The steps plaque over the game is drawn like the panel's cards: the warm frame, the route's
  name over the ice rule, every step on a line of its own between hairlines with its number and
  the icon of what it is -- its quest star, or the object it sits on -- and the next step in the
  steel band of a selected row, which lives as the panel's selected tab does. Its pin and close
  are drawn as the panel's menu tiles draw their icons, in parchment gold. Its S, M and L are a
  slider now, "Overlay window size" in the panel, from 50% to 150%: 50% is the size the plaque
  used to have, and 100%, the default, is a third larger.
- The editor shows every kind of map object when a map is opened, the large categories
  included; any of them is still one click away from being hidden.
- The main window has three sections where it had six. Routes holds the button into the editor
  (E still opens it); Progress holds the route's progress and the steps plaque; Settings holds
  the map area and what detection sees, the general and advanced settings, and updates. Each
  group is a framed card, and the switches, check boxes and sliders are drawn as the game draws
  them: a brush-stroke tick, a teal slider with a diamond knob. The engine's status sits at the
  foot of the route card while the overlay runs, and the explanations are shorter.
- The editor's map stays sharp when you zoom in close: both maps now come with an image twice
  as detailed, 8192 x 8192, that the editor draws from. Routes, objects and matching over the
  game are unchanged. The first start after the update prepares the maps again, which takes a
  few seconds, and the editor shows them once that is done.
- Each leg of the route, over the game and in the editor, takes the colour of the point it leads
  to: running to a side quest the line and its arrow are green, to the end of the route teal.
  They were all in the route's colour. The arrow in the middle of each leg is an open chevron,
  outlined like the line, where it was a small filled triangle. A point placed on an object
  takes that object's colour: teleports purple (the Elyos ones too), hidden cubes red, Empyrean
  Traces white, seals blue.
- On the editor's map the Empyrean Traces, the teleports, the seals and the hidden cubes have
  icons of their own, after the game's: a feather, a winged crest, a question mark and a coral
  cube with a spoked wheel on each face, in the objects list too, beside a route point that sits
  on such an object and on the inspector's "On object" line. Those categories take the palette
  colour nearest their icon -- white, purple, amber, red -- which a point placed on one of them
  inherits; the Collectibles and Locations groups lose a dot nothing on the map wore. The
  villages, occupation points and battlefields are left out of the editor: places, not stops on
  a route.
- In the point inspector the object a point sits on ("On object: Teleports") comes right under
  its label, and the distance from the previous point is gone.
- The point inspector's heading is just "Point 31 of 96": the line under it, "between 30 and
  32", only said the same thing again.
- A point picked in the editor's points list, or "Show on map" in its inspector, flies the map
  in to it: to the map's own resolution, or no further out than you already are, and centred in
  the part of the map the panels leave free. It used to pan only when the point was out of
  sight. A click in the list also puts the cursor in the point's label, ready to type; Enter
  keeps the focus in the list, and F2 still goes to the label.
- The frames round the panels are a muted mix of gold, brown and grey, and a little
  see-through, where they read as plain gold; the line under a panel's title is ice blue. The
  editor's text fields show their focus with their own border rather than a second ring
  inside it, and the route's name has a wider field, without the unsaved-changes dot beside
  it: Save already turns gold and reads "Save" when there is something to save. Save itself is
  wider, and the same width either way, so the bar no longer shifts when it changes. Everything
  in the editor's top bar is one height, and "Find a point" clears with a button of the
  editor's own instead of the browser's.
- The route editor gives the map the whole window. A toolbar runs along the top: the map, the
  route's name (edited in place), Undo, Redo, a Share menu (copy code, paste code, export,
  import) and Save. The points and the map's objects share a drawer on the left, opened from
  a rail of icons, and a point you pick opens an inspector on the right with its label in a
  field of its own, its colour, the object it sits on, where it is and how far from the one
  before. Points can be found by label, dragged into another order by their grip, or moved
  with Alt+Up/Down; F2 edits the selected point's label. Map objects are shown and hidden with
  an eye, as in the game. A strip at the foot of the map shows the main keys, and zoom buttons
  include one that frames the whole route, clear of the panels.
- The control panel is laid out like the game's own menu. On top, the active route's card:
  a progress ring, the route's name and map, and the point that comes next. Under it the gold
  Start button, two toggle chips for the arrows and for screen recordings, and a one-line
  status. Then the sections as tiles with a key each (R routes, P progress, L steps list,
  A map area, S settings, E opens the editor), so no section is more than one press away
  instead of at the bottom of one long column. Routes are picture tiles, the active one
  framed in gold, with New route as the last tile.
- The live colour (map found, next point, a switch that is on) is a pale ice blue instead
  of cyan, which stood out against the rest.
- Icons instead of font glyphs: the pencil, cross and tick used to render in whatever face
  Windows chose, at a weight that matched nothing beside them. Import, Paste code, New, the
  routes folder, Start and Stop, and the editor's Undo, Redo, Copy code, Paste code, Export and
  Import now carry one drawn icon set, and deleting a route shows a bin rather than a cross.
- The panel's main row wraps instead of running off the side: in Russian the Start button
  and its two checkboxes did not fit on one line.
- A new look taken from the Aion 2 client itself: near-black slate panels with a thin warm
  frame, steel blue for what is selected, cyan for what is live, and gold for the one main
  action (Start overlay, Save). Corners are squarer, keycaps look like the game's, and every
  text colour keeps at least 4.5:1 against what it sits on. Warnings now show in orange rather
  than in the information colour.
- The app is now called **Aion 2 - Map Overlay**: in window titles, on the exe
  (`Aion 2 - Map Overlay.exe`), in the installer, its shortcuts and Windows' list of apps. It
  installs into `%LocalAppData%\Aion2MapOverlay` and keeps your data in `%LocalAppData%\Aion2MapOverlayData`.
- The route editor's points list takes the free height of the sidebar instead of about three
  rows, and the map objects fold away under their heading. Picking a point on the map scrolls
  its row into view, and the selected row is marked with a blue bar rather than a barely
  different shade. Hovering a point on the map shows its label.
- Placeholder text in the editor is readable (4.5:1 instead of 2.5:1), and the colour swatches
  are larger and further apart.
- `settings.json` accepts the same ranges the panel's sliders offer, no wider: opacity from 10%,
  frame rate cap from 30 fps, minimum matches 8–60, smoothing up to 90%, refine interval
  0.1–2 s, arrival radius 0.002–0.03. A hand-edited value outside them is pulled to the nearest
  end once, with a notice that names it.
- A settings choice (Quality, Transform, and the like) is now one stop when tabbing, and
  the arrow keys move between its options. Tab used to stop on every option in turn, which
  made crossing the settings block a long walk.
- Route point colours are now named. Hovering a swatch in the editor palette shows the colour's
  name instead of its hex code, so a screen reader announces something useful too.
- The UI is no longer shipped pre-built. Run `cd ui && npm ci && npm run build` once before the
  first start; the Python environment is now installed with `uv sync` instead of
  `pip install -r requirements.txt`.
- The two ready-made object sets in `assets/object-sets/`, Verteron and Altgard, now say where
  they come from and what you may do with them. They are adapted from the community
  aion2-interactive-map data and are licensed CC BY-NC 4.0, not MIT like the code: free to use,
  share and adapt with credit, but not for commercial use. `NOTICE` has the attribution and the
  list of changes.
- The Altgard map is now the 4096 x 4096 continent image rather than an 8192 x 8192
  screenshot. A route drawn on the old image is rescaled onto the new one when it is opened,
  and the app says so once.
- Routes from version 2 (a folder holding a screenshot and a PNG with arrows on it) are moved
  to `legacy_routes/` whole, screenshot included, instead of the screenshot becoming a map.
