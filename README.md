# CD Animator

A Blender add-on for Crimson Desert animations. It imports skeletons (`.pab`) as armatures and animation clips (`.paa`, full and `_lod`) as actions. It exports an action back to a `.paa`, along with the `_lod.paa` and `.paa_metabin` the game loads with every clip. Its clips play in the game. Broomy 1.0.2's hover idle and level takeoff were made with it, and so were the raised-arm idles that first tested the loader. Version 0.4.0 starts new clips from shipped ones, at any length, and edits a clip's events. Version 0.5.0 bakes constraints and IK on export.

It needs Blender 4.4 or newer and was built on 5.2.2.

## Install

In Blender open Edit > Preferences > Get Extensions, open the menu at the top right, choose Install from Disk, and pick `dist/cd_animator-0.5.0.zip`. To rebuild the zip after changing the code:

```
blender --command extension build --source-dir cd_animator --output-dir dist
```

## Use

The add-on reads files already unpacked from the game. Broomy's samples were taken with `master looter/tools/crimson-desert-unpacker/python/paz_unpack.py`, the clips from pack group 0009 and their `.paa_metabin` files from group 0010, for example:

```
py -3 paz_unpack.py "D:/SteamLibrary/steamapps/common/Crimson Desert/0009/0.pamt" --paz-dir "D:/SteamLibrary/steamapps/common/Crimson Desert/0009" -o samples --filter "*cd_phm_rd_broom_basic_*"
```

1. File > Import > Crimson Desert skeleton (.pab). Kliff is `phm_01.pab`.
2. With that armature selected, File > Import > Crimson Desert animation (.paa). Several clips can be picked at once. Each becomes an action, and the last one is shown.
3. For a rider and a mount, import both, select the mount, then shift-click the rider and press Seat rider on mount in the CD Animator tab of the sidebar, which N opens. The rider then follows each clip's offset from the mount, including when you switch actions.
4. To make a new clip, select the armature and press New clip from a template in the sidebar, then pick a shipped clip of the same character. The new clip gets a name and a length in frames; 0 keeps the template's length. It starts either with the template's motion, cut or held at the new end, or with every bone holding the template's first frame. Stretch events scales the template's events and phases to the new length.
5. The sidebar shows the active clip's length, with a button to change it, and its events. An event is a begin and an end in frames and a type from 0 to 7. Add puts one on the current frame. What each type means in the game is not known yet, so copy the types of a shipped clip that does something similar.
6. To write a clip, select the armature and use File > Export > Crimson Desert animation (.paa), or Export animation in the sidebar. It writes the active action against the clip it was imported from. With LOD and metadata ticked, as it is by default, it also writes `<name>_lod.paa` and `<name>.paa_metabin` beside it.

The scene runs at 30 fps, the game's clip rate. Bones a clip does not animate stay on their bind pose. Keys go out on whole frames. A track whose keys are all linear is written key for key; any other track is sampled at every frame, because the game only interpolates in straight lines. With Bake constraints and IK ticked, as it is by default, a bone moved by a constraint, an IK chain, a driver or Euler rotation is written as Blender shows it, sampled every frame, and the export lists the bones it baked. Keys that only repeat the keys on both sides are left out. Baking plays the action on its own, with the NLA off, so an NLA strip mixed in the viewport does not reach the file. Bone scale has no place in a clip and is dropped.

The LOD gets the template LOD's bone list, so a bone the shipped LOD leaves out stays out. The metadata gets the action's events, sorted by begin as the game's are, and the template's phases, and its motion block is rebuilt from `B_MoveControl_01` only when that track changed.

Clips whose header names the skeleton import and export too. That's header flag 0x40, set on Kliff's camel, elephant and iguana clips. Kliff's bear clips and his Wyvern rider clips use a layout the add-on does not read yet.

## In the game

Not every bone you animate shows. On a mount the root bone, Bip01, shows its rotation, but its translation moves the mount itself, and while Broomy hovers in place a roll or float on Bip01 shows nothing. Motion on the bone under it, B_Body_00 on the broom, does show, and a rider on a seat bone below that moves with it. When the game restarts a clip with a short blend, the pose jumps to frame 0, so a clip that follows another should start on the pose the other ends in. NOTES.md has the evidence for each of these.

## Playing a clip in the game

The loader in `loader/` is an ASI plugin, `CDAnimator.asi`, that hands the game every file in `bin64\CDAnimator` in place of the game's file of that name. Export a clip, drop its three files in that folder and start the game. With `LogClips=1` in its ini it also logs each clip the game loads, which is how to find the file behind a motion you see. `loader/README.md` has the rest.

## Examples

All four run headless and write into `out/`:

```
blender -b --factory-startup --python examples/hover_idle.py
blender -b --factory-startup --python examples/level_takeoff.py
blender -b --factory-startup --python examples/raise_arm.py
blender -b --factory-startup --python examples/push_off.py
```

`hover_idle.py` adds a 12 cm float with a small roll and pitch to the broom's idle, on B_Body_00, starting and ending on the shipped pose. `level_takeoff.py` makes a takeoff that holds the idle's first frame and keeps the climb's rise, so flight starts with no jump. Broomy 1.0.2 carries both. `raise_arm.py` turns Kliff's right arm up over his head in his two standing idles and his desert fidget, for the loader; other clips of his can be named on the command line. `push_off.py` is Kliff's kick as Broomy takes off, a new clip holding his broom idle's first frame with IK legs that export bakes. It played in game on 2 October through the Broomy test build, which points Kliff's takeoff at a spare action of his whose clip it replaces.

## Check

```
blender -b --factory-startup --python tests/check_import.py
```

It imports both rigs and the clips in `samples/character`, all 44 broom riding clips plus Kliff's two standing idles and the three parts of his desert fidget with their LODs, then compares every bone at a set of frames and half frames with forward kinematics done in game space. It prints PASS when every bone is within 1 mm.

```
blender -b --factory-startup --python tests/check_export.py
```

It exports every clip unchanged and requires the original bytes back. Each full clip's metadata must come out as the game's byte for byte, and its LOD must carry the shipped LOD's tracks and the clip's source hash. It then exports an edited idle and requires the re-imported pose to match the edit within 3 mm. Each metadata file is written from the events stored on the action, so this also checks that importing and exporting them changes nothing.

```
blender -b --factory-startup --python tests/check_new_clip.py
```

It cuts the broom dismount from 70 frames to 35 and requires the clip, its LOD and its metadata all to say 35, no key past the end, and every event and phase at half its time. It also checks that a clip holding the standing idle's first frame poses every bone the same on its last frame, that an event added in Blender reaches the metadata in order, and that lengthening an imported clip keeps all its keys.

```
blender -b --factory-startup --python tests/check_bake.py
```

It gives Kliff's standing idle an IK arm reaching for a moving empty, a head copying an animated empty's rotation, a spine keyed in Euler angles and a driver on the left clavicle. It exports with baking and imports the clip onto a second Kliff with none of that. Every bone must match within 3 mm. An export without baking must miss by more than 10 cm, so a bake that changes nothing fails.

`tests/preview.py` opens Blender with the broom and Kliff seated on it for a look.

NOTES.md has how the game's data maps onto Blender and the evidence for each part.
