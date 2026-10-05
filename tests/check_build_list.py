"""Check Build characters from a list, and the clip search per skeleton.

    blender -b --factory-startup --python tests/check_build_list.py -- [game folder]

Needs the game installed. It requires:

  * Import character to play the clip given with it, and its clip search
    to offer the clips of the character typed in the same dialog;
  * the clip search for Kliff's skeleton to list only clips in 1_pc/1_phm/,
    the Wyvern's only its own, and a skeleton with no clips of its own
    every clip;
  * Kliff's own folder's clips to list before its subfolders', so
    `nor std idle` finds his standing idle within the search's 300 names;
  * a list of Kliff with a broom idle, the Wyvern with its air idle and a
    name that matches no character to build the two, each in a collection
    of its own, side by side without overlapping, each playing its clip,
    and to report the third as not built;
  * each built character to be saved as a .blend of its own that opens on
    a scene with the armature, its meshes and its clip.

Exit code 0 means every check passed.
"""

import os
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import packs  # noqa: E402

LIST = """# test list
cd_phm_macduff_00000  1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01
cd_m0004_00_wyvern_0001_00000  cd_rd_wyvern_basic_00_00_air_std_idle_00   # trailing comment
no_such_character_anywhere
"""


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_clip_filter(idx):
    phm = packs.clips_for(idx, "character/model/1_pc/1_phm/phm_01")
    wyv = packs.clips_for(idx, "character/model/2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/cd_m0004_00_wyvern")
    none = packs.clips_for(idx, "character/model/2_mon/cd_m0002_00_fourfeet/cd_m0002_00_skunky/cd_m0002_00_skunky")
    ok = (all(c.startswith("1_pc/1_phm/") for c in phm) and all("cd_m0004_00_wyvern/" in c for c in wyv)
          and none is idx.clips and 0 < len(wyv) < len(phm) < len(idx.clips))
    return report(ok, f"clip search per skeleton: {len(phm)} for Kliff, {len(wyv)} for the Wyvern, "
                      f"all {len(idx.clips)} for a skeleton with none of its own")


def check_main_first(idx):
    """Kliff's own folder's clips list before its subfolders', each in path
    order, so the guide's first search finds his standing idle."""
    folder = "1_pc/1_phm/"
    phm = packs.clips_for(idx, "character/model/1_pc/1_phm/phm_01")
    deep = ["/" in c[len(folder):] for c in phm]
    main = deep.count(False)
    hits = packs.search(phm, "nor std idle")
    ok = (deep == sorted(deep) and phm[:main] == sorted(phm[:main]) and phm[main:] == sorted(phm[main:])
          and folder + "cd_phm_basic_00_00_nor_std_idle_00" in hits)
    return report(ok, f"Kliff's {main} own clips list before his subfolders', and nor std idle finds his "
                      f"standing idle among its {len(hits)} names")


def check_single():
    """Import character with a clip, and its clip search."""
    class Props:
        character = "cd_m0004_00_wyvern_0001_00000"
    found = cd_animator._character_clip_names(Props(), bpy.context, "idle")
    res = bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", textures=False,
                                             clip="cd_phm_rd_broom_basic_00_00_nor_std_idle_01")
    arm = bpy.context.view_layer.objects.active
    action = arm.animation_data.action if arm.animation_data else None
    ok = (res == {"FINISHED"} and action is not None and found
          and all("cd_m0004_00_wyvern/" in c for c in found))
    fails = report(ok, f"Import character plays its clip ({action.name if action else None}); the dialog's "
                       f"clip search for the Wyvern offers {len(found)} Wyvern idles")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    return fails


def check_list(folder):
    fails = 0
    text = bpy.data.texts.new("CD characters")
    text.write(LIST)
    res = bpy.ops.cd_animator.game_characters(text=text.name, textures=False, folder=folder, gap=0.5)
    top = bpy.data.collections.get("CD characters")
    colls = list(top.children) if top else []
    arms = [next((o for o in c.objects if o.type == "ARMATURE"), None) for c in colls]
    fails += report(res == {"FINISHED"} and len(colls) == 2 and all(arms),
                    f"two of three listed characters built, each in its own collection: {[c.name for c in colls]}")
    clips = [a.animation_data.action.name if a and a.animation_data and a.animation_data.action else None for a in arms]
    fails += report(all(clips), f"each plays its clip: {clips}")

    spans = []
    for a in arms:
        xs = [(a.matrix_world @ o.matrix_local @ __import__("mathutils").Vector(c)).x
              for o in a.children if o.type == "MESH" for c in o.bound_box]
        spans.append((min(xs), max(xs)))
    apart = all(spans[i][1] <= spans[i + 1][0] + 1e-4 for i in range(len(spans) - 1))
    fails += report(apart, "side by side without overlapping: " + ", ".join(f"{lo:.2f} to {hi:.2f} m" for lo, hi in spans))

    files = sorted(f for f in os.listdir(folder) if f.endswith(".blend"))
    good = 0
    for f in files:
        with bpy.data.libraries.load(os.path.join(folder, f)) as (src, dst):
            dst.scenes = list(src.scenes)
        scene = dst.scenes[0]
        objs = list(scene.collection.all_objects)
        arm = next((o for o in objs if o.type == "ARMATURE"), None)
        meshes = [o for o in objs if o.type == "MESH"]
        if arm and meshes and arm.animation_data and arm.animation_data.action:
            good += 1
    fails += report(len(files) == 2 and good == 2, f"{len(files)} .blend files written, {good} open on a scene "
                                                   f"with the armature, its meshes and its clip")
    return fails


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_clip_filter(idx)
    fails += check_main_first(idx)
    fails += check_single()
    with tempfile.TemporaryDirectory() as folder:
        fails += check_list(folder)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
