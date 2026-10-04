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
    scaled back up by the leg lengths, the first frame's pelvis over the
    rest pelvis and the feet's lowest point at their rest height, with
    Face forward off;
  * do the same with a T-pose keyed before the run, the arms straight out
    as CMU's BVH files start: that frame stands for the source's rest pose
    and stays out of the clip;
  * with Face forward, give the pelvis no turn about the vertical on the
    first frame;
  * give the clip the source's length, and write keys Export accepts;
  * with a start, an end and a speed, take the run's frames 10 to 30 at
    half speed into 40 frames, frame 2n the run's frame 10 + n within 0.1
    degrees;
  * Make it loop over 10 frames end the clip on its first frame's pose,
    the pelvis where it starts, and leave the frames after the blend as
    they were;
  * with Travel, on a clip from the standing idle, which has no
    B_MoveControl_01 track, move the body as before and B_MoveControl_01
    and Bip01 as the pelvis travels over the ground, within 1 mm, and
    export B_MoveControl_01 in floats, as the game's clips have it, with a
    motion block in the metadata;
  * Make it loop on a travelling clip keep its travel: B_MoveControl_01
    starts where it rests and ends as far on as before the loop, and the
    body stands the same from it on the first and last frames;
  * End on his idle over 10 frames give the travelling run's last frame
    the standing idle's first, every bone's turn within 0.1 degrees and
    the pelvis from B_MoveControl_01 within 1 mm, leave the frames
    before the blend as they were, and export every track from frame 0, as
    the game's clips have them.

Exit code 0 means every check passed.
"""

import math
import os
import sys
import tempfile

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import packs, retarget  # noqa: E402
from cd_animator.formats import metabin_codec, paa_codec  # noqa: E402

RUN = "1_pc/1_phm/cd_phm_basic_00_00_nor_move_run_f_ing_00"
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
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
    truth_rot, truth_hips, truth_low = {}, [], 1e9
    for f in range(n + 1):
        scene.frame_set(f)
        truth_hips.append((truth.matrix_world @ truth.pose.bones["Bip01 Pelvis"].head).copy())
        truth_low = min([truth_low] + [(truth.matrix_world @ truth.pose.bones[b].head).z for b in retarget.FEET])
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
    rest_low = min((truth.matrix_world @ truth.data.bones[b].head_local).z for b in retarget.FEET)
    shift = truth_hips[0] - truth.matrix_world @ hips_k
    shift.z = truth_low - rest_low

    def matches():
        worst, worst_hips = 0.0, 0.0
        for f in range(n + 1):
            scene.frame_set(f)
            for g in MIXAMO:
                d = truth_rot[g, f].rotation_difference(world_rot(target, g)).angle
                worst = max(worst, min(d, 2 * math.pi - d))
            pelvis = target.matrix_world @ target.pose.bones["Bip01 Pelvis"].head
            worst_hips = max(worst_hips, (pelvis - truth_hips[f] + shift).length)
        return (math.degrees(worst) < 0.1 and worst_hips < 0.001 and round(action.frame_range[1]) == n,
                f"over {n + 1} frames: worst bone {math.degrees(worst):.4f} degrees, pelvis {worst_hips * 1000:.3f} mm, "
                f"clip {round(action.frame_range[1])} frames")

    bpy.ops.cd_animator.retarget(face_forward=False)
    ok, what = matches()
    fails += report(ok, what)

    # Frame -1: a T-pose, the source's bind pose with the arms aimed straight out.
    aim = {}
    for side, x in (("L", 1.0), ("R", -1.0)):
        for g in (f"Bip01 {side} UpperArm", f"Bip01 {side} Forearm"):
            d = truth.data.bones[retarget.NEXT[g][0]].head_local - truth.data.bones[g].head_local
            aim[g] = d.rotation_difference(Vector((x, 0, 0)))
        aim[f"Bip01 {side} Hand"] = aim[f"Bip01 {side} Forearm"]
    scene.frame_set(-1)
    for g, src in MIXAMO.items():
        pb = rig.pose.bones["mixamorig:" + src]
        m = (aim.get(g, Quaternion()) @ rest_s[g]).to_matrix().to_4x4()
        bpy.context.view_layer.update()
        m.translation = hips_s if src == "Hips" else pb.head
        pb.matrix = m
        bpy.context.view_layer.update()
        pb.keyframe_insert("rotation_quaternion", frame=-1)
        pb.keyframe_insert("location", frame=-1)
    reference, frames = retarget.split(target, rig, range(-1, n + 1))
    bpy.ops.cd_animator.retarget(face_forward=False)
    ok, what = matches()
    fails += report(ok and reference == -1 and frames.start == 0,
                    f"with a T-pose on frame -1, the reference: {reference}; {what}")

    bpy.ops.cd_animator.retarget(face_forward=True)
    scene.frame_set(0)
    pelvis = world_rot(target, "Bip01 Pelvis") @ rest_k["Bip01 Pelvis"].inverted()
    yaw = math.degrees(retarget._yaw(pelvis))
    fails += report(abs(yaw) < 0.1, f"facing forward: pelvis turned {yaw:.4f} degrees about the vertical on frame 0")

    out = os.path.join(tempfile.mkdtemp(prefix="cd_retarget_"), "run.paa")
    bpy.ops.cd_animator.export_paa(filepath=out, clip="ACTION")
    fails += report(round(action.frame_range[1]) == n and os.path.getsize(out) > 1000,
                    f"clip {round(action.frame_range[1])} frames like the source's {n}, exported {os.path.getsize(out)} bytes")

    def angle(a, b):
        d = a.rotation_difference(b).angle
        return math.degrees(min(d, 2 * math.pi - d))

    bpy.ops.cd_animator.retarget(face_forward=False, start=10, end=30, speed=0.5)
    worst = 0.0
    for i in range(21):
        scene.frame_set(2 * i)
        worst = max([worst] + [angle(truth_rot[g, 10 + i], world_rot(target, g)) for g in MIXAMO])
    length = round(action.frame_range[1])
    fails += report(length == 40 and worst < 0.1,
                    f"frames 10 to 30 at half speed: {length} frames, worst bone {worst:.4f} degrees on the run's frames")

    def pose(f):
        scene.frame_set(f)
        return {g: world_rot(target, g) for g in MIXAMO}, (target.matrix_world @ target.pose.bones["Bip01 Pelvis"].head).copy()

    before = {f: pose(f) for f in (10, 20, 30)}
    bpy.ops.cd_animator.make_loop(frames=10)
    length = round(action.frame_range[1])
    (first, first_hips), (last, last_hips) = pose(0), pose(length)
    seam = max(angle(first[g], last[g]) for g in MIXAMO)
    kept = max(angle(before[f][0][g], pose(f)[0][g]) for f in (10, 20, 30) for g in MIXAMO)
    fails += report(length == 30 and seam < 0.1 and (first_hips - last_hips).length < 0.001 and kept < 0.1,
                    f"made a loop: {length} frames, first and last frames {seam:.4f} degrees and "
                    f"{(first_hips - last_hips).length * 1000:.2f} mm apart, frames 10 to 30 moved {kept:.4f} degrees")

    bpy.ops.cd_animator.game_new_clip(clip=IDLE, clip_name="cd_phm_travel_check_00", frames=12, start="HOLD")
    action = target.animation_data.action
    rig.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.cd_animator.retarget(face_forward=False, travel=True)
    ok, what = matches()
    tw = target.matrix_world

    def went(b, f):
        scene.frame_set(f)
        return tw @ target.pose.bones[b].head - tw @ target.data.bones[b].head_local

    ground = truth_hips[n] - truth_hips[0]
    ground.z = 0
    off = max(max(went(b, 0).length, (went(b, n) - ground).length) for b in retarget.TRAVEL)
    out = os.path.join(os.path.dirname(out), "travel.paa")
    bpy.ops.cd_animator.export_paa(filepath=out, clip="ACTION")
    _h, td = paa_codec.decode_file(open(out, "rb").read())
    mc = next(b for b in td.bones if b.name_hash == paa_codec.bone_hash("B_MoveControl_01"))
    stored = math.hypot(mc.pos_keys[-1].x - mc.pos_keys[0].x, mc.pos_keys[-1].z - mc.pos_keys[0].z)
    motion = metabin_codec.read_metabin(open(out[:-4] + ".paa_metabin", "rb").read()).motion
    fails += report(ok and off < 0.001 and mc.kind == paa_codec.KIND_FLOAT and abs(stored - ground.length) < 0.001
                    and motion is not None and len(motion.pos_keys) == len(mc.pos_keys),
                    f"with travel the roots go {ground.length:.3f} m within {off * 1000:.3f} mm, B_MoveControl_01 "
                    f"exported as kind {mc.kind} going {stored:.3f} m, motion block "
                    f"{'with ' + str(len(motion.pos_keys)) + ' position keys' if motion else 'missing'}; {what}")

    bpy.ops.cd_animator.retarget(face_forward=False, start=10, end=30, speed=0.5, travel=True)
    lap = went("B_MoveControl_01", 30) - went("B_MoveControl_01", 0)
    bpy.ops.cd_animator.make_loop(frames=10)

    def from_root(f):
        scene.frame_set(f)
        body = tw @ target.pose.bones["Bip01 Pelvis"].head - tw @ target.pose.bones["B_MoveControl_01"].head
        return {g: world_rot(target, g) for g in MIXAMO}, body

    (first, first_body), (last, last_body) = from_root(0), from_root(30)
    seam = max(angle(first[g], last[g]) for g in MIXAMO)
    start_off, lap_off = went("B_MoveControl_01", 0).length, (went("B_MoveControl_01", 30) - lap).length
    fails += report(seam < 0.1 and (first_body - last_body).length < 0.001 and start_off < 0.001 and lap_off < 0.001,
                    f"a travelling loop goes {lap.length:.3f} m a round, B_MoveControl_01 {start_off * 1000:.3f} mm "
                    f"from rest on frame 0 and {lap_off * 1000:.3f} mm off the round's travel on frame 30; the body "
                    f"from it {seam:.4f} degrees and {(first_body - last_body).length * 1000:.3f} mm apart")

    bpy.ops.cd_animator.retarget(face_forward=False, travel=True)
    early = from_root(n - 20)
    bpy.ops.cd_animator.end_on_idle(frames=10)
    kept = max(angle(early[0][g], from_root(n - 20)[0][g]) for g in MIXAMO)
    kept_body = (early[1] - from_root(n - 20)[1]).length
    scene.frame_set(n)
    ended = {b.name: world_rot(target, b.name) for b in target.pose.bones}
    ended_body = tw @ target.pose.bones["Bip01 Pelvis"].head - tw @ target.pose.bones["B_MoveControl_01"].head
    out = os.path.join(os.path.dirname(out), "ended.paa")
    bpy.ops.cd_animator.export_paa(filepath=out, clip="ACTION")
    late = [b.name for b in paa_codec.decode_file(open(out, "rb").read())[1].bones
            for keys in (b.rot_keys, b.pos_keys, b.scale_keys) if keys and keys[0].frame > 0]
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = truth
    bpy.ops.cd_animator.game_clip(clip=IDLE, voice=False)
    scene.frame_set(0)
    off = max(angle(ended[b.name], world_rot(truth, b.name)) for b in truth.pose.bones)
    idle_body = (truth.matrix_world @ truth.pose.bones["Bip01 Pelvis"].head
                 - truth.matrix_world @ truth.pose.bones["B_MoveControl_01"].head)
    fails += report(off < 0.1 and (ended_body - idle_body).length < 0.001 and kept < 0.1 and kept_body < 0.001
                    and not late,
                    f"ended on the idle: its first frame's bones within {off:.4f} degrees, the pelvis from "
                    f"B_MoveControl_01 within {(ended_body - idle_body).length * 1000:.3f} mm; frame {n - 20} moved "
                    f"{kept:.4f} degrees and {kept_body * 1000:.3f} mm; tracks starting after frame 0: {late}")
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
