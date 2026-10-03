"""Check reading skeletons and clips straight from the game's packs.

    blender -b --factory-startup --python tests/check_packs.py -- [game folder] [samples folder]

Needs the game installed; the folder is found through Steam when not given.
It reads the index of groups 0009 and 0010, unpacks Kliff's skeleton (stored
LZ4-compressed) and his broom idle with its LOD and metadata and requires
them byte for byte equal to the unpacked samples, imports the skeleton and
the clip through the new operators and requires every bone to pose as the
sample import does, exports the game's clip unchanged and requires the
game's bytes back, starts a new clip from a game clip, and checks the name
search and lookup, including a clip name two folders share.
Exit code 0 means every check passed.
"""

import os
import sys
import tempfile
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import anim, export, packs  # noqa: E402
from cd_animator.formats import paz  # noqa: E402

IDLE = "1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_idle_01"
SHARED = "cd_phm_lk_ptm_mace_01_05_att_kickhit_lk_phm_move_f_00"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    return not ok


def poses(obj, action, frames):
    obj.animation_data.action = action
    out = []
    for f in frames:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        out.append({pb.name: (obj.matrix_world @ pb.head, obj.matrix_world @ pb.tail) for pb in obj.pose.bones})
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    samples = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(HERE), "samples")
    cd_animator.register()
    for h in list(bpy.app.handlers.frame_change_pre):
        bpy.app.handlers.frame_change_pre.remove(h)
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    fails = 0

    t = time.time()
    idx = packs.index()
    fails += report(len(idx.clips) > 100000 and len(idx.skeletons) > 100,
                    f"index: {len(idx.clips)} clips, {len(idx.skeletons)} skeletons in {time.time() - t:.1f} s")

    pab = idx.by_path["character/model/1_pc/1_phm/phm_01.pab"]
    same = paz.read(pab) == open(os.path.join(samples, "character", "phm_01.pab"), "rb").read()
    fails += report(same and pab.stored != pab.size, f"phm_01.pab, LZ4 {pab.stored} -> {pab.size} bytes, equals the sample")
    clip_path = packs.fetch_clip(idx, IDLE)
    stem = clip_path[:-4]
    leaf = os.path.basename(IDLE)
    for got, want in ((clip_path, os.path.join(samples, "character", leaf + ".paa")),
                      (stem + "_lod.paa", os.path.join(samples, "character", leaf + "_lod.paa")),
                      (stem + ".paa_metabin", os.path.join(samples, "actionchart", leaf + ".paa_metabin"))):
        fails += report(open(got, "rb").read() == open(want, "rb").read(), f"cached {os.path.basename(got)} equals the sample")

    found = packs.search(idx.clips, "broom idle_01 phm_rd")
    fails += report(IDLE in found, f"search 'broom idle_01 phm_rd': {len(found)} hits, the broom idle among them")
    for typed in (IDLE, leaf, "character/motion/" + IDLE + ".paa", leaf + ".paa"):
        try:
            got = packs.resolve(idx.clips, typed, "clip", prefix=packs.MOTION, ext=".paa")
        except packs.PackError as exc:
            got = str(exc)
        fails += report(got == IDLE, f"'{typed}' resolves to the broom idle")
    try:
        packs.resolve(idx.clips, SHARED, "clip", prefix=packs.MOTION, ext=".paa")
        fails += report(False, f"{SHARED} is refused as ambiguous")
    except packs.PackError as exc:
        fails += report(str(exc).startswith("2 clips"), f"{SHARED}: {exc}")

    res = bpy.ops.cd_animator.game_skeleton(skeleton="phm_01")
    game_rig = bpy.context.object
    fails += report(res == {"FINISHED"} and game_rig.type == "ARMATURE", "game_skeleton imports phm_01")
    res = bpy.ops.cd_animator.game_clip(clip=leaf)
    game_action = game_rig.animation_data.action
    fails += report(res == {"FINISHED"} and game_action.get("cd_source") == clip_path, "game_clip imports the broom idle from the cache")

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(samples, "character", "phm_01.pab"))
    disk_rig = bpy.context.object
    disk_action = anim.import_clip(bpy.context, disk_rig, os.path.join(samples, "character", leaf + ".paa"))[0]
    frames = (0, 13, 50, 99)
    a, b = poses(game_rig, game_action, frames), poses(disk_rig, disk_action, frames)
    worst = max(max((x[n][0] - y[n][0]).length, (x[n][1] - y[n][1]).length) for x, y in zip(a, b) for n in x)
    fails += report(worst < 1e-6, f"the game import poses as the sample import, worst {worst * 1000:.4f} mm")

    out = tempfile.mkdtemp(prefix="cd_packs_")
    written, _p = export.export_with_companions(game_rig, game_action, os.path.join(out, leaf + ".paa"))
    for w, src in zip(written, (clip_path, stem + "_lod.paa", stem + ".paa_metabin")):
        if w.endswith("_lod.paa"):
            continue   # the LOD is rebuilt, not copied; check_export covers it
        fails += report(open(w, "rb").read() == open(src, "rb").read(), f"unchanged export of {os.path.basename(w)} is the game's bytes")

    bpy.context.view_layer.objects.active = game_rig
    res = bpy.ops.cd_animator.game_new_clip(clip=leaf, clip_name="pack_new", frames=40, start="HOLD")
    act = game_rig.animation_data.action
    fails += report(res == {"FINISHED"} and act.name == "pack_new" and int(act.frame_end) == 40,
                    "game_new_clip starts a 40 frame clip from the broom idle")

    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
