"""Give Kliff a standing idle under a new name, with his arms raised.

    blender -b --factory-startup --python examples/new_name.py -- [--send] [out folder]

Starts a new clip, cd_phm_cdanim_raised_idle_00, from Kliff's standing idle
cd_phm_basic_00_00_nor_std_idle_00, and turns both upper arms on every frame
so they point up and out. The idle itself is left alone: the new clip plays
only because the charts point Kliff's idle action (key 26107D3C, the upper
chart's default action) at it, node 0 of basic_upper.paac and node 0 of
basic_lower.paac.

The three clip files and the two charts go into the out folder,
out/new_name by default, with a front view render of frame 0. With --send
they go into the CD Animator Loader's folder instead, as Send to game puts
them, and show from the game's next start.
"""

import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import actioncharts, export, ingame, packs  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
NAME = "cd_phm_cdanim_raised_idle_00"
UPPER = actioncharts.CHARTS + "upperaction/1_pc/1_phm/basic_upper.paac"
LOWER = actioncharts.CHARTS + "loweraction/1_pc/1_phm/basic_lower.paac"
PLAYS = [(UPPER, 0), (LOWER, 0)]
ARMS = ("Bip01 L UpperArm", "Bip01 R UpperArm")
OUT = 0.45   # how far out from straight up the arms point


def raise_arms(arm):
    """Turn each upper arm about its shoulder, on every frame, to point up
    and out, and key it there."""
    scene = bpy.context.scene
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        for name in ARMS:
            pb = arm.pose.bones[name]
            m = pb.matrix.copy()
            head = m.translation.copy()
            along = (pb.tail - pb.head).normalized()
            side = 1.0 if head.x > 0 else -1.0
            turn = along.rotation_difference(Vector((side * OUT, 0.0, 1.0)).normalized()).to_matrix().to_4x4()
            new = turn @ Matrix.Translation(-head) @ m
            new.translation = head
            pb.matrix = new
            bpy.context.view_layer.update()
            pb.keyframe_insert("rotation_quaternion", frame=f, group=name)


def render(arm, path):
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    cam = bpy.data.objects.new("front", bpy.data.cameras.new("front"))
    scene.collection.objects.link(cam)
    cam.location = (0.0, -4.2, 1.1)
    cam.rotation_euler = (1.5708, 0.0, 0.0)
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 600, 800
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    send = "--send" in argv
    rest = [a for a in argv if a != "--send"]
    out = rest[0] if rest else os.path.join(ROOT, "out", "new_name")
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE")
    arm = bpy.context.view_layer.objects.active
    bpy.ops.cd_animator.game_new_clip(clip=IDLE, clip_name=NAME, start="MOTION")
    action = arm.animation_data.action
    raise_arms(arm)
    idx = packs.index()
    clip = actioncharts.new_path(action, NAME)
    folder = ingame.folder() if send else out
    os.makedirs(folder, exist_ok=True)
    if send:
        _name, written, _problems = ingame.send(arm, action, folder)
    else:
        written, _problems = export.export_with_companions(arm, action, os.path.join(folder, NAME + ".paa"))
        render(arm, os.path.join(out, "frame0.png"))
    written += actioncharts.send(idx, folder, clip, PLAYS)
    print("wrote", ", ".join(os.path.basename(w) for w in written), "to", folder, "for", clip)
    sys.stdout.flush()
    os._exit(0)


main()
