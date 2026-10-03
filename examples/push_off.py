"""Make Kliff's push-off for Broomy's takeoff.

    blender -b --factory-startup --python examples/push_off.py -- [out folder] [clip name]

Seated on the broom idle, Kliff's toes hang about 65 cm above the ground and
his legs cannot reach it, while the takeoff lifts the broom 45 cm in its
first 5 frames. So the push-off is a kick: the knees come up a little for 4
frames, both legs drive down and back with the toes pointed until frame 10,
and they swing back to the seated pose by frame 30.

The clip starts as a new clip holding the first frame of Kliff's broom idle
(cd_phm_rd_broom_basic_00_00_nor_std_idle_01) for 36 frames, so it starts
and ends on the pose the idle starts on. Each leg is an IK chain from the
calf to an animated empty; the feet and the spine are keyed. Export bakes the
IK into keys.

The clip name defaults to cd_phm_rd_wyvern_basic_00_00_air_move_fall_walk_end_00,
the clip of FDA30B13, the spare action in Kliff's lower chart that the
Broomy test build plays at takeoff. Writes the .paa, _lod.paa and
.paa_metabin into out/push_off.
"""

import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import clip, export  # noqa: E402

S = os.path.join(ROOT, "samples", "character")
TEMPLATE = "cd_phm_rd_broom_basic_00_00_nor_std_idle_01"
NAME = "cd_phm_rd_wyvern_basic_00_00_air_move_fall_walk_end_00"
FRAMES = 36

# Offsets from the seated pose in Kliff's space (metres; -Y is forward, Z up).
# (frame, foot target offset, toe point in degrees, spine lean in degrees)
LEGS = [
    (0, (0.0, 0.0, 0.0), 0, 0),
    (4, (0.0, -0.05, 0.08), -10, 6),
    (10, (0.0, 0.16, -0.30), 35, -4),
    (14, (0.0, 0.18, -0.28), 30, -3),
    (30, (0.0, 0.0, 0.0), 0, 0),
    (FRAMES, (0.0, 0.0, 0.0), 0, 0),
]
SIDES = ("L", "R")
LATERAL = Vector((1.0, 0.0, 0.0))


def local_axis(pb, world_axis):
    """`world_axis` in the bone's local space at the current pose, so a
    rotation about it turns the bone about that armature axis."""
    m = pb.matrix.to_3x3() @ pb.matrix_basis.to_3x3().inverted()
    return (m.inverted() @ world_axis).normalized()


def key_turn(pb, axis, base, degrees, frame):
    pb.rotation_quaternion = Quaternion(axis, math.radians(degrees)) @ base
    pb.keyframe_insert("rotation_quaternion", frame=frame)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.join(ROOT, "out", "push_off")
    name = argv[1] if len(argv) > 1 else NAME
    os.makedirs(out, exist_ok=True)
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "phm_01.pab"))
    kliff = bpy.context.object
    action = clip.new_clip(bpy.context, kliff, os.path.join(S, TEMPLATE + ".paa"), name, FRAMES, hold=True)
    scene = bpy.context.scene
    scene.frame_set(0)
    bpy.context.view_layer.update()

    pose = kliff.pose.bones
    feet = {s: pose[f"Bip01 {s} Foot"] for s in SIDES}
    spine = pose["Bip01 Spine"]
    turns = {pb.name: (pb, local_axis(pb, LATERAL), pb.rotation_quaternion.copy())
             for pb in list(feet.values()) + [spine]}
    # Point the toes the way that moves them back (+Y), whichever way the
    # foot's local axis happens to face.
    toe_sign = {}
    for s, pb in feet.items():
        pb_, axis, base = turns[pb.name]
        before = (pb.matrix @ Vector((0.0, pb.length, 0.0))).y
        pb.rotation_quaternion = Quaternion(axis, math.radians(20)) @ base
        bpy.context.view_layer.update()
        toe_sign[s] = 1 if (pb.matrix @ Vector((0.0, pb.length, 0.0))).y > before else -1
        pb.rotation_quaternion = base
    bpy.context.view_layer.update()

    for s in SIDES:
        calf = pose[f"Bip01 {s} Calf"]
        start = kliff.matrix_world @ calf.tail
        target = bpy.data.objects.new(f"foot target {s}", None)
        scene.collection.objects.link(target)
        for frame, off, _toe, _lean in LEGS:
            target.location = start + Vector(off)
            target.keyframe_insert("location", frame=frame)
        ik = calf.constraints.new("IK")
        ik.target, ik.chain_count = target, 2

    for frame, _off, toe, lean in LEGS:
        for s, pb in feet.items():
            _pb, axis, base = turns[pb.name]
            key_turn(pb, axis, base, toe * toe_sign[s], frame)
        _pb, axis, base = turns[spine.name]
        key_turn(spine, axis, base, lean, frame)

    written, problems = export.export_with_companions(kliff, action, os.path.join(out, name + ".paa"))
    for p in problems:
        print("  " + p)
    for path in written:
        print("wrote", path)
    sys.stdout.flush()
    os._exit(0)


main()
