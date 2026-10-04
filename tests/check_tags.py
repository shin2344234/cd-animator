"""Check Tag footsteps against the game's own footstep events.

    blender -b --factory-startup --python tests/check_tags.py -- [game folder]

Needs the game installed. On Kliff's skeleton it requires:

  * every event type 0 to 7 to have a name in the sidebar;
  * Tag footsteps, on 16 of the game's clips that carry footstep events,
    to agree with the game's left and right foot planted events (4, 5) on
    at least 78% of frames, where calling every frame planted agrees on
    about 64%;
  * the clip's other events, types 0 and 1, to stay as they were;
  * his standing idle to come out with each foot planted from start to end
    and no step;
  * the new events to reach the exported .paa_metabin.

Exit code 0 means every check passed.
"""

import os
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import meta, packs  # noqa: E402
from cd_animator.formats import metabin_codec  # noqa: E402

CLIPS = ["cd_phm_basic_00_00_nor_base_std_corpse_select_end_00",
         "cd_phm_basic_freeclimb_move_lv1_070to180_070_d_handr_00",
         "cd_phm_sword_01_01_def_normal_move_b_guard_handl_shield_lv3_04",
         "cd_phm_basic_00_00_nor_move_facedown_standup_roll_f_00",
         "cd_phm_basic_00_00_nor_base_move_runfast2_sidestep_fr_ing_00",
         "cd_phm_basic_00_00_normal_move_walk_jump_f_end_r_000",
         "cd_phm_battleaxe_01_01_skill_normal_move_f_footl_kick_05",
         "01_npc/cd_phm_adult_00_00_abn_sit000_move_avoid_r_bump_l_light_00",
         "00_riding/cd_r0004_02_wagon_0001_nor_std_dismount_l_00",
         "cd_yann_basic_01_01_nor_move_dash_r_00",
         "cd_phm_basic_00_00_singlebridge_nor_move_walkfast_fl_ing_00",
         "cd_phm_basic_00_00_nor_move_swim_underwater_walkfast_fu_45_ing_00",
         "cd_phm_dlsd_01_01_nor_att_skill_rotationatt_move_b_stt_00",
         "cd_phm_bow_01_00_sit_std_turn180l_00",
         "cd_phw_03_01_att_skill_jumpshot_00_shot",
         "01_npc/cd_encount_dem_village_01_phm2_stt_00"]
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def planted(events, t, n):
    on = [False] * (n + 1)
    for b, e, tt in events:
        if tt == t:
            for f in range(max(0, round(b * 30)), min(n, round(e * 30)) + 1):
                on[f] = True
    return on


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    packs.index()
    fails = report(all(meta.TAG_NAMES.get(t) for t in range(8)), f"names: {meta.TAG_NAMES}")
    bpy.ops.cd_animator.game_skeleton(skeleton="1_pc/1_phm/phm_01")
    arm = bpy.context.view_layer.objects.active

    agree = total = 0
    others_kept = True
    for name in CLIPS:
        bpy.ops.cd_animator.game_clip(clip="1_pc/1_phm/" + name, voice=False)
        action = arm.animation_data.action
        n = round(action.frame_range[1])
        game = [(e.begin, e.end, e.type) for e in action.cd_meta.events]
        bpy.ops.cd_animator.tag_footsteps()
        mine = [(e.begin, e.end, e.type) for e in action.cd_meta.events]
        others_kept &= sorted(x for x in game if x[2] not in meta.FOOT_TYPES) == \
            sorted(x for x in mine if x[2] not in meta.FOOT_TYPES)
        for t in (4, 5):
            a, g = planted(mine, t, n), planted(game, t, n)
            agree += sum(x == y for x, y in zip(a, g))
            total += n + 1
    fails += report(agree / total >= 0.78, f"planted frames agree with the game's on {agree / total:.3f}")
    fails += report(others_kept, "events of types 0 and 1 kept as they were")

    bpy.ops.cd_animator.game_clip(clip=IDLE, voice=False)
    action = arm.animation_data.action
    bpy.ops.cd_animator.tag_footsteps()
    n = action.frame_range[1] / 30
    feet = sorted((e.type, round(e.begin, 3), round(e.end, 3)) for e in action.cd_meta.events if e.type in meta.FOOT_TYPES)
    fails += report(feet == [(4, 0.0, round(n, 3)), (5, 0.0, round(n, 3))], f"the idle's feet: {feet}")

    out = os.path.join(tempfile.mkdtemp(prefix="cd_tags_"), "idle.paa")
    bpy.ops.cd_animator.export_paa(filepath=out, clip="ACTION")
    written = metabin_codec.read_metabin(open(out[:-4] + ".paa_metabin", "rb").read())
    fails += report(sorted((e.type, round(e.begin, 3), round(e.end, 3)) for e in written.events
                           if e.type in meta.FOOT_TYPES) == feet, "the export carries them")

    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
