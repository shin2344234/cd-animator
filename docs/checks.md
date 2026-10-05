# Checks

The scripts in `tests` check the add-on against the game's own data, headless. Each prints a line per check, `ok` or `FAIL`, then `PASS` or the number of failures, and exits with 0 only when every check passed. Run one from the repository folder:

```
blender -b --factory-startup --python tests/check_ik.py
```

Four of them read only the clips unpacked into `samples/character`, and take another samples folder after `--`. `check_packs.py` compares those files with the packs. The rest read the game's packs, and take another game folder after `--` when the game is not where Steam says. None of them touch the game's folder. The two that test sending to the game write into a temporary folder that stands in for `bin64`.

A few need more than the game. `check_packs.py` takes the game folder first and then the samples folder. `check_mocap.py` needs `out/mocap/90_32.bvh`, CMU's moonwalk from the BVH release, and copies it into the add-on's cache so nothing downloads. `check_voice.py` needs the game's English voice installed.

| Script | Reads | What it checks |
|---|---|---|
| `check_import.py` | samples | The importers, bone by bone, against the game's own maths |
| `check_export.py` | samples | Every unchanged clip exports byte for byte, and edits survive a round trip |
| `check_new_clip.py` | samples | New clips, clip lengths and event editing |
| `check_bake.py` | samples | Export bakes constraints, IK, drivers and Euler rotation |
| `check_packs.py` | game, samples | Skeletons and clips read straight from the packs match the unpacked files |
| `check_skeletons.py` | game | Every skeleton and every clip layout in the game |
| `check_mesh.py` | game | Meshes skinned to their armatures. `--all` tries every mesh |
| `check_textures.py` | game | Materials and textures on imported meshes |
| `check_character.py` | game | Characters built from their appearance files, with their own proportions |
| `check_gear.py` | game | The character and item tables, and characters built with gear |
| `check_build_list.py` | game | Build characters from a list, and the clip search per skeleton |
| `check_props.py` | game | Weapons and props, their own bones, and sockets |
| `check_chains.py` | game | Chain bones and their simulation |
| `check_cloth.py` | game | Cloth pins read from the meshes, and cloaks simulated |
| `check_sway.py` | game | Hair and beard sway values, bones and springs |
| `check_face.py` | game | A facial clip over a body clip, and its export |
| `check_voice.py` | game | Voice lines converted for lip sync clips, and their sound strip |
| `check_tags.py` | game | Tag footsteps against the game's own footstep events |
| `check_retarget.py` | game | Retarget from armature, with a rig made up to differ from the game's |
| `check_mocap.py` | game | Motion capture from CMU, without going online |
| `check_ik.py` | game | IK controls keep the clip's pose, pose a hand, and export |
| `check_send.py` | game | Send to game, the In the game list, and taking clips out |
| `check_seen.py` | game | Seen in game, reading the clips the game played from the log |
| `check_new_name.py` | game | Charts and blends pointed at new clips, moves on keys with their expressions, sounds and props |

The Check section of the repository's `README.md` lists exactly what each script requires, with the numbers it expects.
