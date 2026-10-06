# Object sets

Ready-made sets of points of interest for two Aion 2 maps: teleports, villages, sealed dungeons,
battlefields, occupation points, Empyrean Traces, hidden cubes and gathering points. The route
editor draws them on top of the map, so that a click on an object snaps the new route point to
its coordinates and copies its title; the overlay draws the cubes and the gathering points over
the game.

These files ship with the app and are the only object sets it knows: each map has its own set
and nothing else. There is no importing or removing a set; a set a user imported into
`maps/<map-id>/objects/` with an older version stays on disk but is no longer read.

| File            | Map      | Nodes | Upstream file                        |
| --------------- | -------- | ----- | ------------------------------------ |
| `verteron.json` | Verteron | 3574  | `public/data/markers/World_L_A.yaml` |
| `altgard.json`  | Altgard  | 4787  | `public/data/markers/World_D_A.yaml` |

The gathering points -- 2733 on Verteron, 2692 on Altgard -- are not in the upstream repository.
They come from the marker data the project's site serves, and `scripts/import_gathering.py`
fetches them and writes them into both files as a `gathering` category with a child category
`gathering-<resource>` per resource. Run it again to bring them up to date; `--check` says
whether they are. A resource is taken only if `assets/marks/resources.json` has its drawing.

The hidden cubes on Altgard, 1371 of them, are every spot a cube can appear at, from a list of
the game's cube groups in world coordinates rather than from upstream.
`scripts/import_cubes.py <file> --map altgard` puts them into the set, and marks a spot
`"level": "up"` or `"down"` where it stands more than 20 units above or below the ground about
it, which the overlay and the editor show as an arrow beside the cube. The world lies on the
8192 x 8192 map layer centred, 8160 units to its side: `px = 4096 + x * 8192 / 8160`, and the
same for `z`.

## Source and licence

Both sets are adapted from the marker data of
[aion2-interactive-map](https://github.com/aion2-interactive-map/aion2-interactive-map), a
community map of Aion 2 by tc-imba. That project licenses its data under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), and the adapted files here are
shared under the same licence. **They are not covered by this repository's MIT licence.**

In short, you may use, share and adapt them for non-commercial purposes, as long as you credit
the upstream project, link the licence and say what you changed. Commercial use needs the
upstream author's permission. The upstream copyright notice is in its
[README](https://github.com/aion2-interactive-map/aion2-interactive-map/blob/master/README.md)
and the terms are in its
[LICENSE](https://github.com/aion2-interactive-map/aion2-interactive-map/blob/master/LICENSE).

[`NOTICE`](../../NOTICE) at the repository root lists what was changed on the way here: the
conversion from YAML, the coordinate conversion, and the fields that were renamed, dropped or
added.
Anyone who passes these files on, or a set derived from them, has to carry that credit and the
licence notice along with them.

## Format

The two files here are complete, working examples of the object-set format. Two things worth
knowing, in case a set was built against an older description: a node
whose `categoryId` is not in `categories` is **dropped**, not drawn without a colour, and
`categories[].visible` is **ignored** on import (the editor computes what starts visible from
how many points a category has).

Files may carry extra keys from the tool that produced them, such as `backgroundImage` or a
per-node `id`. The app ignores anything it does not know.

To use a set from somewhere else, convert it to that format and import it the same way. The
app checks an imported set and says what is wrong with it.
