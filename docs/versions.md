# Versions

Every release of the add-on and the loader, oldest first, with the date of its commit. The repository's git log has the full notes for each, including what was tested in game.

## The add-on

| Version | Date | What it added |
|---|---|---|
| 0.1.0 | 2 October 2026 | Imports the game's skeletons and clips into Blender |
| 0.2.0 | 2 October | Exports clips back to `.paa` |
| 0.3.0 | 2 October | Writes each clip's LOD and metadata with it. The first clips played in game |
| 0.3.1 | 2 October | The checks cover Kliff's clips on foot, and `examples/raise_arm.py` writes the clips that first tested the loader |
| 0.4.0 | 2 October | New clips from templates, clip length, event editing |
| 0.5.0 | 2 October | Bakes constraints, IK, drivers and Euler rotation on export |
| 0.6.0 | 3 October | Reads skeletons and clips straight from the game's packs |
| 0.7.0 | 3 October | Reads every skeleton and clip layout in the game |
| 0.8.0 | 3 October | Shows the game's meshes on the armature |
| 0.9.0 | 3 October | Textures on imported meshes |
| 0.10.0 | 3 October | Imports a whole character from its appearance file |
| 0.11.0 | 3 October | Characters get their own body and face proportions |
| 0.12.0 | 3 October | Builds characters from a list, each playing a clip |
| 0.13.0 | 3 October | Weapons and props at the game's sockets |
| 0.14.0 | 3 October | Characters come with the gear their records give them |
| 0.15.0 | 3 October | Physics chains hang and swing |
| 0.16.0 | 3 October | Cloth hangs and flows, held where the game holds it |
| 0.17.0 | 3 October | Hair and beards sway |
| 0.18.0 | 3 October | Facial clips play over body clips |
| 0.19.0 | 3 October | Lip sync clips play their voice lines |
| 0.20.0 | 3 October | Send to game |
| 0.21.0 | 3 October | Seen in game lists the clips the game just played |
| 0.22.0 | 3 October | New clips play under their own names, through the action charts |
| 0.23.0 | 3 October | New clips play from blends too. Needs loader 0.2.0 |
| 0.24.0 | 3 October | Event types named, Tag footsteps, Retarget from armature |
| 0.25.0 | 4 October | Play on a key |
| 0.26.0 | 4 October | Motion capture onto Kliff, on a key |
| 0.27.0 | 4 October | Looping emotes |
| 0.27.1 | 4 October | Retargeted heads look ahead. Only the arms and legs take the source's rest pose; the trunk keeps Kliff's |
| 0.28.0 | 4 October | Start, End and Speed for retargeting, and Make it loop |
| 0.29.0 | 4 October | Moves that travel |
| 0.30.0 | 4 October | End on his idle |
| 0.31.0 | 4 October | A looping move's key stops it |
| 0.32.0 | 4 October | Motion capture from CMU |
| 0.33.0 | 4 October | Relaxed hands. Retargeted fingers hold the template's first frame instead of the bind pose |
| 0.34.0 | 4 October | A looping move's key stops it in the lower chart only, which keeps the two layers in step |
| 0.35.0 | 4 October | An expression with a move |
| 0.36.0 | 4 October | A sound with a move |
| 0.37.0 | 4 October | A prop held in his hand |
| 0.38.0 | 4 October | Blender shows a move's prop and expression |
| 0.39.0 | 4 October | Blender plays a move's sound |
| 0.40.0 | 5 October | Add IK controls. Export counts an IK chain with Use Tail off from the bone's parent, as Blender does |
| 0.40.1 | 5 October | A clip search lists the skeleton's own folder before its subfolders, so `nor std idle` finds Kliff's standing idle |
| 0.40.2 | 5 October | Searches list the closest matches first, ranked as Blender's search box ranks them |
| 0.41.0 | 5 October | The Clip fields show the add-on's own list of the closest clips under the field, the basic set first among equal matches |
| 0.41.1 | 5 October | The Adjust Last Operation panel shows the clip without the list, since typing there ran the import again at every letter |
| 0.41.2 | 5 October | Runs on Blender 4.4 and 4.5. Importing a clip, building a character and hanging chains used two calls that only Blender 5.0 has. The game's deepest clips and meshes, whose cache paths passed Windows' 259 letters, cache in a shorter folder |
| 0.41.3 | 5 October | The Adjust Last Operation panel after Import animation, Import character or New clip shows the clip and the rest of the options again; since 0.41.1 it stopped after the first row |

## The loader

| Version | Date | What it added |
|---|---|---|
| 0.1.0 | 2 October 2026 | Serves files from the `CDAnimator` folder by name, and `LogClips`. On 3 October, still 0.1.0, it learned to serve files no pack has through stand-ins |
| 0.2.0 | 3 October | Serves files under `by_path` at their game path only |
| 0.3.0 | 3 October | `LogStates` and `WatchActions` |

The add-on's Send to game needs loader 0.2.0 or newer for anything that writes charts or blends.
