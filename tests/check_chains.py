"""Check physics chains: weapon bones added to the armature, and their
simulation.

    blender -b --factory-startup --python tests/check_chains.py -- [game folder]

Needs the game installed. It requires:

  * the flexible flail's four swinging links to pivot at their bones'
    heads, and the short flail's chain and ball, one rigid piece on a bone
    at the ball's centre, to pivot where it meets the stick instead;
  * the short flail attached to Kliff's right hand to add its two bones
    under the hand's bone, with the ball's vertices on the swinging one;
  * with no clip, the chain to hang straight down from the stick;
  * with a dismount playing, every link to stay on its pivot at its own
    length, the chain to swing, and the ball's vertices to move with their
    bone;
  * the exported clip to hold no track for a chain bone.

Exit code 0 means every check passed.
"""

import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import chains, export, packs  # noqa: E402
from cd_animator.formats import pac, paz  # noqa: E402

WEAPON = "character/model/1_pc/1_phm/weapon/1_onehandweapon/"
CLIP = "1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_dismount_l_00"
FLAIL = "cd_phm_01_flail_0001"
BALL = FLAIL + ":B_Add_Flail_002"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def read(idx, name):
    return pac.read_pac(paz.read(idx.by_path[WEAPON + name + ".pac"]), 0, idx.bone_hashes())


def check_plan(idx):
    fails = 0
    flex = read(idx, "cd_phm_01_flexibleflail_0001")
    rows = chains.plan(flex, lambda i: flex.bones[i].parent >= 0)
    swing = [(flex.bones[i].name, h) for i, h, _t, s, _m, _r in rows if s]
    heads = {b.name: Vector(b.world[3::4][:3]) for b in flex.bones}
    off = [n for n, h in swing[:3] if (h - heads[n]).length > 1e-4]
    fails += report(len(swing) == 4 and not off and abs(swing[3][1].z - heads[swing[3][0]].z) < 0.05,
                    f"flexible flail: {len(swing)} swinging links, {len(off)} off their heads, last at "
                    f"{swing[-1][1].z:.3f} by its head {heads[swing[-1][0]].z:.3f}" if swing else "no links")
    short = read(idx, FLAIL)
    rows = chains.plan(short, lambda i: short.bones[i].parent >= 0)
    piv = next((h for i, h, _t, s, _m, _r in rows if s), None)
    fails += report(piv is not None and abs(piv.z + 0.86) < 0.03,
                    f"short flail: the ball's piece turns at z {piv.z:.3f}, where it meets the stick, "
                    f"not at its bone, z -1.524" if piv else "short flail: nothing swings")
    return fails


def ball_check(arm, ball_obj):
    """Largest distance between the ball piece's evaluated vertices and
    where its bone's pose puts them."""
    pb = arm.pose.bones[BALL]
    group = ball_obj.vertex_groups[BALL].index
    rest = [v.co.copy() for v in ball_obj.data.vertices
            if any(g.group == group and g.weight > 0.99 for g in v.groups)]
    ids = [v.index for v in ball_obj.data.vertices if any(g.group == group and g.weight > 0.99 for g in v.groups)]
    ev = ball_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    move = pb.matrix @ pb.bone.matrix_local.inverted()
    worst = max((me.vertices[i].co - move @ r).length for i, r in zip(ids, rest))
    ev.to_mesh_clear()
    return worst, len(ids)


def check_kliff():
    fails = 0
    bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", gear="NONE", textures=False)
    arm = bpy.context.view_layer.objects.active
    bpy.ops.cd_animator.game_prop(prop=FLAIL, state="OUT", textures=False)
    added = [b for b in arm.data.bones if b.get("cd_extra") == FLAIL]
    ball_obj = next(o for o in arm.children if o.get("cd_pac") == FLAIL)
    fails += report(len(added) == 2 and added[0].parent.name == "Bip_Weapon_R" and added[1].get("cd_chain")
                    and BALL in ball_obj.vertex_groups,
                    f"flail on Kliff: {[b.name for b in added]} under {added[0].parent.name if added else None}")
    pb = arm.pose.bones[BALL]
    mw = arm.matrix_world
    d = (mw @ pb.tail - mw @ pb.head).normalized()
    angle = d.angle(Vector((0.0, 0.0, -1.0)))
    fails += report(angle < 0.09, f"with no clip the chain hangs {angle * 57.3:.1f} degrees from straight down")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=CLIP)
    scene = bpy.context.scene
    parent = arm.pose.bones[FLAIL + ":B_Add_Flail_000"]
    rel = parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
    length = pb.bone.length
    gap = stretch = worst = 0.0
    dirs = []
    for f in range(scene.frame_start, scene.frame_end + 1, 3):
        scene.frame_set(f)
        gap = max(gap, ((parent.matrix @ rel).translation - pb.head).length)
        stretch = max(stretch, abs((pb.tail - pb.head).length - length))
        dirs.append((pb.tail - pb.head).normalized())
        w, _n = ball_check(arm, ball_obj)
        worst = max(worst, w)
    swing = max(a.angle(b) for a in dirs for b in dirs)
    fails += report(gap < 1e-4 and stretch < 1e-4 and swing > 0.5,
                    f"with a dismount the link stays on its pivot ({gap * 1000:.3f} mm) at its length "
                    f"({stretch * 1000:.3f} mm) and swings through {swing * 57.3:.0f} degrees")
    fails += report(worst < 1e-4, f"the ball's vertices follow their bone within {worst * 1000:.4f} mm")

    _head, td, problems = export.build_track_data(arm, arm.animation_data.action, bake=True)
    named = [t.name for t in td.bones if t.name and ":" in t.name]
    fails += report(not named and not any(":" in p for p in problems),
                    f"the export holds {len(td.bones)} tracks, {len(named)} for chain bones")
    return fails


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_plan(idx)
    fails += check_kliff()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
