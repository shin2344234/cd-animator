"""Give Kliff a new move: press L while standing and he waves.

    blender -b --factory-startup --python examples/new_move.py -- [--send] [out folder]

It makes cd_phm_cdanim_wave_00, a new clip: his standing idle with the
right arm out to the side, the forearm up and rocking side to side with the
palm forward, two seconds. Then it does what Play on a key and Send to game
do in the panel: basic_upper.paac and basic_lower.paac each get a move that
plays the clip on L, and ui/inputmap.xml gets the key (actioncharts.py says
how). Into out/new_move by_path by default; with --send into the loader's
folder.
"""

import math
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
IDLE_CLIP = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
NAME = "cd_phm_cdanim_wave_00"
FRAMES = 60


def aim(arm, name, goal):
    """Turn bone `name` about its head so it points along `goal` (world)."""
    pb = arm.pose.bones[name]
    m = pb.matrix.copy()
    head = m.translation.copy()
    turn = (pb.tail - pb.head).normalized().rotation_difference(goal.normalized()).to_matrix().to_4x4()
    new = turn @ Matrix.Translation(-head) @ m
    new.translation = head
    pb.matrix = new
    bpy.context.view_layer.update()


def palm(arm):
    """The right palm's facing (world): pinky to index, crossed with hand to
    fingers. On the idle it points in at the thigh."""
    pb = arm.pose.bones
    w = arm.matrix_world
    across = w @ pb["Bip01 R Finger1"].head - w @ pb["Bip01 R Finger4"].head
    along = w @ pb["Bip01 R Finger2"].head - w @ pb["Bip01 R Hand"].head
    return across.cross(along).normalized()


def roll(arm, name, facing, goal, amount):
    """Turn bone `name` about its own length by `amount` of the angle that
    brings `facing` round to `goal`, both seen across the bone."""
    pb = arm.pose.bones[name]
    axis = (pb.tail - pb.head).normalized()
    a = facing - axis * facing.dot(axis)
    b = goal - axis * goal.dot(axis)
    if a.length < 1e-6 or b.length < 1e-6:
        return
    angle = math.atan2(axis.dot(a.cross(b)), a.dot(b)) * amount
    m = pb.matrix.copy()
    head = m.translation.copy()
    new = Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-head) @ m
    new.translation = head
    pb.matrix = new
    bpy.context.view_layer.update()


def wave(arm):
    """A wave with the right hand: the upper arm out to the side and a little
    above the shoulder, the elbow bent so the forearm stands up, and the
    forearm rocking side to side two and a half times, eased in and out."""
    scene = bpy.context.scene
    up_name, fore_name = "Bip01 R UpperArm", "Bip01 R Forearm"
    side = -1.0 if arm.data.bones[up_name].head_local.x < 0 else 1.0
    for f in range(FRAMES + 1):
        scene.frame_set(f)
        ease = max(0.0, min(1.0, f / 10, (FRAMES - f) / 10))
        ease = ease * ease * (3 - 2 * ease)
        up, fore = arm.pose.bones[up_name], arm.pose.bones[fore_name]
        rest_up = (up.tail - up.head).normalized()
        aim(arm, up_name, rest_up.lerp(Vector((side * 0.8, -0.15, 0.45)).normalized(), ease))
        rest_fore = (fore.tail - fore.head).normalized()
        sway = math.sin(f / FRAMES * 5 * math.pi)
        aim(arm, fore_name, rest_fore.lerp(Vector((side * (0.1 + 0.45 * sway), -0.2, 1.0)).normalized(), ease))
        # The palm forward, to whoever is in front of him; the arm alone
        # leaves it wherever the shortest turn put it.
        forward = (arm.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
        roll(arm, fore_name, palm(arm), forward, ease)
        up.keyframe_insert("rotation_quaternion", frame=f)
        fore.keyframe_insert("rotation_quaternion", frame=f)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    send = "--send" in argv
    rest = [a for a in argv if a != "--send"]
    out = rest[0] if rest else os.path.join(ROOT, "out", "new_move")
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE")
    arm = bpy.context.view_layer.objects.active
    bpy.ops.cd_animator.game_new_clip(clip=IDLE_CLIP, clip_name=NAME, frames=FRAMES, start="MOTION")
    action = arm.animation_data.action
    wave(arm)
    bpy.ops.cd_animator.play_on_key(key="l")
    if send:
        bpy.ops.cd_animator.send_to_game(clip="ACTION")
        folder = ingame.folder()
    else:
        folder = out
        os.makedirs(folder, exist_ok=True)
        export.export_with_companions(arm, action, os.path.join(folder, NAME + ".paa"))
        actioncharts.send_move(packs.index(), folder, actioncharts.new_path(action, NAME), "l")
    print("wrote", ", ".join(sorted(os.path.relpath(os.path.join(d, f), folder) for d, _s, fs in os.walk(folder)
                                    for f in fs)), "to", folder)
    sys.stdout.flush()
    os._exit(0)


main()
