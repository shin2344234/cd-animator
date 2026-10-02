"""Make a hover idle for Broomy from the broom's shipped idle.

    blender -b --factory-startup --python examples/hover_idle.py -- [out folder]

The shipped idle bobs the broom about 7 cm. This adds a slower float of
FLOAT_CM on top, and a side to side roll of ROLL_DEG about the seat a
quarter cycle behind it, so the broom drifts in a slow figure of eight.
Kliff's clip carries the broom's motion itself (his pelvis stays 6 cm above
B_Rider_01 through the whole idle), so the same motion goes onto his Bip01
and he stays in the seat. B_MoveControl_01 and the TL bones are untouched,
the clip keeps its 100 frames, and so both metadata files stay the game's.

Writes both clips with their _lod.paa and .paa_metabin, named as the shipped
idles so they replace them, and hover_idle.blend for a look.
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


def rekey_root(obj, bone_name, to_mount, frames, pivot):
    """Key `bone_name` (a root bone) on every frame so its pose, seen from
    the broom's object space, moves by hover(). to_mount takes the
    armature's space to the broom's."""
    pb = obj.pose.bones[bone_name]
    rest = obj.data.bones[bone_name].matrix_local
    from_mount = to_mount.inverted()
    poses = []
    for f in frames:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        poses.append(pb.matrix_basis.copy())
    action = obj.animation_data.action
    bag = export._channelbag(obj, action)
    for prop in ("rotation_quaternion", "location"):
        for fc in [c for c in bag.fcurves if c.data_path == f'pose.bones["{bone_name}"].{prop}']:
            bag.fcurves.remove(fc)
    prev = None
    for f, basis in zip(frames, poses):
        world = to_mount @ rest @ basis
        moved = hover(f, pivot) @ world
        new_basis = rest.inverted() @ from_mount @ moved
        loc, rot, _scale = new_basis.decompose()
        if prev is not None and prev.dot(rot) < 0:
            rot.negate()
        prev = rot
        pb.location = loc
        pb.rotation_quaternion = rot
        pb.keyframe_insert("location", frame=f)
        pb.keyframe_insert("rotation_quaternion", frame=f)
    for fc in bag.fcurves:
        if fc.data_path.startswith(f'pose.bones["{bone_name}"]'):
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
    kliff_action, _u = anim.import_clip(ctx, kliff, os.path.join(S, KLIFF_CLIP + ".paa"))
    anim.seat_rider(kliff, broom)
    ctx.view_layer.update()

    # Roll about the seat: B_Rider_01's head at frame 0, in broom space.
    ctx.scene.frame_set(0)
    pivot = broom.pose.bones["B_Rider_01"].head.copy()
    frames = list(range(0, FRAMES + 1))
    rekey_root(broom, "Bip01", Matrix.Identity(4), frames, pivot)
    rekey_root(kliff, "Bip01", kliff.matrix_basis.copy(), frames, pivot)
    broom_action.name = BROOM_CLIP + "_hover"
    kliff_action.name = KLIFF_CLIP + "_hover"

    for obj, name in ((broom, BROOM_CLIP), (kliff, KLIFF_CLIP)):
        written, problems = export.export_with_companions(obj, obj.animation_data.action,
                                                          os.path.join(out, name + ".paa"))
        for p in written:
            print(f"wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p)} bytes)")
        for p in problems:
            print("  note:", p)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "hover_idle.blend"))
    sys.stdout.flush()
    os._exit(0)


main()
