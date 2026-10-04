"""Check Retarget from armature with a rig made up to differ from the game's.

    blender -b --factory-startup --python tests/check_retarget.py -- [game folder]

Needs the game installed. The source rig has Mixamo's bone names, each
bone's rest pointing straight up with its own roll, unlike the game's, and
is 0.8 times Kliff's size. It is keyed so each bone turns, in world space,
as Kliff's bone turns in his run. Retargeting it onto a second Kliff
skeleton must:

  * match all 22 body bones, refusing a rig that has only a few;
  * give every matched bone the run's world rotation within 0.1 degrees on
    every frame, and the pelvis the run's path within 1 mm, the travel
    scaled back up by the hip heights;
  * give the clip the source's length, and write keys Export accepts.

Exit code 0 means every check passed.
"""

import math
import os
import sys
import tempfile

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import packs, retarget  # noqa: E402

RUN = "1_pc/1_phm/cd_phm_basic_00_00_nor_move_run_f_ing_00"
SIZE = 0.8
MIXAMO = {"Bip01 Pelvis": "Hips", "Bip01 Spine": "Spine", "Bip01 Spine1": "Spine1", "Bip01 Spine2": "Spine2",
          "Bip01 Neck": "Neck", "Bip01 Head": "Head"}
for side, s in (("L", "Left"), ("R", "Right")):
    MIXAMO.update({f"Bip01 {side} Clavicle": f"{s}Shoulder", f"Bip01 {side} UpperArm": f"{s}Arm",
                   f"Bip01 {side} Forearm": f"{s}ForeArm", f"Bip01 {side} Hand": f"{s}Hand",
                   f"Bip01 {side} Thigh": f"{s}UpLeg", f"Bip01 {side} Calf": f"{s}Leg",
                   f"Bip01 {side} Foot": f"{s}Foot", f"Bip01 {side} Toe0": f"{s}ToeBase"})


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def skeleton():
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.cd_animator.game_skeleton(skeleton="1_pc/1_phm/phm_01")
    return bpy.context.view_layer.objects.active


def make_source(kliff, names):
    """A rig with `names` bones at Kliff's bone heads times SIZE, each rest
    pointing up with its own roll, parented as the game bones are."""
    data = bpy.data.armatures.new("mixamo")
    rig = bpy.data.objects.new("mixamo", data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for i, (game, src) in enumerate(names.items()):
        e = data.edit_bones.new("mixamorig:" + src)
        e.head = kliff.data.bones[game].head_local * SIZE
        e.tail = e.head + Vector((0, 0, 0.08))
        e.roll = 0.37 * i
    for game, src in names.items():
        p = kliff.data.bones[game].parent
        while p is not None and p.name not in names:
            p = p.parent
        if p is not None:
            data.edit_bones["mixamorig:" + src].parent = data.edit_bones["mixamorig:" + names[p.name]]
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def world_rot(obj, bone):
    return (obj.matrix_world @ obj.pose.bones[bone].matrix).to_quaternion()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    packs.index()
    scene = bpy.context.scene

    truth = skeleton()
    bpy.ops.cd_animator.game_clip(clip=RUN, voice=False)
    n = int(round(truth.animation_data.action.frame_range[1]))
    rig = make_source(truth, MIXAMO)
    rest_k = {g: (truth.matrix_world @ truth.data.bones[g].matrix_local).to_quaternion() for g in MIXAMO}
    rest_s = {g: (rig.matrix_world @ rig.data.bones["mixamorig:" + s].matrix_local).to_quaternion()
              for g, s in MIXAMO.items()}
    hips_k = truth.data.bones["Bip01 Pelvis"].head_local
    hips_s = rig.data.bones["mixamorig:Hips"].head_local
    rig.animation_data_create()
    rig.animation_data.action = bpy.data.actions.new("source")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    truth_rot, truth_hips = {}, []
    for f in range(n + 1):
        scene.frame_set(f)
        truth_hips.append((truth.matrix_world @ truth.pose.bones["Bip01 Pelvis"].head).copy())
        for g in MIXAMO:
            truth_rot[g, f] = world_rot(truth, g)
        for g, s in MIXAMO.items():
            pb = rig.pose.bones["mixamorig:" + s]
            m = (truth_rot[g, f] @ rest_k[g].inverted() @ rest_s[g]).to_matrix().to_4x4()
            bpy.context.view_layer.update()
            m.translation = hips_s + (truth_hips[f] - hips_k) * SIZE if s == "Hips" else pb.head
            pb.matrix = m
            bpy.context.view_layer.update()
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.keyframe_insert("location", frame=f)

    target = skeleton()
    bpy.ops.cd_animator.game_new_clip(clip=RUN, clip_name="cd_phm_retarget_check_00", frames=12, start="HOLD")
    action = target.animation_data.action
    few = make_source(truth, {g: s for g, s in list(MIXAMO.items())[:5]})
    try:
        retarget.retarget(target, few, action, range(0, 2))
        refused = False
    except retarget.RetargetError:
        refused = True
    bpy.data.objects.remove(few)
    pairs = retarget.mapping(target, rig)
    fails = report(len(pairs) == 22 and refused, f"matched {len(pairs)} bones; a 5 bone rig refused: {refused}")

    rig.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.cd_animator.retarget()
    worst, worst_hips = 0.0, 0.0
    for f in range(n + 1):
        scene.frame_set(f)
        for g in MIXAMO:
            d = truth_rot[g, f].rotation_difference(world_rot(target, g)).angle
            worst = max(worst, min(d, 2 * math.pi - d))
        worst_hips = max(worst_hips, (target.matrix_world @ target.pose.bones["Bip01 Pelvis"].head - truth_hips[f]).length)
    fails += report(math.degrees(worst) < 0.1 and worst_hips < 0.001,
                    f"over {n + 1} frames: worst bone {math.degrees(worst):.4f} degrees, pelvis {worst_hips * 1000:.3f} mm")

    out = os.path.join(tempfile.mkdtemp(prefix="cd_retarget_"), "run.paa")
    bpy.ops.cd_animator.export_paa(filepath=out, clip="ACTION")
    fails += report(round(action.frame_range[1]) == n and os.path.getsize(out) > 1000,
                    f"clip {round(action.frame_range[1])} frames like the source's {n}, exported {os.path.getsize(out)} bytes")
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
