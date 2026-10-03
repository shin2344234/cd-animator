"""Check gear: the data tables of characters and items, and characters built
with what their records give them.

    blender -b --factory-startup --python tests/check_gear.py -- [game folder]

Needs the game installed. It requires:

  * the iteminfo and characterinfo tables to read with every record's key
    and name, and Kliff to be key 1;
  * Kliff's record to be found from his appearance, to name his own
    character description and to give his ten items in order, the sword
    with its scabbard;
  * at least 1,400 appearances to find gear, and a greyhound whose record
    lists a shield among its loot to find none;
  * the player description's rules to say a shield shows only in use, and
    the NPC description's rule for the same part not to pick that up;
  * Kliff built with his gear put away to wear his Inytium leather in
    place of his appearance's outfit, with the sword and scabbard at his
    left hip, the lantern at his right thigh, and no shield, bow or dagger;
  * Kliff with his gear in use to hold the sword in his right hand and the
    shield on his left forearm, the bow left out;
  * a soldier to keep his appearance's armour, carry his shield on his
    back moved out over his clothes, and carry no second copy of a part
    his appearance already has.

Exit code 0 means every check passed.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import packs  # noqa: E402
from cd_animator.formats import paz, sockets, staticinfo  # noqa: E402

KLIFF = "1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000"
KLIFF_ITEMS = ["Wolf_OneHandSword", "Wood_OneHandShield", "Rusty_Hagwood_OneHandDagger", "GreyWolf_OneHandBow",
               "Inytium_Leather_Armor", "Inytium_Leather_Cloak", "Inytium_Leather_Gloves", "Inytium_Leather_Boots",
               "Item_Fist_Kliff", "Lantern"]
SOLDIER = "cd_m0001_00_phm_south_22090"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_tables(idx):
    fails = 0
    for name, count in (("iteminfo", 6816), ("characterinfo", 7250)):
        table = idx.table(name)
        bad = [k for k, rec in table.items()
               if not staticinfo.record_name(rec) or int.from_bytes(rec[:4], "little") != k]
        fails += report(len(table) == count and not bad, f"{name}: {len(table)} records, {len(bad)} without key and name")
    kliff = staticinfo.record_name(idx.table("characterinfo")[1])
    fails += report(kliff == "Kliff", f"characterinfo key 1 is {kliff}")
    return fails


def check_records(idx):
    fails = 0
    g = packs.gear(idx, KLIFF)
    names = [i for i, _p in g.items] if g else []
    sword = dict(g.items).get("Wolf_OneHandSword") if g else None
    fails += report(g is not None and g.record == "Kliff" and g.description == "phm_description_player_kliff"
                    and names == KLIFF_ITEMS and sword == ["cd_phm_01_sword_0019_r", "cd_phm_01_sword_0053_r_in"],
                    f"Kliff's record: {g.record if g else None}, {g.description if g else None}, {names}, sword {sword}")
    found = sum(1 for a in idx.appearances if packs.gear(idx, a))
    dog = next(a for a in idx.appearances if a.endswith("cd_m0002_00_greyhound_0001_00000"))
    fails += report(found >= 1400 and packs.gear(idx, dog) is None,
                    f"{found} of {len(idx.appearances)} appearances have gear; the greyhound has "
                    f"{packs.gear(idx, dog)}")
    player = sockets.read_part_sockets(paz.read(idx.by_path[packs.DESCRIPTIONS + "phm_description_player_kliff.xml"]))
    rules = packs.part_rules(idx, "character/model/1_pc/1_phm/phm_01", False, "phm_description_001")
    fails += report(player["CD_MainWeapon_Shield_L"].get("Visible") == "Out"
                    and "Visible" not in rules["CD_MainWeapon_Shield_L"],
                    f"shield rule: player {player['CD_MainWeapon_Shield_L'].get('Visible')}, "
                    f"NPC {rules['CD_MainWeapon_Shield_L'].get('Visible')}")
    return fails


def parts(arm):
    return {o["cd_component"]: o for o in arm.children if "cd_component" in o and "cd_cloth_of" not in o}


def check_kliff():
    fails = 0
    bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", gear="AWAY", textures=False)
    arm = bpy.context.view_layer.objects.active
    got = parts(arm)
    where = {c: str(o.get("cd_socket", "")).split(" ", 1)[0] for c, o in got.items()}
    body = got.get("CD_Upperbody")
    fails += report(body is not None and body.name.split(".")[0] == "cd_phm_00_ub_0054_15"
                    and got["CD_Cloak"].get("cd_item") == "Inytium_Leather_Cloak"
                    and arm.get("cd_description") == "phm_description_player_kliff",
                    f"Kliff wears {body.name if body else None} and {got['CD_Cloak'].get('cd_item')}")
    fails += report(where.get("CD_MainWeapon_Sword_R") == "Pelvis_L_Socket"
                    and where.get("CD_MainWeapon_Sword_IN_R") == "Pelvis_L_Socket"
                    and where.get("CD_Lantern") == "Physics_ThighR_00_Socket"
                    and not {"CD_MainWeapon_Shield_L", "CD_MainWeapon_Bow", "CD_MainWeapon_Dagger_R"} & set(got),
                    f"put away: sword {where.get('CD_MainWeapon_Sword_R')}, scabbard "
                    f"{where.get('CD_MainWeapon_Sword_IN_R')}, lantern {where.get('CD_Lantern')}, "
                    f"shown only in use left out: {not {'CD_MainWeapon_Shield_L', 'CD_MainWeapon_Bow'} & set(got)}")
    bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", gear="DRAWN", textures=False)
    got = parts(bpy.context.view_layer.objects.active)
    where = {c: str(o.get("cd_socket", "")).split(" ", 1)[0] for c, o in got.items()}
    fails += report(where.get("CD_MainWeapon_Sword_R") == "RHand_Socket"
                    and where.get("CD_MainWeapon_Shield_L") == "LForearm_Socket"
                    and where.get("CD_MainWeapon_Sword_IN_R") == "Pelvis_L_Socket"
                    and "CD_MainWeapon_Bow" not in got,
                    f"in use: sword {where.get('CD_MainWeapon_Sword_R')}, shield {where.get('CD_MainWeapon_Shield_L')}, "
                    f"bow {where.get('CD_MainWeapon_Bow', 'left out')}")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    return fails


def check_soldier():
    bpy.ops.cd_animator.game_character(character=SOLDIER, gear="AWAY", textures=False)
    arm = bpy.context.view_layer.objects.active
    got = parts(arm)
    shield = got.get("CD_MainWeapon_Shield_L")
    body = got.get("CD_Upperbody")
    components = [o["cd_component"] for o in arm.children if "cd_component" in o and "cd_cloth_of" not in o]
    twice = sorted({c for c in components if components.count(c) > 1})
    pushed = shield.get("cd_pushed", 0) if shield else 0
    return report(shield is not None and str(shield.get("cd_socket", "")).startswith("Spine2_B_Shield_Socket")
                  and 0.03 < pushed < 0.25 and body is not None and "cd_item" not in body and not twice,
                  f"soldier: shield at {shield.get('cd_socket') if shield else None}, moved out {pushed * 100:.1f} cm, "
                  f"upper body {body.name if body else None} from the appearance, parts twice: {twice}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_tables(idx)
    fails += check_records(idx)
    fails += check_kliff()
    fails += check_soldier()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
