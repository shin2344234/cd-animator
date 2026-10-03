"""Check cloth: the pins read from the meshes, and cloaks simulated in
Blender.

    blender -b --factory-startup --python tests/check_cloth.py -- [game folder]

Needs the game installed. It requires:

  * Kliff's body to have every vertex pinned (63), and his leather cloak
    573 free vertices (0), all lower than any fully pinned one but a few;
  * Kliff built in his gear to give the cloak, which is all cloth, a Cloth
    modifier after its Armature modifier with the pins as its pin group,
    to split his coat's tails into a cloth object of their own, and to give
    his body a Collision modifier;
  * with a run baked, the pinned vertices to sit where the skeleton puts
    them, the hem to move off the skinned pose, and no vertex to end up
    more than 1.5 m from the pelvis;
  * standing still, the cloak to settle within 10 cm of the skinned pose.

Exit code 0 means every check passed.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import cloth, packs  # noqa: E402
from cd_animator.formats import pac, paz  # noqa: E402

RUN = "1_pc/1_phm/cd_phm_basic_00_00_nor_move_run_f_ing_00"
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
ARMOR = "character/model/1_pc/1_phm/armor/"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_pins(idx):
    hashes = idx.bone_hashes()
    body = pac.read_pac(paz.read(idx.by_path["character/model/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac"]), 0, hashes)
    pins = [p for sb in body.submeshes for p in sb.pins]
    cloak = pac.read_pac(paz.read(idx.by_path[ARMOR + "19_cloak/cd_phm_00_cloak_0054_15.pac"]), 0, hashes)
    rows = [(pos[1], p) for sb in cloak.submeshes for pos, p in zip(sb.positions, sb.pins)]
    free = [y for y, p in rows if p == 0]
    held = sorted(y for y, p in rows if p == 63)
    above = sum(1 for y in free if y > held[len(held) // 20])
    return report(min(pins) == 63 and len(free) == 573 and above < 60,
                  f"pins: body all {min(pins)}; cloak {len(free)} free of {len(rows)}, {above} above the lowest "
                  f"5% of its pinned vertices")


def evaluated(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = [obj.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return co


def skinned(obj):
    m = next(m for m in obj.modifiers if m.type == "CLOTH")
    m.show_viewport = False
    co = evaluated(obj)
    m.show_viewport = True
    return co


def check_kliff():
    fails = 0
    bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", gear="AWAY", textures=False, clip=RUN)
    arm = bpy.context.view_layer.objects.active
    objs = cloth.cloth_objects(arm)
    cloak = next(o for o in objs if o.get("cd_component") == "CD_Cloak")
    kinds = [m.type for m in cloak.modifiers]
    group = cloak.vertex_groups[cloth.PIN_GROUP].index
    weight = [next((g.weight for g in v.groups if g.group == group), 0.0) for v in cloak.data.vertices]
    tails = [o for o in objs if o.get("cd_cloth_of") == "cd_phm_00_ub_0054_15"]
    body = next(o for o in arm.children if o.get("cd_component") == "CD_Nude")
    fails += report(kinds == ["ARMATURE", "CLOTH"] and "cd_cloth_of" not in cloak and min(weight) == 0.0
                    and max(weight) == 1.0 and len(tails) == 1 and any(m.type == "COLLISION" for m in body.modifiers),
                    f"cloak modifiers {kinds}, pins {min(weight):.0f} to {max(weight):.0f}, coat tails split off: "
                    f"{[o.name for o in tails]}, body collides")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.bake_chains()
    scene = bpy.context.scene
    pelvis = arm.pose.bones["Bip01 Pelvis"]
    pinned = [i for i, w in enumerate(weight) if w > 0.999]
    free = [i for i, w in enumerate(weight) if w == 0.0]
    slip = moved = far = 0.0
    for f in (scene.frame_end // 2, scene.frame_end):
        scene.frame_set(f)
        sim, skin = evaluated(cloak), skinned(cloak)
        centre = (arm.matrix_world @ pelvis.matrix).translation
        slip = max(slip, max((sim[i] - skin[i]).length for i in pinned))
        moved = max(moved, max((sim[i] - skin[i]).length for i in free))
        for o in objs:
            far = max(far, max((p - centre).length for p in evaluated(o)))
    fails += report(slip < 0.001 and moved > 0.05 and far < 1.5,
                    f"running: pinned vertices {slip * 1000:.3f} mm off the skeleton, the hem up to "
                    f"{moved * 100:.0f} cm off it, nothing more than {far:.2f} m from the pelvis")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=IDLE)
    bpy.ops.cd_animator.bake_chains()
    scene.frame_set(60)
    sim, skin = evaluated(cloak), skinned(cloak)
    drift = max((a - b).length for a, b in zip(sim, skin))
    fails += report(drift < 0.1, f"standing, the cloak settles within {drift * 100:.1f} cm of its skinned shape")
    return fails


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_pins(idx)
    fails += check_kliff()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
