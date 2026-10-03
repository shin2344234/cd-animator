"""Check every skeleton and each clip layout, straight from the game's packs.

    blender -b --factory-startup --python tests/check_skeletons.py -- [game folder]

Needs the game installed; the folder is found through Steam when not given.
It builds an armature from every skeleton in the game and requires one bone
per bone in the file. Then, for a clip of each header layout, on the
Wyvern, the horse, the bear and Kliff, it imports the skeleton and the clip
from the packs and requires:

  * every track to find its bone, except on clips made for another of the
    game's Kliff-shaped skeletons, whose missing bones are counted;
  * scale keys to show as the bones' pose scale;
  * an unchanged export to give the game's clip and metadata back byte for
    byte, and a LOD with the game LOD's tracks in its order.

Last it turns a Wyvern bone, exports, and requires the file to hold the turn
and every other track unchanged. Exit code 0 means every check passed.
"""

import os
import sys
import tempfile
import time

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import convert, export, packs  # noqa: E402
from cd_animator.formats import paa, paa_codec, paz  # noqa: E402

PHM = "character/model/1_pc/1_phm/phm_01"
WYVERN = "character/model/2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/cd_m0004_00_wyvern"
WYVERN_IDLE = "2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/00_mon/cd_rd_wyvern_basic_00_00_air_std_idle_00"

# (skeleton, clip, bones the skeleton lacks, what the clip shows)
CASES = [
    (WYVERN, WYVERN_IDLE, 0, "the Wyvern, flags 0x0F"),
    ("character/model/4_riding/cd_r0002_00_fourfeet/cd_r0002_00_horse/cd_r0002_00_horse",
     "4_riding/cd_r0002_00_fourfeet/cd_r0002_00_horse/cd_prh_basic_00_00_nor_std_idle_00", 0,
     "the horse, flags 0xCF, scale keys"),
    ("character/model/2_mon/cd_m0001_00_twofeet/cd_m0001_00_bear/cd_m0001_00_bear",
     "2_mon/cd_m0001_00_twofeet/cd_m0001_00_bear/00_mon/cd_bear_basic_00_00_nor_std_idle_00", 0, "the bear, flags 0x4F"),
    (PHM, "1_pc/1_phm/00_riding/cd_phm_rd_bear_basic_00_00_nor_std_idle_00", 0, "Kliff on the bear, scale keys"),
    (PHM, "1_pc/1_phm/00_riding/cd_phm_rd_wyvern_basic_00_00_air_std_idle_00", 0, "Kliff on the Wyvern, five block counts"),
    (PHM, "1_pc/1_phm/99_autofacial/english(us)/ndm_adult_1_deerking_boss_3100_npc_00_00001", 0,
     "a facial clip, animated non-uniform scale"),
    (PHM, "1_pc/1_phm/cd_phm_00_00_basic_skill_normal_chargelightning_action_000", 8, "flags 0, no lead records"),
    (PHM, "1_pc/1_phm/cd_phm_basic_00_00_sit_holepass_move_walk_f_ing_00", 6, "a UTF-16 tag"),
]


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def remove(obj):
    arm = obj.data
    bpy.data.objects.remove(obj)
    bpy.data.armatures.remove(arm)


def game_heads(sk):
    """Each bone's bind position in Blender space, through the game's
    hierarchy with bind scale."""
    full = []
    for b in sk.bones:
        size = Matrix.Diagonal(convert.vec_in(b.scale).to_4d())
        local = convert.matrix_in(b.quat, b.trans) @ size
        full.append(local if b.parent < 0 else full[b.parent] @ local)
    return [m.translation for m in full]


def check_all_skeletons(idx):
    t = time.time()
    bad, worst, where = [], 0.0, ""
    for name in idx.skeletons:
        res = bpy.ops.cd_animator.game_skeleton(skeleton=name)
        obj = bpy.context.object
        sk = paa.read_pab(paz.read(idx.by_path[name + ".pab"]))
        if res != {"FINISHED"} or len(obj.data.bones) != len(sk.bones):
            bad.append(name)
        else:
            for b, head in zip(sk.bones, game_heads(sk)):
                gap = (obj.data.bones[b.name].head_local - head).length
                if gap > worst:
                    worst, where = gap, f"{os.path.basename(name)} {b.name}"
        if res == {"FINISHED"}:
            remove(obj)
    for name in bad[:5]:
        print("    ", name)
    fails = report(not bad, f"{len(idx.skeletons)} skeletons build an armature with every bone, {len(bad)} do not "
                            f"({time.time() - t:.0f} s)")
    return fails + report(worst < 1e-4, f"every bone sits where the game's hierarchy puts it, worst {worst * 1000:.4f} mm ({where})")


def scale_shows(rig, td, step_of):
    """Worst gap between a scale key and the bone's pose scale on its frame."""
    names = {paa_codec.bone_hash(b.name): b.name for b in rig.data.bones}
    worst, seen = 0.0, 0
    for bt in td.bones:
        name = names.get(bt.name_hash)
        if not name or not bt.scale_keys:
            continue
        axis = rig.data.bones[name]["cd_axis"]
        for k in bt.scale_keys[:4]:
            bpy.context.scene.frame_set(k.frame * step_of(bt.kind))
            want = convert.scale_to_basis(axis, (k.x, k.y, k.z))
            worst = max(worst, (rig.pose.bones[name].scale - want).length)
            seen += 1
    return worst, seen


def check_case(idx, out, skel, clip, missing, what):
    fails = 0
    print(f"{what}: {os.path.basename(clip)}")
    bpy.ops.cd_animator.game_skeleton(skeleton=skel)
    rig = bpy.context.object
    res = bpy.ops.cd_animator.game_clip(clip=clip)
    action = rig.animation_data.action
    path = packs.fetch_clip(idx, clip)
    _h, td = paa_codec.decode_file(open(path, "rb").read())
    names = {paa_codec.bone_hash(b.name) for b in rig.data.bones}
    lacks = sum(1 for b in td.bones if b.name_hash not in names)
    fails += report(res == {"FINISHED"} and lacks == missing,
                    f"imported, {len(td.bones)} tracks, {lacks} for bones this skeleton lacks (expected {missing})")
    if any(b.scale_keys for b in td.bones):
        worst, seen = scale_shows(rig, td, paa_codec.frame_step)
        fails += report(worst < 1e-6, f"{seen} scale keys show as pose scale, worst {worst:.2e}")

    leaf = os.path.basename(clip)
    written, _problems = export.export_with_companions(rig, action, os.path.join(out, leaf + ".paa"))
    fails += report(open(written[0], "rb").read() == open(path, "rb").read(), "unchanged export is the game's clip")
    game_mb = path[:-4] + ".paa_metabin"
    if os.path.exists(game_mb):
        fails += report(open(written[2], "rb").read() == open(game_mb, "rb").read(), "metabin is the game's")
    game_lod = path[:-4] + "_lod.paa"
    if os.path.exists(game_lod):
        _a, mine = paa_codec.decode_file(open(written[1], "rb").read())
        _b, theirs = paa_codec.decode_file(open(game_lod, "rb").read())
        same = [(b.name_hash, b.kind) for b in mine.bones] == [(b.name_hash, b.kind) for b in theirs.bones]
        fails += report(same and _a.flags == _b.flags, f"LOD has the game LOD's {len(theirs.bones)} tracks and flags {_b.flags:#x}")
    return fails, rig, action


def check_edit(rig, action, out):
    """Turn the first rotated bone's first key and export."""
    bag = export._channelbag(rig, action)
    fc = next(f for f in bag.fcurves if f.data_path.endswith(".rotation_quaternion") and f.array_index == 1)
    bone = fc.data_path[len('pose.bones["'):].partition('"]')[0]
    fc.keyframe_points[0].co[1] += 0.25
    fc.update()
    path = os.path.join(out, "wyvern_edit.paa")
    export.export_clip(rig, action, path)
    _a, new = paa_codec.decode_file(open(path, "rb").read())
    _b, old = paa_codec.decode_file(open(action["cd_source"], "rb").read())
    h = paa_codec.bone_hash(bone)
    changed = [b.name for b, o in zip(new.bones, old.bones) if b.rot_keys != o.rot_keys or b.pos_keys != o.pos_keys]
    nb = next(b for b in new.bones if b.name_hash == h)
    axis = rig.data.bones[bone]["cd_axis"]
    k = nb.rot_keys[0]
    q = convert.key_to_basis(axis, (k.x, k.y, k.z, k.w), (0, 0, 0))[0]
    want = [fcx.keyframe_points[0].co[1] for fcx in sorted(
        (f for f in bag.fcurves if f.data_path == fc.data_path), key=lambda f: f.array_index)]
    gap = max(abs(a - b) for a, b in zip(q, want))
    return report(changed == [bone] and gap < 2e-3,
                  f"edited {bone}: only its track changed, key holds the edit within {gap:.1e}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    for h in list(bpy.app.handlers.frame_change_pre):
        bpy.app.handlers.frame_change_pre.remove(h)
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    out = tempfile.mkdtemp(prefix="cd_skeletons_")
    fails = check_all_skeletons(idx)
    wyvern = None
    for case in CASES:
        f, rig, action = check_case(idx, out, *case)
        fails += f
        if case[1] == WYVERN_IDLE:
            wyvern = (rig, action)
    fails += check_edit(*wyvern, out)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
