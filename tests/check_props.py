"""Check weapons and props: meshes with bones of their own, and sockets.

    blender -b --factory-startup --python tests/check_props.py -- [game folder]

Needs the game installed. It requires:

  * 100 weapon meshes, picked evenly, to read with their own bone list and a
    palette naming those bones;
  * phm_01's 52 sockets to hang from bones of the skeleton, the back and
    hip sockets keeping their parents although StackEquipInfo names them
    again, and the part rules to send a right-hand sword to the right hand
    by its grip when drawn and to the left hip when put away;
  * a sword attached to Kliff's right hand to follow only Bip_Weapon_R, its
    grip on the socket at rest, and with a clip playing every vertex to move
    exactly as that bone does;
  * a helmet with its own bone list to follow Kliff's head bones with every
    vertex weighted;
  * the spear in an NPC's appearance to be attached at its socket when the
    character is built.

Exit code 0 means every check passed.
"""

import os
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import convert, packs  # noqa: E402
from cd_animator.formats import paa, pac, paz, sockets  # noqa: E402

PHM = "character/model/1_pc/1_phm/phm_01"
CLIP = "1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_dismount_l_00"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def evaluated(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = [v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return co


def check_reader(idx):
    weapons = sorted(m for m in idx.meshes if "/1_phm/weapon/" in m)
    picked = weapons[::max(1, len(weapons) // 100)][:100]
    hashes = idx.bone_hashes()
    bad, own = [], 0
    for name in picked:
        try:
            m = pac.read_pac(paz.read(idx.by_path[name + ".pac"]), 0, hashes)
        except ValueError as exc:
            bad.append(f"{name}: {exc}")
            continue
        names = {b.hash for b in m.bones}
        own += bool(m.bones) and any(h in names for h in m.palette)
    return report(not bad and own == len(picked),
                  f"{len(picked)} of {len(weapons)} weapon meshes read, {own} with their own bones in the palette"
                  f"{'; ' + bad[0] if bad else ''}")


def check_rules(idx):
    fails = 0
    sk = packs.sockets(idx, PHM)
    bones = {b.name for b in paa.read_pab(paz.read(idx.by_path[PHM + ".pab"])).bones}
    orphans = [s.name for s in sk.values() if s.parent and s.parent not in bones]
    fails += report(len(sk) == 52 and not orphans and sk["Pelvis_R_Socket"].parent == "B_WeaponIn_L_00"
                    and sk["Spine2_B_SubWeapon_Socket"].parent == "Bip_Weapon_Attach_In_02",
                    f"{len(sk)} sockets on phm_01, all on its bones{'; not ' + str(orphans) if orphans else ''}")
    rule = packs.part_rules(idx, PHM, playable=True).get("CD_MainWeapon_Sword_R")
    fails += report(sockets.placement(rule, True) == ("RHand_Socket", "Basic_ChildSocket")
                    and sockets.placement(rule, False) == ("Pelvis_L_Socket", "Pelvis_L_ChildSocket"),
                    f"right-hand sword: drawn {sockets.placement(rule, True)}, put away {sockets.placement(rule, False)}")
    return fails


def check_sword_and_helmet(idx):
    fails = 0
    bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", textures=False)
    arm = bpy.context.view_layer.objects.active
    before = set(arm.children)
    bpy.ops.cd_animator.game_prop(prop="cd_phm_01_sword_0001_01_r", state="OUT", textures=False)
    sword = next(o for o in arm.children if o not in before)
    groups = [g.name for g in sword.vertex_groups]
    flat = sword["cd_placement"]
    placement = Matrix([flat[0:4], flat[4:8], flat[8:12], flat[12:16]])
    grip = sockets.read_sockets(paz.read(idx.by_path[
        "character/descriptors/socketbonedata/1_pc/1_phm/weapon/1_onehandweapon/cd_phm_01_sword_0001_r.sockets.xml"]))
    grip_point = placement @ convert.vec_in(grip["Basic_ChildSocket"].translation)
    hand = arm.data.bones["Bip_Weapon_R"].head_local
    fails += report(groups == ["Bip_Weapon_R"] and (grip_point - hand).length < 1e-5,
                    f"sword in the right hand: follows {groups}, grip {(grip_point - hand).length * 1000:.4f} mm "
                    "from the hand socket")

    before = set(arm.children)
    bpy.ops.cd_animator.game_prop(prop="cd_phm_00_hel_set_0102_c", textures=False)
    helmet = next(o for o in arm.children if o not in before)
    unweighted = sum(1 for v in helmet.data.vertices if not v.groups)
    hg = {g.name for g in helmet.vertex_groups}
    fails += report(unweighted == 0 and "Bip01 Head" in hg and hg <= {b.name for b in arm.data.bones}
                    and "cd_socket" not in helmet,
                    f"helmet with its own bones follows {len(hg)} of Kliff's bones, Bip01 Head among them, "
                    f"{unweighted} vertices unweighted")

    rest = evaluated(sword)
    bone_rest = arm.data.bones["Bip_Weapon_R"].matrix_local.copy()
    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=CLIP)
    worst = 0.0
    for f in (10, 25, 50):
        bpy.context.scene.frame_set(f)
        move = arm.pose.bones["Bip_Weapon_R"].matrix @ bone_rest.inverted()
        got = evaluated(sword)
        worst = max(worst, max((g - move @ r).length for g, r in zip(got, rest)))
    fails += report(worst < 1e-5, f"with a dismount playing the sword moves as the hand bone, worst {worst * 1000:.4f} mm")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    return fails


def check_npc_spear():
    bpy.ops.cd_animator.game_character(character="cd_ntm_desert_20010", textures=False)
    arm = bpy.context.view_layer.objects.active
    spear = next((o for o in arm.children if o.get("cd_component") == "CD_TwoHandWeapon_Spear"), None)
    where = spear.get("cd_socket") if spear else None
    return report(where is not None and where.startswith("RHand_Socket"),
                  f"an NPC's spear is attached when the character is built: {where}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_reader(idx)
    fails += check_rules(idx)
    fails += check_sword_and_helmet(idx)
    fails += check_npc_spear()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
