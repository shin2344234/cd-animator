"""Make a level takeoff for Broomy from the broom's 75 degree climb.

    blender -b --factory-startup --python examples/level_takeoff.py -- [out folder]

Broomy used to play the climb (walkfast_f_75u) for the Wyvern's takeoff. It
tips the broom about 60 degrees past the idle while B_Rider_01 keeps Kliff
upright, and flight then swung the broom back level under him. Playing the
idle there instead left a smaller jump, because the takeoff ended partway
through the idle's 20 cm bob and flight started the idle from frame 0.

This clip holds every bone on the idle's frame 0 for the climb's 60 frames,
so flight starts from the pose the takeoff ends in. Bip01 keeps the climb's
rise and forward drift on top of the idle's frame 0 position, and
B_MoveControl_01 keeps the climb's keys. Broomy keeps the Wyvern's metadata
for the takeoff, so the .paa_metabin written here is not used.

Writes cd_rd_broom_basic_00_00_nor_std_takeoff_00.paa and its _lod.paa and
.paa_metabin, a name no shipped file has.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import anim, export  # noqa: E402

S = os.path.join(ROOT, "samples", "character")
IDLE = "cd_rd_broom_basic_00_00_nor_std_idle_01"
CLIMB = "cd_rd_broom_basic_00_00_nor_move_walkfast_f_75u_ing_00"
OUT_NAME = "cd_rd_broom_basic_00_00_nor_std_takeoff_00"
KEEP = ("B_MoveControl_01", "B_TL_Position_01", "B_TL_Position_02")


def poses(obj, action, frames):
    """Each bone's basis at each frame of `action`."""
    obj.animation_data.action = action
    out = []
    for f in frames:
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        out.append({pb.name: pb.matrix_basis.copy() for pb in obj.pose.bones})
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.join(ROOT, "out", "level_takeoff")
    os.makedirs(out, exist_ok=True)
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "cd_r0032_00_broom.pab"))
    broom = bpy.context.object
    idle, _u = anim.import_clip(bpy.context, broom, os.path.join(S, IDLE + ".paa"))
    climb, _u = anim.import_clip(bpy.context, broom, os.path.join(S, CLIMB + ".paa"))
    last = round(climb["cd_duration"] * anim.FPS)
    frames = list(range(0, last + 1))

    rest = poses(broom, idle, [0])[0]
    climb_poses = poses(broom, climb, frames)
    broom.animation_data.action = climb
    bag = export._channelbag(broom, climb)
    for pb in broom.pose.bones:
        if pb.name in KEEP:
            continue
        prefix = f'pose.bones["{pb.name}"]'
        for fc in [c for c in bag.fcurves if c.data_path.startswith(prefix)]:
            bag.fcurves.remove(fc)
        loc0, rot0, _s = rest[pb.name].decompose()
        keys = frames if pb.name == "Bip01" else [0, last]
        start = climb_poses[0][pb.name].translation
        for f in keys:
            # Bip01 carries the climb's rise; every other bone holds still.
            pb.location = loc0 + (climb_poses[f][pb.name].translation - start) if pb.name == "Bip01" else loc0
            pb.rotation_quaternion = rot0
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_quaternion", frame=f)
        for fc in bag.fcurves:
            if fc.data_path.startswith(prefix):
                for p in fc.keyframe_points:
                    p.interpolation = "LINEAR"
    climb.name = OUT_NAME

    written, problems = export.export_with_companions(broom, climb, os.path.join(out, OUT_NAME + ".paa"))
    for p in written:
        print(f"wrote {os.path.relpath(p, ROOT)} ({os.path.getsize(p)} bytes)")
    for p in problems:
        print("  note:", p)
    sys.stdout.flush()
    os._exit(0)


main()
