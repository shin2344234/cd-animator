"""Check that export bakes constraints, IK, drivers and Euler rotation.

    blender -b --factory-startup --python tests/check_bake.py -- <samples folder>

On Kliff's standing idle it sets up an IK chain from the right forearm to a
moving empty, a head that copies an animated empty's rotation, a spine keyed
in Euler angles, and a driver raising the left clavicle over time. It
exports with baking, imports the result onto a second Kliff with none of
that, and requires every bone's head and tail to match the first Kliff's
within 3 mm on a set of frames. It also requires the setup to move the hand
by more than 10 cm, so a bake that changes nothing cannot pass, and an
export without baking to leave the IK out.
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
from cd_animator import anim, export  # noqa: E402

IDLE = "cd_phm_basic_00_00_nor_std_idle_00"
FRAMES = (0, 1, 7, 30, 61, 120, 199, 240)
LIMIT = 0.003


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    return not ok


def kliff(folder, name):
    bpy.ops.cd_animator.import_pab(filepath=os.path.join(folder, "phm_01.pab"))
    obj = bpy.context.object
    obj.name = name
    return obj


def empty(name, keys):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    for frame, loc, rot in keys:
        e.location, e.rotation_euler = loc, rot
        e.keyframe_insert("location", frame=frame)
        e.keyframe_insert("rotation_euler", frame=frame)
    return e


def rig_up(obj):
    w = obj.matrix_world
    hand = obj.pose.bones["Bip01 R Hand"]
    bpy.context.scene.frame_set(0)
    start = w @ hand.head
    reach = empty("reach", [(0, start + Vector((0.15, -0.25, 0.30)), (0, 0, 0)),
                            (120, start + Vector((-0.10, -0.35, 0.45)), (0, 0, 0)),
                            (240, start + Vector((0.15, -0.25, 0.30)), (0, 0, 0))])
    ik = obj.pose.bones["Bip01 R Forearm"].constraints.new("IK")
    ik.target, ik.chain_count = reach, 2

    look = empty("look", [(0, (0, 0, 0), (0, 0, 0)), (90, (0, 0, 0), (0.0, 0.4, 0.6)),
                          (240, (0, 0, 0), (0, 0, 0))])
    cr = obj.pose.bones["Bip01 Head"].constraints.new("COPY_ROTATION")
    cr.target, cr.mix_mode, cr.target_space, cr.owner_space = look, "ADD", "LOCAL", "LOCAL"

    spine = obj.pose.bones["Bip01 Spine1"]
    spine.rotation_mode = "XYZ"
    for frame, x in ((0, 0.0), (100, math.radians(25)), (240, 0.0)):
        spine.rotation_euler = (x, 0.0, 0.0)
        spine.keyframe_insert("rotation_euler", frame=frame)

    d = obj.pose.bones["Bip01 L Clavicle"].driver_add("location", 1).driver
    d.type, d.expression = "SCRIPTED", "frame / 4000"
    return reach


def poses(obj):
    out = {}
    for f in FRAMES:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        w = obj.matrix_world
        out[f] = {pb.name: (w @ pb.head, w @ pb.tail) for pb in obj.pose.bones}
    return out


def worst(a, b):
    err, where = 0.0, None
    for f in a:
        for n, (h, t) in a[f].items():
            e = max((h - b[f][n][0]).length, (t - b[f][n][1]).length)
            if e > err:
                err, where = e, (f, n)
    return err, where


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    folder = argv[0] if argv else os.path.join(os.path.dirname(HERE), "samples", "character")
    cd_animator.register()
    out = tempfile.mkdtemp(prefix="cd_bake_")
    src = os.path.join(folder, IDLE + ".paa")
    fails = 0

    plain = kliff(folder, "plain")
    anim.import_clip(bpy.context, plain, src)
    shipped = poses(plain)
    bpy.data.objects.remove(plain)

    rigged = kliff(folder, "rigged")
    action = anim.import_clip(bpy.context, rigged, src)[0]
    rig_up(rigged)
    want = poses(rigged)
    moved = worst(want, shipped)[0]
    fails += report(moved > 0.10, f"the setup moves bones by up to {moved * 100:.1f} cm")

    path = os.path.join(out, "baked.paa")
    bpy.context.scene.frame_set(17)
    written, problems = export.export_with_companions(rigged, action, path)
    fails += report(bpy.context.scene.frame_current == 17, "the scene is back on frame 17 after baking")
    print("   ", next(p for p in problems if p.startswith("baked")))
    export.export_clip(rigged, action, os.path.join(out, "unbaked.paa"), bake=False)
    after = poses(rigged)
    fails += report(worst(after, want)[0] == 0.0, "the rigged Kliff's pose is unchanged by the export")

    for label, clip, should in (("baked", written[0], True), ("unbaked", os.path.join(out, "unbaked.paa"), False)):
        check = kliff(folder, "check_" + label)
        anim.import_clip(bpy.context, check, clip)
        err, where = worst(want, poses(check))
        if should:
            fails += report(err < LIMIT, f"baked clip matches the rigged pose within {err * 1000:.2f} mm (worst {where})")
        else:
            fails += report(err > 0.10, f"without baking the clip misses the rig by {err * 100:.1f} cm (worst {where})")
        bpy.data.objects.remove(check)

    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
