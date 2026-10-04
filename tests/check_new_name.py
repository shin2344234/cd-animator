"""Check new clip names: action charts pointed at new clips.

    blender -b --factory-startup --python tests/check_new_name.py -- [game folder]

Needs the game installed; it writes only to a temporary folder that stands
in for the game's bin64. It requires:

  * the chart reader to pack 556 of the game's 558 charts back byte for
    byte, the two it cannot parse being commonactioninfo and its
    _serialized copy;
  * the chart nodes that play Kliff's standing idle to include node 0 of
    basic_upper and of basic_lower, both in action 26107D3C, the upper
    chart's default action;
  * Where it plays to store the nodes chosen on a new clip;
  * Send to game to write the clip's three files and the two charts, each
    chart the game's with the new path added at the end of its clip table
    and the chosen node on it, every other node and the rest of the file
    unchanged;
  * a second new clip on another node of basic_upper to go into the same
    chart, keeping the first;
  * sending the first again with only its upper node chosen to put its
    lower node back, which leaves basic_lower the game's own, so it is
    deleted;
  * Check the game to list each chart with the clip its nodes play;
  * Take out of the game to put a clip's nodes back, and the chart, once
    nothing in it differs from the game's, to go.

Exit code 0 means every check passed.
"""

import os
import shutil
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import actioncharts, ingame, packs  # noqa: E402
from cd_animator.formats import paac  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
UPPER = actioncharts.CHARTS + "upperaction/1_pc/1_phm/basic_upper.paac"
LOWER = actioncharts.CHARTS + "loweraction/1_pc/1_phm/basic_lower.paac"
FIRST, SECOND = "cd_phm_cdanim_check_first_00", "cd_phm_cdanim_check_second_00"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def chart(path):
    with open(path, "rb") as f:
        return paac.Chart.parse(f.read())


def differs(mine, game):
    """Nodes whose clip differs, and whether anything else does once the
    clip table and the nodes' clip indexes are set to the game's."""
    nodes = [i for i, (a, b) in enumerate(zip(mine.nodes, game.nodes))
             if mine.strings[1][a.header.anim_index] != game.strings[1][b.header.anim_index]]
    extra = mine.strings[1][len(game.strings[1]):]
    for a, b in zip(mine.nodes, game.nodes):
        a.header.anim_index, a.header.anim_index_a = b.header.anim_index, b.header.anim_index_a
    mine.strings[1] = mine.strings[1][:len(game.strings[1])]
    return nodes, extra, mine.pack() == game.pack()


def new_clip(arm, name, plays):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_new_clip(clip=IDLE, clip_name=name, start="MOTION")
    bpy.ops.cd_animator.play_where(uses=[{"chart": p, "node": n, "chosen": True, "name": f"{p} {n}"}
                                         for p, n in plays])
    return arm.animation_data.action


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = 0

    same, unread = 0, []
    for p in actioncharts.chart_paths(idx):
        data = actioncharts.game_bytes(idx, p)
        try:
            same += paac.Chart.parse(data).pack() == data
        except paac.ParseError:
            unread.append(actioncharts.chart_name(p))
    fails += report(same == 556 and sorted(unread) == ["commonactioninfo.paac", "commonactioninfo_serialized.paac"],
                    f"charts packed back byte for byte: {same} of {len(actioncharts.chart_paths(idx))}; "
                    f"unread {unread}")

    uses = actioncharts.uses(idx, IDLE)
    keys = {(p, n): k for p, n, k in uses}
    upper = paac.Chart.parse(actioncharts.game_bytes(idx, UPPER))
    fails += report(keys.get((UPPER, 0)) == 0x26107D3C and keys.get((LOWER, 0)) == 0x26107D3C
                    and upper.default_action_hash == 0x26107D3C,
                    f"the idle plays at {len(uses)} nodes of {len({p for p, _n, _k in uses})} charts, "
                    "node 0 of basic_upper and basic_lower in action 26107D3C")

    tmp = tempfile.mkdtemp(prefix="cd_newname_")
    b64 = os.path.join(tmp, "bin64")
    os.makedirs(b64)
    open(os.path.join(b64, ingame.LOADER), "wb").close()
    ingame.bin64 = lambda context=None: b64
    root = os.path.join(b64, ingame.FOLDER)

    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE")
    arm = bpy.context.view_layer.objects.active
    first = new_clip(arm, FIRST, [(UPPER, 0), (LOWER, 0)])
    fails += report(list(first.get("cd_plays", [])) == [f"{UPPER}#0", f"{LOWER}#0"],
                    f"Where it plays stored {list(first.get('cd_plays', []))}")

    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    files = sorted(os.listdir(root))
    game_upper = paac.Chart.parse(actioncharts.game_bytes(idx, UPPER))
    game_lower = paac.Chart.parse(actioncharts.game_bytes(idx, LOWER))
    up = differs(chart(os.path.join(root, "basic_upper.paac")), game_upper) if "basic_upper.paac" in files else None
    low = differs(chart(os.path.join(root, "basic_lower.paac")), game_lower) if "basic_lower.paac" in files else None
    want = ([0], ["1_pc/1_phm/" + FIRST + ".paa"], True)
    fails += report(files == sorted(["basic_lower.paac", "basic_upper.paac", FIRST + ".paa", FIRST + "_lod.paa",
                                     FIRST + ".paa_metabin"]) and up == want and low == want,
                    f"sent {files}; upper chart {up}, lower {low}")

    new_clip(arm, SECOND, [(UPPER, 1)])
    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    up = differs(chart(os.path.join(root, "basic_upper.paac")), game_upper)
    fails += report(up == ([0, 1], ["1_pc/1_phm/" + FIRST + ".paa", "1_pc/1_phm/" + SECOND + ".paa"], True),
                    f"a second clip in the same chart: {up}")

    arm.animation_data.action = first
    first["cd_plays"] = [f"{UPPER}#0"]
    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    up = differs(chart(os.path.join(root, "basic_upper.paac")), game_upper)
    # The first clip's path goes out and comes back in after the second's.
    fails += report(not os.path.exists(os.path.join(root, "basic_lower.paac"))
                    and up == ([0, 1], ["1_pc/1_phm/" + SECOND + ".paa", "1_pc/1_phm/" + FIRST + ".paa"], True),
                    f"sent again on the upper node only: basic_lower gone, upper {up}")

    bpy.ops.cd_animator.check_game()
    lines = cd_animator._in_game["charts"]
    fails += report(sorted(lines) == [("basic_upper.paac", FIRST, 1, True), ("basic_upper.paac", SECOND, 1, True)],
                    f"Check the game lists {lines}")

    bpy.ops.cd_animator.remove_from_game(name=FIRST)
    up = differs(chart(os.path.join(root, "basic_upper.paac")), game_upper)
    left_first = [n for n in os.listdir(root) if n.startswith(FIRST)]
    bpy.ops.cd_animator.remove_from_game(name=SECOND)
    left = sorted(os.listdir(root))
    fails += report(up == ([1], ["1_pc/1_phm/" + SECOND + ".paa"], True) and not left_first and left == [],
                    f"took the first out: upper {up}; took the second out: left {left}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
