"""Raise the Wyvern's left wing in its idles, the first test of 0.7.0 in game.

    blender -b --factory-startup --python examples/bend_wing.py -- [out folder]

Needs the game installed: the skeleton and clips come from the packs. The
left upper arm, the root of the wing, turns 60 degrees up about the
shoulder on top of whatever each clip already does, so the left wing stands
up while the right one keeps the shipped pose. The rest of the wing keeps
its own keys and still moves the way it did.

The three clips are the Wyvern's ground idle, the idle it hovers in, and its
air idle. Drop the files written into bin64\\CDAnimator and summon the
Wyvern. The loader serves files by name, so the copies of these clips in
2_mon/m0004_00_dragon/m0004_00_wyvern get the edited ones too.
"""

import math
import os
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import anim, export  # noqa: E402

SKELETON = "character/model/2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/cd_m0004_00_wyvern"
FOLDER = "2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/00_mon/"
CLIPS = ["cd_rd_wyvern_basic_00_00_nor_std_idle_00",
         "cd_rd_wyvern_basic_00_00_nor_std_fly_idle_00",
         "cd_rd_wyvern_basic_00_00_air_std_idle_00"]
BONE = "Bip01 L UpperArm"
TIP = "Bip01 L Hand"
RAISE_DEG = -60.0   # about the armature's Y axis, which lifts the left (+X) side


def raise_wing(rig, action):
    """Rekey BONE on every frame of `action`, turned RAISE_DEG about its own
    head in the armature's space."""
    pb = rig.pose.bones[BONE]
    last = round(action["cd_duration"] * anim.FPS)
    turn = Matrix.Rotation(math.radians(RAISE_DEG), 4, "Y")
    bases = []
    for f in range(last + 1):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        m = pb.matrix.copy()
        head = Matrix.Translation(m.translation)
        pb.matrix = head @ turn @ head.inverted() @ m
        bpy.context.view_layer.update()
        bases.append(pb.matrix_basis.copy())
    bag = export._channelbag(rig, action)
    prefix = f'pose.bones["{BONE}"]'
    for fc in [c for c in bag.fcurves if c.data_path.startswith(prefix) and not c.data_path.endswith(".scale")]:
        bag.fcurves.remove(fc)
    prev = None
    for f, basis in enumerate(bases):
        loc, rot, _scale = basis.decompose()
        if prev is not None and prev.dot(rot) < 0:
            rot.negate()
        prev = rot
        pb.location = loc
        pb.rotation_quaternion = rot
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion", frame=f)
    for fc in bag.fcurves:
        if fc.data_path.startswith(prefix):
            for p in fc.keyframe_points:
                p.interpolation = "LINEAR"


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.join(ROOT, "out", "bend_wing")
    os.makedirs(out, exist_ok=True)
    cd_animator.register()
    for h in list(bpy.app.handlers.frame_change_pre):
        bpy.app.handlers.frame_change_pre.remove(h)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.game_skeleton(skeleton=SKELETON)
    rig = bpy.context.object
    tip = rig.pose.bones[TIP]

    for clip in CLIPS:
        bpy.ops.cd_animator.game_clip(clip=FOLDER + clip)
        action = rig.animation_data.action
        bpy.context.scene.frame_set(0)
        before = tip.head.z
        raise_wing(rig, action)
        bpy.context.scene.frame_set(0)
        bpy.context.view_layer.update()
        print(f"{clip}: left wing tip at frame 0 from {before:.2f} m to {tip.head.z:.2f} m up")
        written, problems = export.export_with_companions(rig, action, os.path.join(out, clip + ".paa"))
        for p in written:
            print(f"  wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p)} bytes)")
        for p in problems:
            print("  note:", p)
    sys.stdout.flush()
    os._exit(0)


main()
