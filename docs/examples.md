# Example scripts

The scripts in `examples` make real clips with the add-on, from a command prompt with no Blender window. Each is also a worked example of driving the add-on from Python. Run them from the repository folder:

```
blender -b --factory-startup --python examples/<script>.py -- [options]
```

Everything after `--` goes to the script. Each writes into a folder under `out/` unless you name another, except `mocap_move.py`, which always writes into `out/mocap`. The ones that take `--send` write straight into the loader's folder instead, as Send to game does, and show from the game's next start.

The Broomy scripts and `raise_arm.py` read clips unpacked into `samples/character`, which `paz_unpack.py` makes as [Skeletons, clips and meshes](importing.md#files-on-disk) shows. Git leaves that folder out, since it is the game's own data. The other scripts read the game's packs, so the game has to be installed for them.

## Broomy's clips

### hover_idle.py

```
blender -b --factory-startup --python examples/hover_idle.py -- [out folder]
```

Makes Broomy's hover idle from the broom's shipped idle. It adds a slow float to B_Body_00, with a side-to-side roll about the seat and a small pitch, so the broom drifts in a slow figure of eight, and every part is zero on frame 0 so flight starts with no jump. The root bone is left alone, because the game throws away a hovering mount's root motion. It writes the broom's clip under the shipped idle's name, with its LOD and metadata, and `hover_idle.blend` to look at.

### level_takeoff.py

```
blender -b --factory-startup --python examples/level_takeoff.py -- [out folder]
```

Makes a level takeoff from the broom's 75 degree climb. Every bone holds the idle's frame 0 for the climb's 60 frames, while Bip01 keeps the climb's rise and drift, so flight starts from the pose the takeoff ends in. It writes `cd_rd_broom_basic_00_00_nor_std_takeoff_00`, a name no shipped file has.

### push_off.py

```
blender -b --factory-startup --python examples/push_off.py -- [out folder]
```

Makes Broomy's takeoff with Kliff pushing off the ground, two clips timed together. The broom dips under him first, so his feet can reach the ground, then rises. His clip uses IK legs that export bakes, and the script moves the IK targets until the balls of his feet sit just above the ground on the contact frames, printing each foot's clearance. It writes the broom's takeoff and Kliff's `cd_phm_rd_broom_basic_00_00_nor_std_takeoff_00`.

## Kliff and the Wyvern

### raise_arm.py

```
blender -b --factory-startup --python examples/raise_arm.py -- [out folder] [clip ...]
```

The loader's first test. Turns Kliff's right upper arm 150 degrees out and up on top of whatever each clip does, so his hand rises from about 1 m to about 2 m while the forearm and hand keep their own motion. It does his two standing idles and his desert fidget, or any of his clips named after the out folder.

### bend_wing.py

```
blender -b --factory-startup --python examples/bend_wing.py -- [out folder]
```

Raises the Wyvern's left wing 60 degrees in its ground, hover and air idles, while the right wing keeps the shipped pose and the rest of the left wing keeps its own motion. Put the files in the loader's folder and summon the Wyvern.

### open_mouth.py

```
blender -b --factory-startup --python examples/open_mouth.py -- [--send] [out folder]
```

Holds Kliff's mouth open in his two standing wait faces, the facial clips `f_cd_phm_act_wait_00_0001_kliff` and `_0002_kliff`. It finds the frame of one of his spoken lines where his lower teeth drop furthest, takes every face bone's pose there, doubles it and adds it on top of each wait face, so the teeth, tongue, lips and chin open together. A facial clip example from start to finish.

## New names and moves

### new_name.py

```
blender -b --factory-startup --python examples/new_name.py -- [--send] [out folder]
```

Gives Kliff a standing idle and a run under new names, `cd_phm_cdanim_raised_idle_00` and `cd_phm_cdanim_raised_run_00`, both with his arms raised. The idle plays because node 0 of `basic_upper.paac` and of `basic_lower.paac` are pointed at it, and the run because slot 0 of the blends `basic_move_lv3` and `basic_move_lv3_new` is. His own idle and run stay as the game ships them. It also renders a front view of each clip's frame 0. This is [Where it plays](in-the-game.md#new-clip-names) done from a script.

### new_move.py

```
blender -b --factory-startup --python examples/new_move.py -- [--send] [out folder]
```

Makes `cd_phm_cdanim_wave_00`, two seconds of Kliff waving with his right hand, palm forward, and puts it on L the way [Play on a key](moves.md) does: a move in both of his body charts and the key in the input map.

### mocap_move.py

```
blender -b --factory-startup --python examples/mocap_move.py -- [file.bvh] [options]
```

Puts a motion capture file on a key, doing by itself what the panel does by hand: a new clip from Kliff's standing idle, the BVH imported at 30 frames a second, Retarget from armature with Face forward, and Play on a key. With no file it takes `out/mocap/141_16.bvh`, CMU's motion 141_16, "Wave Hello", which it expects you to have downloaded from github.com/una-dinosauria/cmu-mocap, where it is `data/141/141_16.bvh`.

| Option | What it does |
|---|---|
| `--key=7` | The key, 7 by default |
| `--loop` | Loops until he moves, as an emote |
| `--name=...` | The new clip's name |
| `--start=`, `--end=` | Part of the recording, in its frames at 30 a second, as Retarget's Start and End |
| `--speed=1` | Retarget's Speed |
| `--smooth=frames` | Runs Make it loop over that many frames |
| `--travel` | Retarget's Travel, so he goes as far as the actor did |
| `--idle=frames` | Runs End on his idle over that many frames |
| `--face=happy` | Starts one of his expressions with the move |
| `--sound=...`, `--sound_frame=0` | Plays one of the game's sounds on a frame |
| `--prop=...`, `--hand=RIGHT` | Puts a prefab in his right or left hand |
| `--send` | Writes into the loader's folder instead of `out/mocap` |

[Motion capture and other rigs](mocap.md#after-a-retarget) has the commands that made his Charleston and moonwalk.

## Opening a preview

`tests/preview.py` is not an example, but it is a quick way to look at riding clips. It opens Blender with the broom and Kliff seated on it, playing a matching pair of clips.

```
blender --python tests/preview.py -- [clip suffix]
```
