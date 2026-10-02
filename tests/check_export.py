"""Check the exporter.

    blender -b --factory-startup --python tests/check_export.py -- <samples folder>

1. Every clip, imported and exported without changes, must come out byte for
   byte the same as the file it came from.
2. An edited clip (Kliff's idle with Spine1 turned 20 degrees and a new track
   on a bone the idle never animates) is exported, imported again, and must
   pose every bone where the edited action did, within half float precision.
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
from cd_animator import anim, export  # noqa: E402
from cd_animator.formats import paa_codec  # noqa: E402

RIGS = [("cd_r0032_00_broom.pab", "cd_rd_broom_basic_00_00_"),
        ("phm_01.pab", "cd_phm_rd_broom_basic_00_00_")]


def first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))


def check_unchanged(context, folder, out_dir):
    failures = 0
    for pab, prefix in RIGS:
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.cd_animator.import_pab(filepath=os.path.join(folder, pab))
        obj = context.object
        for clip in sorted(f for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(".paa")):
            src = os.path.join(folder, clip)
            action, _unknown = anim.import_clip(context, obj, src)
            data, problems = export.export_clip(obj, action, os.path.join(out_dir, clip))
            want = open(src, "rb").read()
            same = data == want
            failures += not same
            note = "" if same else f", first difference at byte {first_difference(data, want)} of {len(want)}"
            print(f"  {'ok  ' if same else 'FAIL'} {clip}: {'identical' if same else 'differs'}{note}"
                  + (f" ({'; '.join(problems)})" if problems else ""))
    return failures


def pose_snapshot(obj, frames):
    snap = {}
    for f in frames:
        bpy.context.scene.frame_set(f)
        for pb in obj.pose.bones:
            m = pb.matrix
            snap[(f, pb.name)] = (m.translation.copy(), m @ Vector((0.1, 0, 0)), m @ Vector((0, 0.1, 0)))
    return snap


def check_edited(context, folder, out_dir):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.import_pab(filepath=os.path.join(folder, "phm_01.pab"))
    obj = context.object
    src = os.path.join(folder, "cd_phm_rd_broom_basic_00_00_nor_std_idle_01.paa")
    action, _u = anim.import_clip(context, obj, src)
    bag = export._channelbag(obj, action)

    # Turn Spine1 20 degrees about its local X at every key.
    turn = Quaternion((1, 0, 0), math.radians(20))
    spine = [bag.fcurves.find('pose.bones["Bip01 Spine1"].rotation_quaternion', index=i) for i in range(4)]
    for k in range(len(spine[0].keyframe_points)):
        q = Quaternion([spine[i].keyframe_points[k].co[1] for i in range(4)])
        q = q @ turn
        for i in range(4):
            spine[i].keyframe_points[k].co[1] = q[i]
    for fc in spine:
        fc.update()

    # Key a bone the idle never animates.
    pb = obj.pose.bones["B_Eyeball_L"]
    for f, deg in ((0, 0.0), (50, 25.0), (100, 0.0)):
        pb.rotation_quaternion = Quaternion((0, 0, 1), math.radians(deg))
        pb.keyframe_insert("rotation_quaternion", frame=f)
    pb.rotation_quaternion = (1, 0, 0, 0)

    frames = [0, 13, 50, 77, 100]
    before = pose_snapshot(obj, frames)
    out = os.path.join(out_dir, "edited_idle.paa")
    data, problems = export.export_clip(obj, action, out)
    _c, td = paa_codec.decode_file(data)
    eye = paa_codec.bone_hash("B_Eyeball_L")
    hashes = [b.name_hash for b in td.bones]
    print(f"  edited idle: {len(data)} bytes, {len(td.bones)} tracks; {'; '.join(problems)}")

    anim.import_clip(context, obj, out)
    after = pose_snapshot(obj, frames)
    worst, at = 0.0, None
    for key, pts in before.items():
        err = max((a - b).length for a, b in zip(pts, after[key]))
        if err > worst:
            worst, at = err, key
    failures = 0
    checks = [
        ("re-imported pose matches the edited action within 3 mm", worst < 3e-3, f"max {worst * 1000:.2f} mm at {at}"),
        ("new track is in the file", eye in hashes, ""),
        ("new track sits in section 1", eye in hashes and td.bones[hashes.index(eye)].section == 1
         and hashes.index(eye) < sum(1 for b in td.bones if b.section == 1), ""),
    ]
    for label, ok, detail in checks:
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}{': ' + detail if detail else ''}")
    return failures


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    folder = argv[0] if argv else os.path.join(os.path.dirname(HERE), "samples", "character")
    cd_animator.register()
    context = bpy.context
    out_dir = tempfile.mkdtemp(prefix="cd_animator_export_")
    print("unchanged clips:")
    failures = check_unchanged(context, folder, out_dir)
    print("edited clip:")
    failures += check_edited(context, folder, out_dir)
    print("PASS" if not failures else f"{failures} FAILURES")
    sys.stdout.flush()
    os._exit(0 if not failures else 1)


main()
