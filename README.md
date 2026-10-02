# CD Animator

A Blender add-on for Crimson Desert animations. Version 0.1.0 imports skeletons (`.pab`) as armatures and animation clips (`.paa`, full and `_lod`) as actions. Export back to the game is the next step and is not in yet.

It needs Blender 4.4 or newer and was built on 5.2.2.

## Install

In Blender open Edit > Preferences > Get Extensions, open the menu at the top right, choose Install from Disk, and pick `dist/cd_animator-0.1.0.zip`. To rebuild the zip after changing the code:

```
blender --command extension build --source-dir cd_animator --output-dir dist
```

## Use

The add-on reads files already unpacked from the game. Broomy's samples were taken with `master looter/tools/crimson-desert-unpacker/python/paz_unpack.py` from pack group 0009, for example:

```
py -3 paz_unpack.py "D:/SteamLibrary/steamapps/common/Crimson Desert/0009/0.pamt" --paz-dir "D:/SteamLibrary/steamapps/common/Crimson Desert/0009" -o samples --filter "*cd_phm_rd_broom_basic_*"
```

1. File > Import > Crimson Desert skeleton (.pab). Kliff is `phm_01.pab`.
2. With that armature selected, File > Import > Crimson Desert animation (.paa). Several clips can be picked at once. Each becomes an action, and the last one is shown.
3. For a rider and a mount, import both, select the mount, then shift-click the rider and press Seat rider on mount in the CD Animator tab of the sidebar (N). The rider then follows each clip's offset from the mount, including when you switch actions.

The scene runs at 30 fps, the game's clip rate. Bones a clip does not animate stay on their bind pose.

## Check

```
blender -b --factory-startup --python tests/check_import.py
```

It imports both rigs and all 44 broom riding clips from `samples/character`, then compares every bone at a set of frames and half frames with forward kinematics done in game space. It prints PASS when every bone is within 1 mm. `tests/preview.py` opens Blender with the broom and Kliff seated on it for a look.

NOTES.md has how the game's data maps onto Blender and the evidence for each part.
