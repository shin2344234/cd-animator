"""Check IK controls: hand and foot controls that pose Kliff's arms and legs.

    blender -b --factory-startup --python tests/check_ik.py -- [game folder]

Needs the game installed. On Kliff's standing idle, Add IK controls must
give his four limbs a control at the hand or foot and one at the elbow or
knee, in the bone collection "CD controls", and none of them a game bone.
Every bone of the limbs and a finger must then stay where the clip puts it,
its head, tail and a point 10 cm out along its X axis, which a twist moves,
within 1 mm on the frames the clip keys and 3 mm between them. Adding them
again to the same clip must be refused, and so must a skeleton with no Bip01
limbs, the broom's. Moving the left hand control 10 cm up on frame 60 must
put the forearm's tail there and turn the hand with its control. Export
must bake that and write no control: the clip imported onto a second Kliff
must have the left forearm's tail and hand within 3 mm of the first's. The
run imported onto the first Kliff must key the controls anew, with the
idle's keys and the pole angles kept, and stand within 1 mm of the run's own
pose on its keyed frames.
Exit code 0 means every check passed.
"""

import os
import sys
import tempfile

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import anim, export, ik, packs  # noqa: E402
from cd_animator.formats import paa_codec  # noqa: E402

IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
RUN = "1_pc/1_phm/cd_phm_basic_00_00_nor_move_run_f_ing_00"
FINGERS = ("Bip01 L Finger1", "Bip01 R Finger1")


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def watched(arm):
    return [n for limb in ik.limbs(arm) for n in limb[:3]] + list(FINGERS)


def pose(arm, frames):
    out = {}
    for f in frames:
        bpy.context.scene.frame_set(f)
        out[f] = {n: (pb.head.copy(), pb.tail.copy(), pb.matrix @ Vector((0.1, 0.0, 0.0)))
                  for n in watched(arm) for pb in [arm.pose.bones[n]]}
    return out


def keyed(arm, action):
    """Frames the clip keys some bone of each watched bone's chain, by bone."""
    bag = export._channelbag(arm, action)
    by_bone = {}
    for fc in bag.fcurves:
        by_bone.setdefault(ik._keyed(fc), set()).update(round(p.co[0]) for p in fc.keyframe_points)
    out = {}
    for n in watched(arm):
        out[n], b = set(), arm.data.bones[n]
        while b is not None:
            out[n] |= by_bone.get(b.name, set())
            b = b.parent
    return out


def miss(before, after, frames_by_bone):
    """The worst miss in mm on the keyed frames and between them."""
    on = off = 0.0
    for f, bones in before.items():
        for n, points in bones.items():
            d = max((a - b).length for a, b in zip(after[f][n], points)) * 1000
            if f in frames_by_bone[n]:
                on = max(on, d)
            else:
                off = max(off, d)
    return on, off


def refused():
    try:
        bpy.ops.cd_animator.ik_controls()
    except RuntimeError as exc:
        return str(exc)
    return None


def constraints(arm, on):
    for pb in arm.pose.bones:
        for c in pb.constraints:
            c.enabled = on


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    fails = 0
    scene = bpy.context.scene

    bpy.ops.cd_animator.game_skeleton(skeleton="cd_r0032_00_broom")
    broom = bpy.context.object
    broom.animation_data_create().action = bpy.data.actions.new("broom pose")
    why = refused()
    fails += report(why is not None and "no Bip01 arms or legs" in why, f"the broom refused: {why}")
    bpy.data.objects.remove(broom)

    bpy.ops.cd_animator.game_skeleton(skeleton="1_pc/1_phm/phm_01")
    arm = bpy.context.object
    bpy.ops.cd_animator.game_clip(clip=IDLE)
    idle = arm.animation_data.action
    end = int(idle.frame_range[1])
    frames = range(0, end + 1)
    before = pose(arm, frames)
    res = bpy.ops.cd_animator.ik_controls()
    found = ik.limbs(arm)
    ctrls = [n for limb in found for n in limb[3:]]
    coll = arm.data.collections.get(ik.COLLECTION)
    fails += report(res == {"FINISHED"} and len(found) == 4 and coll is not None
                    and sorted(b.name for b in coll.bones) == sorted(ctrls)
                    and not any("cd_index" in arm.data.bones[n] for n in ctrls),
                    f"controls on {len(found)} limbs, in {coll.name if coll else None}: {ctrls}")
    on, off = miss(before, pose(arm, frames), keyed(arm, idle))
    fails += report(on < 1.0 and off < 3.0, f"the idle's pose kept within {on:.3f} mm on keyed frames, {off:.3f} mm between")
    why = refused()
    fails += report(why is not None and "already keys" in why, f"adding them again to the idle refused: {why}")

    # Pose the left hand by its control on frame 60.
    hand, fore = arm.pose.bones["Bip01 L Hand"], arm.pose.bones["Bip01 L Forearm"]
    ctrl = arm.pose.bones["Ctrl L Hand"]
    scene.frame_set(60)
    m = ctrl.matrix.copy()
    m.translation.z += 0.1
    ctrl.matrix = m
    ctrl.keyframe_insert("location", frame=60)
    scene.frame_set(60)
    turned = max(abs(a - b) for ra, rb in zip(hand.matrix.to_3x3(), ctrl.matrix.to_3x3()) for a, b in zip(ra, rb))
    reached = (fore.tail - m.translation).length * 1000
    moved = (hand.head - before[60]["Bip01 L Hand"][0]).length * 1000
    fails += report(reached < 1.0 and turned < 1e-4 and 80 < moved < 120,
                    f"the left forearm's tail {reached:.3f} mm from the moved control, the hand turned with it "
                    f"({turned:.6f} off) and moved {moved:.1f} mm")
    shown = (fore.tail.copy(), hand.head.copy(), hand.tail.copy())

    tmp = tempfile.mkdtemp(prefix="cd_ik_")
    path = os.path.join(tmp, "ik_check.paa")
    export.export_clip(arm, idle, path, True)
    with open(path, "rb") as f:
        _header, td = paa_codec.decode_file(f.read())
    written = {t.name_hash for t in td.bones}
    stray = [n for n in ctrls if paa_codec.bone_hash(n) in written]
    bpy.ops.cd_animator.game_skeleton(skeleton="1_pc/1_phm/phm_01")
    second = bpy.context.object
    anim.import_clip(bpy.context, second, path)
    scene.frame_set(60)
    p2 = second.pose.bones
    far = max((p2["Bip01 L Forearm"].tail - shown[0]).length, (p2["Bip01 L Hand"].head - shown[1]).length,
              (p2["Bip01 L Hand"].tail - shown[2]).length) * 1000
    fails += report(not stray and far < 3.0, f"exported with no control tracks {stray}; a second Kliff's left "
                                            f"forearm and hand {far:.3f} mm from the first's on frame 60")
    bpy.data.objects.remove(second)

    counts = {fc.data_path: len(fc.keyframe_points) for fc in export._channelbag(arm, idle).fcurves
              if ik._keyed(fc) in ctrls}
    angles = [arm.pose.bones[limb[1]].constraints[ik.IK].pole_angle for limb in found]
    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=RUN)
    run = arm.animation_data.action
    constraints(arm, False)
    run_frames = range(0, int(run.frame_range[1]) + 1)
    run_before = pose(arm, run_frames)
    constraints(arm, True)
    res = bpy.ops.cd_animator.ik_controls()
    on, _off = miss(run_before, pose(arm, run_frames), keyed(arm, run))
    kept = {fc.data_path: len(fc.keyframe_points) for fc in export._channelbag(arm, idle).fcurves
            if ik._keyed(fc) in ctrls}
    same_angles = [arm.pose.bones[limb[1]].constraints[ik.IK].pole_angle for limb in found] == angles
    fails += report(res == {"FINISHED"} and kept == counts and same_angles and on < 1.0,
                    f"the run keyed its own controls, within {on:.3f} mm of its pose; the idle's keys kept "
                    f"{kept == counts}, the pole angles {same_angles}")

    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
