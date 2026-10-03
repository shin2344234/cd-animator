"""Check hair and beard sway: the values, the sway bones and their springs.

    blender -b --factory-startup --python tests/check_sway.py -- [game folder]

Needs the game installed. It requires:

  * Kliff's hair to have 24,607 of its vertices below 63 and none at 0, so
    that it sways and is not cloth;
  * Damian built with no clip to get sway bones on Bip01 Head, a bone
    under it, or the neck or upper back the long hair rests on, at rest,
    with every hair vertex's sway weights adding up to 1 - value / 63 and
    no weight on a root at 63;
  * with a run playing, the sway bones to start at rest on the first frame,
    swing more than 5 degrees and less than 40;
  * standing in an idle, to stay under 10 degrees;
  * Kliff's short hair, on bones about 5 cm long, to swing more than 5
    degrees and less than 40 in his run, inside its 45 degree limit;
  * Kliff's beard, held whole by the skeleton in the game, to get none;
  * a southern bandit's beard to hang its sway bones from the chin's face
    bone, not the head, starting at the beard and not inside the head,
    and to swing more than 5 degrees and less than 40 in a run.

Exit code 0 means every check passed.
"""

import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import mesh, packs, sway  # noqa: E402
from cd_animator.formats import pac, paz  # noqa: E402

DAMIAN = "1_pc/2_phw/cd_phw_damian/cd_phw_damian_00000"
RUN = "1_pc/2_phw/01_npc/cd_phw_adult_00_00_nor_move_run_f_ing_00"
IDLE = "1_pc/2_phw/01_npc/cd_phw_adult_00_00_nor_std_idle_00"
KLIFF_RUN = "1_pc/1_phm/cd_phm_basic_00_00_nor_move_run_f_ing_00"
BANDIT = "2_mon/cd_m0001_00_twofeet/cd_m0001_00_phm_south/cd_m0001_00_phm_south_23002"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_values(idx):
    path = "character/model/1_pc/1_phm/head/hair/cd_phm_00_hair_00_0022_player.pac"
    m = pac.read_pac(paz.read(idx.by_path[path]), 0, idx.bone_hashes())
    pins = [p for sb in m.submeshes for p in sb.pins]
    below = sum(1 for p in pins if p < 63)
    return report(below == 24607 and min(pins) > 0 and sway.sway_parts(m),
                  f"Kliff's hair: {below} of {len(pins)} vertices below 63, lowest {min(pins)}")


def angles(arm):
    out = []
    for b in arm.data.bones:
        if b.get("cd_stiffness"):
            a = math.degrees(arm.pose.bones[b.name].rotation_quaternion.angle)
            out.append(min(a, 360.0 - a))
    return out


def most(arm, step=1):
    scene = bpy.context.scene
    top = 0.0
    for f in range(scene.frame_start, scene.frame_end + 1, step):
        scene.frame_set(f)
        top = max(top, max(angles(arm)))
    return top


def check_damian(idx):
    fails = 0
    bpy.ops.cd_animator.game_character(character=DAMIAN, textures=False, cloth=False)
    arm = bpy.context.view_layer.objects.active
    hair = next(o for o in arm.children if o.get("cd_sway"))
    bones = [b for b in arm.data.bones if b.get("cd_stiffness")]
    path = next(p for p in idx.meshes if p.endswith("/" + hair["cd_pac"]))
    m = pac.read_pac(paz.read(idx.by_path[path + ".pac"]), 0, mesh.known_hashes(arm, idx.bone_hashes()))
    pins = [p for sb in m.submeshes for p in sb.pins]
    names = {b.name for b in bones}
    groups = {g.index for g in hair.vertex_groups if g.name in names}
    worst = 0.0
    for v, pin in zip(hair.data.vertices, pins):
        share = sum(g.weight for g in v.groups if g.group in groups)
        worst = max(worst, abs(share - (1.0 - pin / 63.0)))
    still = max(angles(arm))
    parents = sorted({b.parent.name for b in bones})
    under = all(b.parent.name == "Bip01 Head" or "Bip01 Head" in {a.name for a in b.parent.parent_recursive}
                or b.parent.name.startswith(("Bip01 Neck", "Bip01 Spine2")) for b in bones)
    fails += report(len(bones) >= 2 and under and worst < 1e-3 and still < 0.01,
                    f"Damian: {len(bones)} sway bones on {parents}, sway weights within {worst:.5f} of "
                    f"1 - value / 63, at rest {still:.2f} degrees")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=RUN)
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    first = max(angles(arm))
    top = most(arm)
    fails += report(first < 0.5 and 5.0 < top < 40.0,
                    f"running: {first:.1f} degrees on the first frame, at most {top:.1f}")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=IDLE)
    calm = most(arm, 2)
    fails += report(calm < 10.0, f"standing: at most {calm:.1f} degrees")
    return fails


def check_kliff():
    fails = 0
    bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", textures=False, cloth=False,
                                       clip=KLIFF_RUN)
    arm = bpy.context.view_layer.objects.active
    lengths = [b.length for b in arm.data.bones if b.get("cd_stiffness")]
    top = most(arm)
    fails += report(lengths and 5.0 < top < 40.0,
                    f"Kliff running: {len(lengths)} sway bones {min(lengths) * 100:.1f} to "
                    f"{max(lengths) * 100:.1f} cm long, at most {top:.1f} degrees")
    beard = next(o for o in arm.children if o.get("cd_component") == "CD_Beard")
    fails += report(not beard.get("cd_sway"), f"Kliff's beard {beard.name} gets {beard.get('cd_sway', 0)} sway bones")
    return fails


def check_beard():
    bpy.ops.cd_animator.game_character(character=BANDIT, textures=False, cloth=False, clip=KLIFF_RUN)
    arm = bpy.context.view_layer.objects.active
    beard = next(o for o in arm.children if "_beard_" in o.get("cd_pac", ""))
    bones = [b for b in arm.data.bones if b.get("cd_stiffness") and b.get("cd_extra") == beard["cd_pac"]]
    head = arm.data.bones["Bip01 Head"].head_local
    face = all(b.parent.parent and b.parent.parent.name == "B_face_com" for b in bones)
    inside = min((b.head_local - head).length for b in bones) if bones else 0.0
    top = 0.0
    scene = bpy.context.scene
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        for b in bones:
            a = math.degrees(arm.pose.bones[b.name].rotation_quaternion.angle)
            top = max(top, min(a, 360.0 - a))
    return report(len(bones) >= 2 and face and inside > 0.03 and 5.0 < top < 40.0,
                  f"{beard.name}: {len(bones)} sway bones on {sorted({b.parent.name for b in bones})}, starting "
                  f"{inside * 100:.0f} cm or more from the head bone, running at most {top:.1f} degrees")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_values(idx)
    fails += check_damian(idx)
    fails += check_kliff()
    fails += check_beard()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
