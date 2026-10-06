"""Hold Kliff's mouth open while he stands still.

    blender -b --factory-startup --python examples/open_mouth.py -- [--send] [out folder]

Kliff's standing face is two facial clips, f_cd_phm_act_wait_00_0001_kliff
and _0002_kliff. This opens his mouth in both the way the game opens it
when he talks: it finds the frame of one of his spoken lines where his lower
teeth (B_Toothdown_C) are furthest from rest, takes every face bone's pose
at that frame, doubles it, and adds it on top of each wait face, so the
teeth, tongue, lips and chin open together and the wait face's own motion
carries on underneath. Moving only the skin bones below the mouth, as a
first try did, stretches the lower lip while the teeth stay shut, and in
game that reads as swollen lips.

The clips go into the out folder, out/open_mouth by default, as Export
writes them. With --send they go straight into the CD Animator Loader's
folder instead, as Send to game does, and show from the game's next start.
"""

import os
import sys

import bpy
from bpy_extras import anim_utils
from mathutils import Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import anim, export, ingame  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
LINE = "1_pc/1_phm/99_autofacial/english(us)/unique_kliff_aidialogstringinfo_minigame_seotda_win_43299"
WAIT = "1_pc/1_phm/99_facial/00_action/"
CLIPS = ["f_cd_phm_act_wait_00_0001_kliff", "f_cd_phm_act_wait_00_0002_kliff"]
TEETH = "B_Toothdown_C"
SCALE = 2.0   # times the widest mouth of the line


def widest_mouth(arm, face):
    """{bone: (location, rotation)} of the face bones' pose on the frame of
    the active clip where the lower teeth are furthest from rest, scaled."""
    pbs, bones = arm.pose.bones, arm.data.bones
    scene = bpy.context.scene
    rest = (bones["Bip01 Head"].matrix_local.inverted() @ bones[TEETH].matrix_local).translation
    best, best_f = -1.0, 0
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        at = (pbs["Bip01 Head"].matrix.inverted() @ pbs[TEETH].matrix).translation
        if (at - rest).length > best:
            best, best_f = (at - rest).length, f
    scene.frame_set(best_f)
    out = {}
    for n in face:
        axis, angle = pbs[n].rotation_quaternion.to_axis_angle()
        out[n] = (pbs[n].location * SCALE, Quaternion(axis, angle * SCALE))
    print(f"widest mouth on frame {best_f}: lower teeth {best * 1000:.1f} mm from rest, used {SCALE:g} times")
    return out


def add_pose(action, pose):
    """Add `pose` on top of every key of `action`: locations add, rotations
    turn by the pose's rotation. Bones the clip does not key get the pose
    from its first frame to its last."""
    bag = anim_utils.action_get_channelbag_for_slot(action, action.slots[0])
    end = int(action.frame_end)
    for n, (loc, rot) in pose.items():
        base = f'pose.bones["{n}"]'
        if loc.length > 1e-7:
            for i in range(3):
                fc = bag.fcurves.find(base + ".location", index=i)
                if fc is None:
                    fc = anim.new_fcurve(bag, base + ".location", i, n)
                    fc.keyframe_points.insert(0, 0.0)
                    fc.keyframe_points.insert(end, 0.0)
                for p in fc.keyframe_points:
                    p.co[1] += loc[i]
                    p.interpolation = "LINEAR"
                fc.update()
        if rot.angle > 1e-5:
            fcs = [bag.fcurves.find(base + ".rotation_quaternion", index=i) for i in range(4)]
            if any(fc is None for fc in fcs):
                frames, quats = [0, end], [Quaternion(), Quaternion()]
                fcs = [fc or anim.new_fcurve(bag, base + ".rotation_quaternion", i, n)
                       for i, fc in enumerate(fcs)]
                for fc in fcs:
                    fc.keyframe_points.clear()
            else:
                frames = sorted({p.co[0] for fc in fcs for p in fc.keyframe_points})
                quats = [Quaternion([fc.evaluate(f) for fc in fcs]) for f in frames]
                for fc in fcs:
                    fc.keyframe_points.clear()
            turned = [rot @ q for q in quats]
            for i, fc in enumerate(fcs):
                fc.keyframe_points.add(len(frames))
                fc.keyframe_points.foreach_set("co", [x for f, q in zip(frames, turned) for x in (f, q[i])])
                for p in fc.keyframe_points:
                    p.interpolation = "LINEAR"
                fc.update()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    send = "--send" in argv
    rest = [a for a in argv if a != "--send"]
    out = rest[0] if rest else os.path.join(ROOT, "out", "open_mouth")
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE",
                                       clip=LINE, voice=False)
    arm = bpy.context.view_layer.objects.active
    pose = widest_mouth(arm, sorted(anim.face_bones(arm)))
    folder = ingame.folder() if send else out
    os.makedirs(folder, exist_ok=True)
    for clip in CLIPS:
        bpy.context.view_layer.objects.active = arm
        bpy.ops.cd_animator.game_clip(clip=WAIT + clip, voice=False)
        action = arm.animation_data.action
        add_pose(action, pose)
        if send:
            _name, written, _problems = ingame.send(arm, action, folder)
        else:
            written, _problems = export.export_with_companions(arm, action, os.path.join(folder, clip + ".paa"))
        print("wrote", ", ".join(os.path.basename(w) for w in written), "to", folder)
    sys.stdout.flush()
    os._exit(0)


main()
