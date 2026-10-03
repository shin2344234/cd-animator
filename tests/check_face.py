"""Check facial clips: a face clip over a body clip, and its export.

    blender -b --factory-startup --python tests/check_face.py -- [game folder]

Needs the game installed. It requires:

  * every facial clip family to key only face bones, B_face_com and the
    bones under it, and the facial clip search for Kliff to list only them;
  * Kliff built with a run and the angry face to keep the run as the
    active action and put the face on the CD face track, the face bones to
    move with it, and every body bone to pose exactly as with the run alone;
  * the face clip imported first and the run second to end the same way;
  * both clips to export byte for byte as the game's files;
  * Remove facial clip to put the face back on its rest pose;
  * a southern bandit's swaying beard, speaking a line, to keep its springs
    on the moving chin bone and inside their 45 degree cone.

Exit code 0 means every check passed.
"""

import math
import os
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import anim, export, packs  # noqa: E402
from cd_animator.formats import paa_codec, paz  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
RUN = "1_pc/1_phm/cd_phm_basic_00_00_nor_move_run_f_ing_00"
FACE = "1_pc/1_phm/99_facial/99_emotion/f_cd_phm_emo_anger_00_0001_kliff"
LINE = "1_pc/1_phm/99_autofacial/english(us)/ndm_adult_1_deerking_boss_3100_npc_00_00001"
FAMILIES = (FACE, "1_pc/1_phm/99_facial/00_action/f_cd_phm_act_anger_00_0001", LINE,
            "1_pc/1_phm/99_arfacial/f_cd_boss_caliburn_9000_boss_caliburn_20250625114033")
BANDIT = "2_mon/cd_m0001_00_twofeet/cd_m0001_00_phm_south/cd_m0001_00_phm_south_23002"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_families(idx):
    bpy.ops.cd_animator.game_skeleton(skeleton="1_pc/1_phm/phm_01")
    arm = bpy.context.view_layer.objects.active
    face = {paa_codec.bone_hash(n) for n in anim.face_bones(arm)}
    counts = []
    for clip in FAMILIES:
        _c, td = paa_codec.decode_file(paz.read(idx.by_path[packs.MOTION + clip + ".paa"]))
        counts.append((len(td.bones), sum(1 for b in td.bones if b.name_hash in face)))
    listed = cd_animator.facial_clips(idx, "character/model/1_pc/1_phm/phm_01")
    odd = [c for c in listed if "facial" not in c]
    bpy.data.objects.remove(arm)
    return report(all(n == f for n, f in counts) and len(listed) > 100000 and not odd,
                  f"facial clips key only face bones {counts}; the search lists {len(listed)} for Kliff, "
                  f"{len(odd)} of them outside a facial folder")


def world(arm, names):
    return {n: (arm.matrix_world @ arm.pose.bones[n].matrix).copy() for n in names}


def on_head(arm, names):
    head = arm.pose.bones["Bip01 Head"].matrix.inverted()
    return {n: head @ arm.pose.bones[n].matrix for n in names}


def off(a, b):
    return max(((a[n].translation - b[n].translation).length for n in a), default=0.0) * 1000


def check_kliff(idx):
    fails = 0
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE",
                                       clip=RUN)
    arm = bpy.context.view_layer.objects.active
    face = sorted(anim.face_bones(arm))
    body = [b.name for b in arm.data.bones if b.name not in face and b.get("cd_index") is not None]
    scene = bpy.context.scene
    frames = (10, 30, 47)
    alone = {}
    for f in frames:
        scene.frame_set(f)
        alone[f] = world(arm, body)
    rest_face = on_head(arm, face)

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=FACE)
    ad = arm.animation_data
    face_action = anim.face_action(arm)
    moved = drift = 0.0
    for f in frames:
        scene.frame_set(f)
        moved = max(moved, off(on_head(arm, face), rest_face))
        drift = max(drift, off(world(arm, body), alone[f]))
    fails += report(ad.action.name.startswith("cd_phm_basic_00_00_nor_move_run_f_ing_00") and face_action is not None
                    and face_action.name.endswith("anger_00_0001_kliff") and face_action.get("cd_face")
                    and moved > 2.0 and drift < 0.001 and scene.frame_end == int(face_action.frame_end),
                    f"run active, {face_action.name if face_action else None} on the face: face bones up to "
                    f"{moved:.1f} mm off rest, body bones {drift:.4f} mm off the run alone, "
                    f"scene to frame {scene.frame_end}")

    out = tempfile.mkdtemp(prefix="cd_face_")
    same = []
    for action, clip in ((ad.action, RUN), (face_action, FACE)):
        data, _problems = export.export_clip(arm, action, os.path.join(out, action.name + ".paa"))
        same.append(data == paz.read(idx.by_path[packs.MOTION + clip + ".paa"]))
    fails += report(all(same), f"export byte for byte: run {same[0]}, face {same[1]}")

    bpy.ops.cd_animator.remove_face()
    scene.frame_set(30)
    back = off(on_head(arm, face), rest_face)
    fails += report(anim.face_action(arm) is None and back < 0.01,
                    f"Remove facial clip: face {back:.4f} mm off rest at frame 30")

    # The other order: the face first, then the body clip.
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE",
                                       clip=FACE)
    arm2 = bpy.context.view_layer.objects.active
    first = arm2.animation_data.action.name
    bpy.ops.cd_animator.game_clip(clip=RUN)
    face2 = anim.face_action(arm2)
    fails += report(first.startswith("f_cd_phm_emo_anger_00_0001_kliff")
                    and arm2.animation_data.action.name.startswith("cd_phm_basic_00_00_nor_move_run_f_ing_00")
                    and face2 is not None and face2.name == first,
                    f"face first: active {first}, then the run moves it to the face layer "
                    f"({face2.name if face2 else None})")
    return fails


def check_beard():
    bpy.ops.cd_animator.game_character(character=BANDIT, textures=False, cloth=False, clip=LINE)
    arm = bpy.context.view_layer.objects.active
    beard = next(o for o in arm.children if "_beard_" in o.get("cd_pac", ""))
    springs = [b.name for b in arm.data.bones if b.get("cd_stiffness") and b.get("cd_extra") == beard["cd_pac"]]
    if not springs:
        return report(False, f"{beard.name}: no sway bones")
    chin = arm.data.bones[springs[0]].parent.name
    pbs = arm.pose.bones
    scene = bpy.context.scene
    moved = slip = turn = 0.0
    for f in range(0, scene.frame_end + 1, 2):
        scene.frame_set(f)
        moved = max(moved, (pbs[chin].matrix.translation - arm.data.bones[chin].matrix_local.translation).length)
        for n in springs:
            carried = pbs[chin].matrix @ arm.data.bones[chin].matrix_local.inverted() @ arm.data.bones[n].matrix_local
            slip = max(slip, (pbs[n].matrix.translation - carried.translation).length)
            a = math.degrees(pbs[n].rotation_quaternion.angle)
            turn = max(turn, min(a, 360.0 - a))
    return report(chin in anim.face_bones(arm) and moved > 0.001 and slip < 1e-5 and turn < 45.0,
                  f"{beard.name} speaking: its springs hang on {chin}, which moves up to {moved * 1000:.1f} mm; "
                  f"their roots stay on it ({slip * 1000:.4f} mm), turning at most {turn:.1f} degrees")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_families(idx)
    fails += check_kliff(idx)
    fails += check_beard()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
