"""Make a hover idle for Broomy from the broom's shipped idle.

    blender -b --factory-startup --python examples/hover_idle.py -- [out folder]

The shipped idle bobs the broom on Bip01, its root bone. In game the root
bone's motion moves the broom as a whole, and while Broomy hovers in place
the game throws that away (a 25 degree roll and a 12 cm float on Bip01 both
showed nothing). B_Body_00, the bone under it, does show, and Kliff sits on
B_Rider_01 under that, so he goes with it (a 40 cm probe on 2 October 2026).

So this adds a slow float of FLOAT_CM to B_Body_00, with a side to side roll
of ROLL_DEG about the seat a quarter cycle behind it and a small pitch, so
the broom drifts in a slow figure of eight. Kliff's clip stays the game's.
Bip01, B_MoveControl_01 and the TL bones are untouched, the clip keeps its
100 frames, and so its metadata stays the game's.

Writes the broom's clip with its _lod.paa and .paa_metabin, named as the
shipped idle so it replaces it, and hover_idle.blend for a look.
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

FLOAT_CM = 12.0     # extra rise and fall, each way
ROLL_DEG = 6.0      # side to side roll, each way
PITCH_DEG = 2.0     # nose up and down, in step with the float
FRAMES = 100        # the shipped idle's length; one full cycle

S = os.path.join(ROOT, "samples", "character")
BROOM_CLIP = "cd_rd_broom_basic_00_00_nor_std_idle_01"
KLIFF_CLIP = "cd_phm_rd_broom_basic_00_00_nor_std_idle_01"


def hover(frame, pivot):
    """The extra motion at `frame`, in the broom's object space (Blender
    axes: Z up, the broom flies along -Y)."""
    phase = 2.0 * math.pi * frame / FRAMES
    rise = Matrix.Translation((0.0, 0.0, FLOAT_CM / 100.0 * math.sin(phase)))
    roll = Matrix.Rotation(math.radians(ROLL_DEG) * math.sin(phase - math.pi / 2), 4, "Y")
    pitch = Matrix.Rotation(math.radians(PITCH_DEG) * math.cos(phase), 4, "X")
    about = Matrix.Translation(pivot) @ roll @ pitch @ Matrix.Translation(-pivot)
    return rise @ about


def rekey_body(obj, frames, pivot):
    """Key B_Body_00 on every frame so its pose, in the armature's space,
    moves by hover(). Bip01 above it keeps its own keys."""
    pb = obj.pose.bones["B_Body_00"]
    bases = []
    for f in frames:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        pb.matrix = hover(f, pivot) @ pb.matrix
        bpy.context.view_layer.update()
        bases.append(pb.matrix_basis.copy())
    action = obj.animation_data.action
    bag = export._channelbag(obj, action)
    prefix = 'pose.bones["B_Body_00"]'
    for fc in [c for c in bag.fcurves if c.data_path.startswith(prefix)]:
        bag.fcurves.remove(fc)
    prev = None
    for f, basis in zip(frames, bases):
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
    out = argv[0] if argv else os.path.join(ROOT, "out", "hover_idle")
    os.makedirs(out, exist_ok=True)
    cd_animator.register()
    ctx = bpy.context
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "cd_r0032_00_broom.pab"))
    broom = ctx.object
    broom_action, _u = anim.import_clip(ctx, broom, os.path.join(S, BROOM_CLIP + ".paa"))
    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "phm_01.pab"))
    kliff = ctx.object
    anim.import_clip(ctx, kliff, os.path.join(S, KLIFF_CLIP + ".paa"))
    anim.seat_rider(kliff, broom)
    ctx.view_layer.update()

    # Roll about the seat: B_Rider_01's head at frame 0, in broom space.
    ctx.scene.frame_set(0)
    pivot = broom.pose.bones["B_Rider_01"].head.copy()
    rekey_body(broom, list(range(0, FRAMES + 1)), pivot)
    broom_action.name = BROOM_CLIP + "_hover"

    written, problems = export.export_with_companions(broom, broom_action, os.path.join(out, BROOM_CLIP + ".paa"))
    for p in written:
        print(f"wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p)} bytes)")
    for p in problems:
        print("  note:", p)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "hover_idle.blend"))
    sys.stdout.flush()
    os._exit(0)


main()
