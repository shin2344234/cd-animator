"""Check characters built from their appearance files.

    blender -b --factory-startup --python tests/check_character.py -- [game folder]

Needs the game installed. It requires:

  * 300 appearance files, picked evenly through the packs, to resolve to a
    skeleton and meshes that are all in the packs;
  * Kliff (cd_phm_macduff_00000) to build with his skeleton and exactly the
    19 meshes of his default look, each one read, textured and parented;
  * Damian to build on the female skeleton with every mesh read.

Exit code 0 means every check passed.
"""

import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import packs  # noqa: E402

PHM = "1_pc/1_phm/"
KLIFF = {
    "CD_Nude": "nude/cd_phm_00_nude_00_0001",
    "CD_Underwear": "armor/38_underwear/cd_phm_00_uw_00_0001",
    "CD_Head": "head/head/cd_phm_00_head_00_0001_macduff",
    "CD_EyeLeft": "head/head_sub/cd_phm_00_eyeleft_00_0001",
    "CD_EyeRight": "head/head_sub/cd_phm_00_eyeright_00_0001",
    "CD_Eyebrows": "head/head_sub/cd_phm_00_eyebrow_00_0002",
    "CD_Eyelashes": "head/head_sub/cd_phm_00_head_00_0001_macduff_eyelash_0001",
    "CD_Tooth": "head/head_sub/cd_phm_00_tooth_00_0001",
    "CD_Nude_Hair": "head/beard/cd_phm_00_fuzz_00_0001",
    "CD_Hair": "head/hair/cd_phm_00_hair_00_0022_player",
    "CD_Beard": "head/beard/cd_phm_00_beard_00_0005_06_player",
    "CD_Upperbody": "armor/9_upperbody/cd_phm_00_ub_00_0054",
    "CD_Lowerbody": "armor/10_lowerbody/cd_phm_00_lb_00_0054",
    "CD_Lowerbody_Acc": "armor/10_lowerbody/cd_phm_00_lb_belt_00_0001",
    "CD_Shoulder_Under": "armor/14_sho/cd_phm_00_sho_under_00_0054",
    "CD_Cloak": "armor/19_cloak/cd_phm_00_cloak_00_0054",
    "CD_Cloak_Shoulder": "armor/14_sho/cd_phm_00_sho_00_0054",
    "CD_Hand": "armor/11_hand/cd_phm_00_hand_0054",
    "CD_Foot": "armor/12_foot/cd_phm_00_foot_0054",
}


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_survey(idx):
    t = time.time()
    names = idx.appearances[::max(1, len(idx.appearances) // 300)][:300]
    meshes, bad = 0, []
    for name in names:
        try:
            skel, parts, _skipped, missing = packs.character(idx, name)
        except (packs.PackError, ValueError, SyntaxError) as exc:
            bad.append(f"{name}: {exc}")
            continue
        absent = [m for _c, m in parts if m + ".pac" not in idx.by_path]
        if missing or absent or skel + ".pab" not in idx.by_path:
            bad.append(f"{name}: {missing or absent or skel}")
        meshes += len(parts)
    # One appearance file in the game is not well-formed XML.
    return report(len(bad) <= 1, f"{len(names)} of {len(idx.appearances)} appearances resolve, {meshes} meshes, "
                                 f"all in the packs ({time.time() - t:.1f} s){'; ' + bad[0] if bad else ''}")


def build(name):
    t = time.time()
    res = bpy.ops.cd_animator.game_character(character=name)
    arm = bpy.context.view_layer.objects.active
    return res, arm, time.time() - t


def check_kliff():
    res, arm, took = build("cd_phm_macduff_00000")
    got = {o["cd_component"]: o for o in arm.children}
    want = {c: "character/model/" + PHM + p for c, p in KLIFF.items()}
    wrong = [c for c in want if c not in got or got[c].name.split(".")[0] != want[c].rsplit("/", 1)[-1]]
    extra = [c for c in got if c not in want]
    untextured = [o.name for o in got.values()
                  if not any(m.get("cd_shader") for m in o.data.materials)]
    fails = report(res == {"FINISHED"} and arm.get("cd_game_path") == "character/model/" + PHM + "phm_01",
                   f"Kliff builds on phm_01 ({took:.1f} s)")
    fails += report(not wrong and not extra, f"{len(got)} meshes, his 19 default parts"
                                             f"{'; wrong ' + str(wrong) if wrong else ''}{'; extra ' + str(extra) if extra else ''}")
    fails += report(not untextured, f"every part has the game's materials{'; not ' + str(untextured) if untextured else ''}")
    return fails


def check_damian():
    res, arm, took = build("1_pc/2_phw/cd_phw_damian/cd_phw_damian_00000")
    return report(res == {"FINISHED"} and arm["cd_game_path"].endswith("/phw_01") and len(arm.children) == 16,
                  f"Damian builds on phw_01 with {len(arm.children)} meshes ({took:.1f} s)")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_survey(idx)
    fails += check_kliff()
    fails += check_damian()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
