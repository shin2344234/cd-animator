# CD Animator documentation

CD Animator makes and edits Crimson Desert animations in Blender and puts them in the game. It comes in two parts that work together.

The add-on runs inside Blender 4.4 or newer. It reads skeletons, clips, meshes, textures, sounds and the game's action charts straight from the game's packs, builds characters with their gear, and writes clips the game can play. These pages describe version 0.41.0.

The loader is `CDAnimator.asi`, a plugin the game loads through Ultimate ASI Loader like any other ASI mod. Every time the game starts, it hands the game each file in `bin64\CDAnimator` in place of the game's own file of that name, and it can log each clip the game loads. These pages describe version 0.3.0, made for Crimson Desert 2.03.02, exe 1.0.0.2976.

The add-on writes into the loader's folder and reads the loader's log. A clip goes from Blender into the game with one button, and a clip you just saw in the game comes back into Blender with one click.

## Your first clip in the game

1. Install both parts, as [Installing](install.md) describes.
2. In Blender, hover over the 3D viewport, press N and open the CD Animator tab.
3. Press Import character. Leave Character on Kliff, type `nor std idle` in Clip, click `cd_phm_basic_00_00_nor_std_idle_00` at the top of the list under it, and press OK.
4. Change the pose. [Posing with IK controls](ik-controls.md) is the quickest way to move a hand or a foot.
5. Press Send to game, under In the game.
6. Start the game, load a save and let Kliff stand still. Most places give him this idle, so he plays your edit. A few, such as the desert, have idles of their own.
7. Back in Blender, press the refresh button beside Send to game. The clip's line now says when the game played it.

## Pages

| Page | What it covers |
|---|---|
| [Installing](install.md) | Installing and updating the add-on and the loader, the game folder setting, the cache, building both from source |
| [The CD Animator tab](sidebar.md) | Every button in the sidebar and the File menus, top to bottom, with a link to where each is explained |
| [How the game plays animation](concepts.md) | Clips and their three files, the bones that do special jobs, action charts, blends, and a glossary |
| [Skeletons, clips and meshes](importing.md) | The search fields, importing from the game's packs and from files on disk, mesh options |
| [Characters, gear and props](characters.md) | Import character, Build characters from a list, Attach weapon or prop |
| [Chains, cloth and hair](physics.md) | What moves on its own after an import, and Simulate chains and cloth |
| [Faces and voice lines](faces.md) | Facial clips over body clips, lip sync with its voice, Remove facial clip |
| [Making and editing clips](making-clips.md) | New clips, length, loops, ending on the idle, events, footsteps, riders on mounts |
| [Posing with IK controls](ik-controls.md) | Hand, foot, elbow and knee controls, and how they reach the game |
| [Motion capture and other rigs](mocap.md) | The CMU database and Retarget from armature |
| [Exporting clips](exporting.md) | Export animation and what it writes |
| [Sending clips to the game](in-the-game.md) | Send to game, the In the game list, Seen in game, new clip names |
| [Moves on keys](moves.md) | Play on a key with its expression, sound and prop |
| [The CD Animator Loader](loader.md) | The plugin's folder, settings, log and limits |
| [Using a clip in another mod](mods.md) | Shipping clips, charts and blends inside a mod of your own, as Broomy and Speeder Bike do |
| [Scripting the add-on](scripting.md) | Running the add-on from Python, every operator's arguments, and what it stores |
| [Example scripts](examples.md) | The scripts in `examples` and what each makes |
| [Checks](checks.md) | The test scripts in `tests` and how to run them |
| [Versions](versions.md) | What each release of the add-on and the loader added |
| [When something does not work](troubleshooting.md) | Greyed-out buttons, error messages and clips that do not show in game |

`NOTES.md` at the top of the repository holds the evidence behind the add-on: the file formats, how the game's data maps onto Blender, and what each in-game test showed. These pages say how to use things and link to it where the reason matters.

## Credits

The action chart reader and the blend reader and writer are the ones Broomy's research wrote from the game's own loaders. The mesh vertex layout follows CrimsonForge, github.com/hzeemr/crimsonforge, under the MIT licence. The voice decoder ports the part of ww2ogg, github.com/hcs64/ww2ogg, that the game's voice files need, under ww2ogg's BSD 3-clause licence, which `cd_animator/formats/wwise.py` reproduces in full. Motion capture from CMU uses the motion list of B. Hahne's BVH release of the CMU Graphics Lab Motion Capture Database. Its data comes from mocap.cs.cmu.edu, and the database was created with funding from NSF EIA-0196217.
