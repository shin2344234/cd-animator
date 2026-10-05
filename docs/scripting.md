# Scripting the add-on

Everything in the sidebar can run from Python, in Blender's Python console or from a command prompt with no Blender window. The [example scripts](examples.md) work this way, and so do Speeder Bike's build scripts, which make every one of its clips without a click.

## Running headless

```
blender -b --factory-startup --python my_script.py -- my arguments
```

`--factory-startup` ignores your preferences and the installed add-on, so the script loads the add-on from the repository itself:

```python
import os
import sys

import bpy

sys.path.insert(0, r"C:\path\to\CD animator")   # the repository folder, which holds cd_animator
import cd_animator
from cd_animator import actioncharts, anim, export, ingame, packs

cd_animator.register()
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
```

A script that lives in another mod's repository can find the add-on through an environment variable, falling back to a folder beside its own repository, the way Speeder Bike's scripts read `CD_ANIMATOR`.

The game is found through Steam's libraries, as in Blender. To name it, replace the lookup before the first use:

```python
packs.game_folder = lambda context=None: r"D:\SteamLibrary\steamapps\common\Crimson Desert"
```

Run this way the add-on keeps its cache in `%APPDATA%\Blender Foundation\Blender\5.2\datafiles\cd_animator\game`, a separate copy from the installed add-on's.

An operator that reports an error raises `RuntimeError` in a script, with the message the sidebar would show, so wrap a call in `try` where a refusal is expected. Operators act on the active object, so set it first with `bpy.context.view_layer.objects.active = arm`. Seat rider on mount and Retarget from armature also read which objects are selected.

## The operators

Each button is an operator, `bpy.ops.cd_animator.<name>(...)`. Arguments left out take the defaults the dialogs show.

| Operator | Arguments and defaults | Button |
|---|---|---|
| `game_skeleton` | `skeleton` | Import skeleton |
| `game_clip` | `clip`, `voice=True` | Import animation |
| `game_mesh` | `mesh`, `level=0`, `textures=True`, `variant=0`, `cloth=True`, `sway=True` | Import mesh |
| `game_character` | `character`, Kliff by default; `clip=""`, `face=""`, `level=0`, `textures=True`, `proportions=True`, `gear="AWAY"`, also `"DRAWN"` or `"NONE"`; `cloth=True`, `sway=True`, `voice=True` | Import character |
| `game_characters` | `text="CD characters"`, `gap=0.5`, `folder=""`, and `game_character`'s options | Build characters from a list |
| `game_prop` | `prop`, `state="OUT"` or `"IN"`, `socket=""`, `level`, `textures`, `cloth`, `sway` | Attach weapon or prop |
| `game_new_clip` | `clip`, `clip_name=""`, `frames=0`, `start="MOTION"` or `"HOLD"`, `stretch_events=True` | New clip from a game clip |
| `import_pab` | `filepath` | Import skeleton (.pab) |
| `import_paa` | `filepath`, or `directory` and `files` for several | Import animation (.paa) |
| `import_pac` | `filepath` and `game_mesh`'s options | Import mesh (.pac) |
| `new_clip` | `filepath` and `game_new_clip`'s options | New clip from a template |
| `export_paa` | `filepath`, `companions=True`, `bake=True`, `clip="ACTION"` or `"FACE"` | Export animation (.paa) |
| `set_length` | `frames`, `stretch_events=False` | Set clip length |
| `make_loop` | `frames=15` | Make it loop |
| `end_on_idle` | `frames=15` | End on his idle |
| `event_add`, `event_remove`, `tag_footsteps` | none | The events buttons |
| `mocap` | `motion` | Motion capture from CMU |
| `retarget` | `face_forward=True`, `start=0`, `end=0`, `speed=1.0`, `travel=False` | Retarget from armature |
| `bake_chains` | `damping=0.03`, `collide=True`, `cloth=True` | Simulate chains and cloth |
| `ik_controls` | none | Add IK controls |
| `seat_rider`, `unseat_rider` | none | Seat rider on mount, Unseat rider |
| `remove_face` | none | Remove facial clip |
| `send_to_game` | `clip="ACTION"` or `"FACE"`, `bake=True` | Send to game |
| `check_game` | none | The refresh button |
| `remove_from_game` | `name` | The X on a clip's line |
| `log_clips` | none | Turn on clip logging |
| `play_where` | `uses`, a list of `{"chart": path, "node": number, "chosen": True}` | Where it plays |
| `play_on_key` | `key`, `loop=False`, `face="NONE"` or an expression such as `"happy"`, `sound=""`, `sound_frame=0`, `prop=""`, `hand="RIGHT"` or `"LEFT"` | Play on a key |

The search fields take the same words or paths as in the sidebar. `seen_in_game` opens a window and is no use in a script; `ingame.read_clips` below reads the same log.

A move from a script, as `examples/new_move.py` makes one:

```python
bpy.ops.cd_animator.game_character(character="1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000",
                                   gear="NONE", textures=False, cloth=False, sway=False)
bpy.ops.cd_animator.game_new_clip(clip="1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00",
                                  clip_name="cd_phm_cdanim_wave_00", frames=60, start="MOTION")
# ... pose and key the arm here ...
bpy.ops.cd_animator.play_on_key(key="l")
bpy.ops.cd_animator.send_to_game(clip="ACTION")
```

## Editing keys

Blender 5 has no `action.fcurves`. An action keeps its curves in a channel bag for each of its slots, and `export._channelbag(obj, action)` returns the bag of the slot the armature plays, which is how the example scripts reach a clip's curves:

```python
from cd_animator import export

action = arm.animation_data.action
bag = export._channelbag(arm, action)
for fc in bag.fcurves:
    if fc.data_path == 'pose.bones["Bip01 Head"].rotation_quaternion':
        print(fc.array_index, [tuple(k.co) for k in fc.keyframe_points])
```

Posing a bone and calling `keyframe_insert("rotation_quaternion", frame=f)` on it works as in any Blender script. Keep keys on whole frames from 0 to the clip's last frame and rotation in quaternions, or leave `bake` on so export bakes the rest.

## Functions under the buttons

For work the buttons do not cover, such as writing a mod's files into a folder of its own, the modules have the pieces. These are the ones the example scripts use.

| Function | What it does |
|---|---|
| `packs.index()` | The game's pack index, read on first use, about 6 seconds |
| `packs.fetch_clip(idx, path)` | Copies a clip, with its LOD and metadata, from the packs into the cache and returns the clip's file. `path` is under `character/motion/` with no extension |
| `anim.import_clip(bpy.context, arm, file)` | Loads a clip file onto an armature as a new action. Returns the action and any bone hashes the armature lacks |
| `export.export_with_companions(arm, action, file, bake=True)` | Writes the clip and its `_lod.paa` and `.paa_metabin` side by side. Returns the files written and any problems |
| `ingame.folder()` | The loader's folder, refusing when the loader is not installed |
| `ingame.send(arm, action, root, bake=True)` | What Send to game does for the clip itself, into folder `root`. Returns the name, the files and any problems |
| `ingame.read_clips(ingame.bin64())` | The clips the game loaded in its current or last session, in the moments Seen in game lists, oldest first |
| `actioncharts.uses(idx, path)` | Every chart node and blend slot that plays a game clip |
| `actioncharts.new_path(action, name)` | The game path a new clip gets: its template's folder and the new name |
| `actioncharts.send(idx, root, path, plays)` | Writes the charts and blends that point the chosen nodes and slots at the new clip |
| `actioncharts.send_move(idx, root, path, key, frames, ...)` | Writes Kliff's two charts and the input map for a move on a key |
| `ik.add_controls(bpy.context, arm, action)` | What Add IK controls does |
| `actioncharts.game_bytes(idx, path)` | A chart or blend file as the game ships it, by game path |
| `formats.paac.Chart.parse(data)`, `chart.pack()` | Reads a chart into nodes, actions and string tables, and writes it back. An unchanged chart packs byte for byte |
| `actioncharts.point(chart, nodes, clip)` | Points chart nodes, or a blend's slots, at a clip, adding its path to the clip table |
| `actioncharts.pointed(chart, game)` | The nodes of a chart that play something other than the game's chart's, by clip |
| `formats.hashlittle.hashlittle(name.encode(), 0xC5EDE)` | An action's key from its name |

`root` can be any folder. The charts, blends and input map go under `root\by_path` at their game paths, the layout the loader reads, which is also what a mod needs to know to serve them itself. `examples/new_name.py` writes everything into `out\new_name` that way unless it is given `--send`.

## What the add-on stores

The add-on keeps its state in custom properties, which a script can read and set.

| Where | Property | What it holds |
|---|---|---|
| Action | `cd_source` | The clip file the action exports against |
| Action | `cd_template` | For a new clip, the game clip it was started from |
| Action | `cd_lod` | True for a LOD clip |
| Action | `cd_face` | True on a facial clip; on a move, the expression's name |
| Action | `cd_key`, `cd_loop` | A move's key, and whether it loops |
| Action | `cd_sound`, `cd_sound_frame` | A move's sound and the frame it starts on |
| Action | `cd_prop`, `cd_prop_hand` | A move's prop and hand |
| Action | `cd_plays` | The nodes and slots chosen in Where it plays, each `chart path#number` |
| Action | `cd_rec1` | The clip's transform record, which Seat rider on mount places a rider by |
| Action | `cd_meta` | Its events, `cd_meta.events`, each with `begin` and `end` in seconds, `begin_frame` and `end_frame` in frames, and `type`, and its phases |
| Action | `cd_duration`, `cd_blocks` | The clip's length in seconds, and each track's layout in its file, as JSON, with the frames whose rotations the file stores negated. Export writes against both, and Set clip length keeps them in step |
| Action | `cd_chains` | True on the action Simulate chains and cloth stores, which plays on the `CD chains` track |
| Armature | `cd_pab`, `cd_game_path` | Marks an armature from the importer, and the skeleton's game path |
| Armature | `cd_record` | The character record its gear came from |
| Armature | `cd_character`, `cd_bone_count` | The appearance Import character built it from, and its skeleton's bone count |
| Armature | `cd_seated`, `cd_seated_action` | Marks a rider Seat rider on mount placed, and the clip that placed it |
| Armature | `cd_mocap` | On an armature from Motion capture from CMU, the motion's name |
| Bone | `cd_index` | Its place in the game's skeleton. Export writes only bones that have it |
| Bone | `cd_chain` | Makes the bone swing as a chain |
| Bone | `cd_axis`, `cd_bind_q`, `cd_bind_t` | Its axis conversion between the game and Blender, and its bind rotation and position from the skeleton file |
| Bone | `cd_mass`, `cd_stiffness` | A chain link's mass, and a sway spring's stiffness |
| Mesh object | `cd_component`, `cd_item` | Its slot in the appearance, and the gear item it came from |
| Mesh object | `cd_socket`, `cd_socket_bone`, `cd_placement` | For a prop, the socket it hangs from, that socket's bone and its placement |
| Mesh object | `cd_cloth`, `cd_cloth_part`, `cd_cloth_of` | Marks the cloth split off a mesh, and links the cloth and the rest to each other |
| Mesh object | `cd_move_prop` | On a prop that Play on a key shows, the move's action |
| Action | `cd_move_face` | On the facial clip that shows a move's expression, the move's action |
| Sound strip | `cd_voice_line`, `cd_move_sound` | The voice line a lip sync strip plays, or the move whose sound the strip is |

The add-on also names a few things in the scene:

| Name | What it is |
|---|---|
| `CD face` | The NLA track that plays a facial clip over the body clip |
| `CD chains` | The NLA track that plays the stored chain, hair and cloth motion |
| `CD controls` | The bone collection of the IK controls |
| `CD IK`, `CD turn`, `CD place` | The IK constraint on a forearm or calf, and the two constraints that give a hand or foot its control's turn and keep it on the limb |
| `CD pin` | The vertex group that holds cloth to the body where the game pins it |
| `CD characters` | The text block Build characters from a list reads |

Setting `cd_key` and the move properties by hand works, but Play on a key also checks the key, finds the sound and closes the hand, so prefer the operator.
