"""Raise Kliff's right arm in his standing idles and the desert fidget.

    blender -b --factory-startup --python examples/raise_arm.py -- [out folder] [clip ...]

The first test of CD Animator Loader (loader/README.md): the right upper arm
turns 150 degrees out to the side and up, about the shoulder, on top of
whatever each clip already does, so the hand rises from about 1.0 m to
about 2.0 m. The forearm and hand keep their own keys, so in the desert
fidget the raised arm still moves the way the original arm moves.

Kliff's standing idles and the desert fidget are the clips named below; any
other clip of Kliff's can be named after the out folder. Drop the three files
each writes into bin64\\CDAnimator and start the game.
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

S = os.path.join(ROOT, "samples", "character")
CLIPS = ["cd_phm_basic_00_00_nor_std_idle_00",
         "cd_phm_basic_00_00_nor_std_idle_01",
         "cd_kliff_basic_00_00_nor_so_std_idle_desert_stt_00",
         "cd_kliff_basic_00_00_nor_so_std_idle_desert_ing_00",
         "cd_kliff_basic_00_00_nor_so_std_idle_desert_end_00"]
BONE = "Bip01 R UpperArm"
RAISE_DEG = 150.0   # about the armature's Y axis, which takes the right arm out and up


def raise_arm(kliff, action):
    """Rekey BONE on every frame of `action`, turned RAISE_DEG about its own
    head in the armature's space."""
    pb = kliff.pose.bones[BONE]
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
    bag = export._channelbag(kliff, action)
    prefix = f'pose.bones["{BONE}"]'
    for fc in [c for c in bag.fcurves if c.data_path.startswith(prefix)]:
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
    out = argv[0] if argv else os.path.join(ROOT, "out", "raise_arm")
    clips = argv[1:] or CLIPS
    os.makedirs(out, exist_ok=True)
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "phm_01.pab"))
    kliff = bpy.context.object
    hand = kliff.pose.bones["Bip01 R Hand"]

    for clip in clips:
        action, _u = anim.import_clip(bpy.context, kliff, os.path.join(S, clip + ".paa"))
        bpy.context.scene.frame_set(0)
        before = hand.head.z
        raise_arm(kliff, action)
        bpy.context.scene.frame_set(0)
        bpy.context.view_layer.update()
        print(f"{clip}: right hand at frame 0 from {before:.2f} m to {hand.head.z:.2f} m")
        written, problems = export.export_with_companions(kliff, action, os.path.join(out, clip + ".paa"))
        for p in written:
            print(f"  wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p)} bytes)")
        for p in problems:
            print("  note:", p)
    sys.stdout.flush()
    os._exit(0)


main()
