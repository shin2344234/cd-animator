# CD Animator

A Blender add-on for Crimson Desert animations. It imports skeletons (`.pab`) as armatures and animation clips (`.paa`, full and `_lod`) as actions. It exports an action back to a `.paa`, along with the `_lod.paa` and `.paa_metabin` the game loads with every clip. Its clips play in the game. Broomy 1.0.2's hover idle and level takeoff were made with it, and so were the raised-arm idles that first tested the loader. Version 0.3.1 also reads Kliff's on-foot clips.

It needs Blender 4.4 or newer and was built on 5.2.2.

## Install

In Blender open Edit > Preferences > Get Extensions, open the menu at the top right, choose Install from Disk, and pick `dist/cd_animator-0.3.1.zip`. To rebuild the zip after changing the code:

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
4. To write a clip, select the armature and use File > Export > Crimson Desert animation (.paa), or Export animation in the sidebar. It writes the active action against the clip it was imported from. With LOD and metadata ticked, as it is by default, it also writes `<name>_lod.paa` and `<name>.paa_metabin` beside it.

The scene runs at 30 fps, the game's clip rate. Bones a clip does not animate stay on their bind pose. Keys go out on whole frames. A track whose keys are all linear is written key for key; any other track is sampled at every frame, because the game only interpolates in straight lines. Constraints and IK are not baked yet, so bake to keys first if you use them.

The LOD gets the template LOD's bone list, so a bone the shipped LOD leaves out stays out. The metadata keeps the template's events and phases, and its motion block is rebuilt from `B_MoveControl_01` only when that track changed.

Clips whose header names the skeleton import and export too. That's header flag 0x40, set on Kliff's camel, elephant and iguana clips. Kliff's bear clips and his Wyvern rider clips use a layout the add-on does not read yet.

## In the game

Not every bone you animate shows. On a mount the root bone, Bip01, shows its rotation, but its translation moves the mount itself, and while Broomy hovers in place a roll or float on Bip01 shows nothing. Motion on the bone under it, B_Body_00 on the broom, does show, and a rider on a seat bone below that moves with it. When the game restarts a clip with a short blend, the pose jumps to frame 0, so a clip that follows another should start on the pose the other ends in. NOTES.md has the evidence for each of these.

## Playing a clip in the game

The loader in `loader/` is an ASI plugin, `CDAnimator.asi`, that hands the game every file in `bin64\CDAnimator` in place of the game's file of that name. Export a clip, drop its three files in that folder and start the game. With `LogClips=1` in its ini it also logs each clip the game loads, which is how to find the file behind a motion you see. `loader/README.md` has the rest.

## Examples

All three run headless and write into `out/`:

```
blender -b --factory-startup --python examples/hover_idle.py
blender -b --factory-startup --python examples/level_takeoff.py
blender -b --factory-startup --python examples/raise_arm.py
```

`hover_idle.py` adds a 12 cm float with a small roll and pitch to the broom's idle, on B_Body_00, starting and ending on the shipped pose. `level_takeoff.py` makes a takeoff that holds the idle's first frame and keeps the climb's rise, so flight starts with no jump. Broomy 1.0.2 carries both. `raise_arm.py` turns Kliff's right arm up over his head in his two standing idles and his desert fidget, for the loader; other clips of his can be named on the command line.

## Check

```
blender -b --factory-startup --python tests/check_import.py
```

It imports both rigs and the clips in `samples/character`, all 44 broom riding clips plus Kliff's two standing idles and the three parts of his desert fidget with their LODs, then compares every bone at a set of frames and half frames with forward kinematics done in game space. It prints PASS when every bone is within 1 mm.

```
blender -b --factory-startup --python tests/check_export.py
```

It exports every clip unchanged and requires the original bytes back. Each full clip's metadata must come out as the game's byte for byte, and its LOD must carry the shipped LOD's tracks and the clip's source hash. It then exports an edited idle and requires the re-imported pose to match the edit within 3 mm. `tests/preview.py` opens Blender with the broom and Kliff seated on it for a look.

NOTES.md has how the game's data maps onto Blender and the evidence for each part.
