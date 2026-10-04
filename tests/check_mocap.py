"""Check Motion capture from CMU without going online.

    blender -b --factory-startup --python tests/check_mocap.py -- [game folder]

Needs the game installed and out/mocap/90_32.bvh, CMU's moonwalk from the
BVH release, which it copies into the add-on's cache so nothing downloads.
It must:

  * read 2,435 motions from the bundled index and find 90_32 by the word
    moonwalk and by its name alone;
  * refuse words that match many motions or none;
  * point 90_32 at data/090/90_32.bvh of the release and 01_01 at
    data/001/01_01.bvh;
  * import the moonwalk at 30 frames a second, frames 1 to 182, and leave
    Kliff's armature active with its new clip and the BVH selected, so
    Retarget from armature runs straight away and gives a 180-frame clip.

Exit code 0 means every check passed.
"""

import os
import shutil
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import mocap, packs  # noqa: E402

IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
MOON = os.path.join(ROOT, "out", "mocap", "90_32.bvh")
RELEASE = "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    packs.index()

    moon = mocap.find("moonwalk")
    fails = report(len(mocap.motions()) == 2435 and moon.startswith("90_32 moonwalk") and mocap.find("90_32") == moon,
                   f"{len(mocap.motions())} motions, moonwalk found as {moon!r}")
    refused = []
    for text in ("dance", "no such motion"):
        try:
            mocap.find(text)
        except mocap.MocapError:
            refused.append(text)
    fails += report(refused == ["dance", "no such motion"], f"refused {refused}")
    urls = mocap.url("90_32"), mocap.url("01_01")
    fails += report(urls == (RELEASE + "090/90_32.bvh", RELEASE + "001/01_01.bvh"), f"downloads from {urls}")

    cached = os.path.join(packs.cache_root(), "mocap", "90_32.bvh")
    os.makedirs(os.path.dirname(cached), exist_ok=True)
    shutil.copyfile(MOON, cached)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.cd_animator.game_skeleton(skeleton="1_pc/1_phm/phm_01")
    kliff = bpy.context.view_layer.objects.active
    bpy.ops.cd_animator.game_new_clip(clip=IDLE, clip_name="cd_phm_mocap_check_00", frames=12, start="HOLD")
    bpy.context.scene.render.fps = 24
    bpy.ops.cd_animator.mocap(motion="moonwalk")
    source = next(o for o in bpy.context.selected_objects if o is not kliff and o.type == "ARMATURE")
    first, last = source.animation_data.action.frame_range
    active = bpy.context.view_layer.objects.active is kliff
    bpy.ops.cd_animator.retarget(face_forward=True)
    length = round(kliff.animation_data.action.frame_end)
    fails += report(active and source.get("cd_mocap") == moon and bpy.context.scene.render.fps == 30
                    and (round(first), round(last)) == (1, 182) and length == 180,
                    f"imported {source.name}, frames {first:g} to {last:g} at {bpy.context.scene.render.fps} a "
                    f"second, Kliff active: {active}; retargeted into {length} frames")
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
