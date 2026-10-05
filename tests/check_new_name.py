"""Check new clip names: action charts and blends pointed at new clips.

    blender -b --factory-startup --python tests/check_new_name.py -- [game folder]

Needs the game installed; it writes only to a temporary folder that stands
in for the game's bin64. It requires:

  * the chart reader to pack 556 of the game's 558 charts back byte for
    byte, the two it cannot parse being commonactioninfo and its
    _serialized copy, and the blend reader all 1,688 blends;
  * the chart nodes that play Kliff's standing idle to include node 0 of
    basic_upper and of basic_lower, both in action 26107D3C, the upper
    chart's default action, and the uses of his run to include slot 0 of
    the blends basic_move_lv3 and basic_move_lv3_new;
  * Send to game to refuse charts and blends with a loader older than
    0.2.0, which serves files by name only;
  * Where it plays to store the nodes chosen on a new clip;
  * Send to game to write the clip's three files and the two charts under
    by_path at their game paths, each chart the game's with the new path
    added at the end of its clip table and the chosen node on it, every
    other node and the rest of the file unchanged;
  * a second new clip on another node of basic_upper to go into the same
    chart, keeping the first;
  * sending the first again with only its upper node chosen to put its
    lower node back, which leaves basic_lower the game's own, so it is
    deleted;
  * a new run on the two blends to write both under by_path, each the
    game's with only slot 0 changed, though phw_locomotion has a
    basic_move_lv3 of its own;
  * Play on a key to refuse e, which Kliff already uses standing, k, which
    opens the skill view, and a key the game has no name for, and Send to
    game to put a move on L into both charts, with the anger expression
    and a hand clap on frame 15 and the abacus in his left hand by its
    Basic_ChildSocket in basic_lower only, its path and sockets added to
    that chart's tables, the left hand's fingers and Bip_Weapon_L keyed
    once each as the grip clip's first frame has them, after a cup in his
    right hand keyed the cup festival's fingers and weapon bone turn with
    the bone where GRIP_CLIPS puts it,
    after refusing a sound the game lacks, words two sounds match, a frame
    past the clip's end, a prop the game lacks and a cup in his left hand,
    and Blender to show the abacus in his left hand and anger's facial clip
    on his face and put the clap in the timeline on frame 15, which
    clearing the key takes off again, a sound streamed from its own file
    decoding as well and one a plug-in makes refused,
    the move's action last and every action still
    sorted by key, the expression a copy of anger in his facial chart
    under the move's own key, lasting the move, the game's chart
    otherwise, and a second move's copy to go in beside it in key order
    and stay when the first comes out,
    the pointed nodes of basic_upper kept, and the key into the input map
    under by_path;
  * Check the game to list each chart and blend with the clip it plays;
  * a looping move to end on its own branch back into itself, to go
    back to the idle on its own key from 0.13 s in in basic_lower alone,
    to start the happy expression there with the event the game's nodes
    use, first in its node's events, the idle's kept after it, a drum
    beside it and a clap 1 s in, in time order, its sound named by
    hashlittle, all in the same order when the chart is made again, and to
    have the idle's ways out but its end and those into other standing
    idles, the lower chart's walk among them, and to go in again as a
    loop with its expression when a chart is made again; one that travels to have 1 in the low byte at
    0x40 of its node, where the idle's has 0, and to keep it when made
    again; a move's node to last its clip, the speed record 0.1 s more,
    in both charts, though the upper idle's lasts 3 s;
  * every expression of Play on a key to be an action of Kliff's facial
    chart;
  * Take out of the game to take the move out of both charts, his facial
    chart and the input map, leaving basic_upper's pointed nodes and
    deleting the rest;
  * Take out of the game to put a clip's nodes and slots back, and a file
    that then matches the game's to go, leaving the folder empty.

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
from cd_animator import actioncharts, anim, export, ingame, mesh, packs, sounds  # noqa: E402
from cd_animator.formats import motionblend, paac  # noqa: E402
from cd_animator.formats.hashlittle import hashlittle  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
UPPER = actioncharts.CHARTS + "upperaction/1_pc/1_phm/basic_upper.paac"
LOWER = actioncharts.CHARTS + "loweraction/1_pc/1_phm/basic_lower.paac"
RUN = "1_pc/1_phm/cd_phm_basic_00_00_nor_move_run_f_ing_00"
LV3 = actioncharts.BLENDS + "phm_locomotion/basic_move_lv3.motionblending"
LV3_NEW = actioncharts.BLENDS + "phm_locomotion/basic_move_lv3_new.motionblending"
FIRST, SECOND = "cd_phm_cdanim_check_first_00", "cd_phm_cdanim_check_second_00"
RUNNER = "cd_phm_cdanim_check_run_00"
MOVER = "cd_phm_cdanim_check_move_00"


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


def new_clip(arm, name, plays, template=IDLE):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_new_clip(clip=template, clip_name=name, start="MOTION")
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
    blends = actioncharts.blend_paths(idx)
    same = sum(motionblend.write(motionblend.parse(d)) == d for d in (actioncharts.game_bytes(idx, p) for p in blends))
    fails += report(same == len(blends) == 1688, f"blends written back byte for byte: {same} of {len(blends)}")

    uses = actioncharts.uses(idx, IDLE)
    keys = {(p, n): k for p, n, k in uses}
    upper = paac.Chart.parse(actioncharts.game_bytes(idx, UPPER))
    fails += report(keys.get((UPPER, 0)) == 0x26107D3C and keys.get((LOWER, 0)) == 0x26107D3C
                    and upper.default_action_hash == 0x26107D3C,
                    f"the idle plays at {len(uses)} nodes of {len({p for p, _n, _k in uses})} charts, "
                    "node 0 of basic_upper and basic_lower in action 26107D3C")
    run_uses = actioncharts.uses(idx, RUN)
    fails += report((LV3, 0, None) in run_uses and (LV3_NEW, 0, None) in run_uses,
                    f"the run plays at {len(run_uses)} places, slot 0 of basic_move_lv3 and basic_move_lv3_new among them")

    tmp = tempfile.mkdtemp(prefix="cd_newname_")
    b64 = os.path.join(tmp, "bin64")
    os.makedirs(b64)
    loader = os.path.join(b64, ingame.LOADER)
    open(loader, "wb").close()
    ingame.bin64 = lambda context=None: b64
    root = os.path.join(b64, ingame.FOLDER)

    def at(path):
        return os.path.join(root, actioncharts.BY_PATH, *path.split("/"))

    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE")
    arm = bpy.context.view_layer.objects.active
    first = new_clip(arm, FIRST, [(UPPER, 0), (LOWER, 0)])
    fails += report(list(first.get("cd_plays", [])) == [f"{UPPER}#0", f"{LOWER}#0"],
                    f"Where it plays stored {list(first.get('cd_plays', []))}")

    try:
        bpy.ops.cd_animator.send_to_game(clip="ACTION")
        refused = False
    except RuntimeError as exc:
        refused = "0.2.0" in str(exc)
    fails += report(refused and not os.path.exists(at(UPPER)), "a loader older than 0.2.0: charts refused")
    with open(loader, "wb") as f:
        f.write(b"\0MZ [mod] CD Animator Loader 0.2.0 for Crimson Desert 2.03.02 (exe 1.0.0.2976).\0")

    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    files = sorted(n for n in os.listdir(root) if n != actioncharts.BY_PATH)
    game_upper = paac.Chart.parse(actioncharts.game_bytes(idx, UPPER))
    game_lower = paac.Chart.parse(actioncharts.game_bytes(idx, LOWER))
    up = differs(chart(at(UPPER)), game_upper) if os.path.isfile(at(UPPER)) else None
    low = differs(chart(at(LOWER)), game_lower) if os.path.isfile(at(LOWER)) else None
    want = ([0], ["1_pc/1_phm/" + FIRST + ".paa"], True)
    fails += report(files == sorted([FIRST + ".paa", FIRST + "_lod.paa", FIRST + ".paa_metabin"])
                    and up == want and low == want, f"sent {files} and the charts under by_path; upper {up}, lower {low}")

    new_clip(arm, SECOND, [(UPPER, 1)])
    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    up = differs(chart(at(UPPER)), game_upper)
    fails += report(up == ([0, 1], ["1_pc/1_phm/" + FIRST + ".paa", "1_pc/1_phm/" + SECOND + ".paa"], True),
                    f"a second clip in the same chart: {up}")

    arm.animation_data.action = first
    first["cd_plays"] = [f"{UPPER}#0"]
    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    up = differs(chart(at(UPPER)), game_upper)
    # The first clip's path goes out and comes back in after the second's.
    fails += report(not os.path.exists(at(LOWER))
                    and up == ([0, 1], ["1_pc/1_phm/" + SECOND + ".paa", "1_pc/1_phm/" + FIRST + ".paa"], True),
                    f"sent again on the upper node only: basic_lower gone, upper {up}")

    new_clip(arm, RUNNER, [(LV3, 0), (LV3_NEW, 0)], template=RUN)
    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    blend_ok = []
    for path in (LV3, LV3_NEW):
        game = motionblend.parse(actioncharts.game_bytes(idx, path))
        mine = motionblend.parse(open(at(path), "rb").read()) if os.path.isfile(at(path)) else None
        names = mine.root.values["_animationFileNames"] if mine else []
        expect = [("1_pc/1_phm/" + RUNNER + ".paa").encode()] + game.root.values["_animationFileNames"][1:]
        if mine:
            mine.root.values["_animationFileNames"] = game.root.values["_animationFileNames"]
        blend_ok.append(mine is not None and names == expect
                        and motionblend.write(mine) == actioncharts.game_bytes(idx, path))
    fails += report(all(blend_ok), f"the run went into both blends at slot 0, the rest the game's: {blend_ok}")

    mover = new_clip(arm, MOVER, [])
    length = int(mover.frame_end)
    refused = []
    for key in ("e", "k", "nosuchkey"):
        try:
            bpy.ops.cd_animator.play_on_key(key=key)
        except RuntimeError:
            refused.append(key)
    for sound, frame in (("no such sound", 0), ("hand clap", 0), ("sfx_social_hand_clap", length)):
        try:
            bpy.ops.cd_animator.play_on_key(key="l", sound=sound, sound_frame=frame)
        except RuntimeError:
            refused.append(sound)
    try:
        bpy.ops.cd_animator.play_on_key(key="l", prop="no such prop")
    except RuntimeError:
        refused.append("no such prop")
    every = sounds.names(idx)

    def hand(side):
        return {(fc.data_path, fc.array_index): [tuple(k.co) for k in fc.keyframe_points]
                for fc in export._channelbag(arm, mover).fcurves
                if f'"Bip01 {side} Finger' in fc.data_path or f'"Bip_Weapon_{side}"' in fc.data_path}
    # A cup grips as the cup festival's right hand does, and never in his left.
    try:
        bpy.ops.cd_animator.play_on_key(key="l", prop="cd_t0000_cup_0006", hand="LEFT")
    except RuntimeError:
        refused.append("cup in his left hand")
    bpy.ops.cd_animator.play_on_key(key="l", prop="cd_t0000_cup_0006", hand="RIGHT")
    # The festival's fingers and weapon bone turn, that bone where the table puts it for him.
    festival, place = actioncharts.GRIP_CLIPS[("Bip_Weapon_L", (-0.13, -0.049, -0.031))]
    cup = anim.first_pose(arm, packs.fetch_clip(idx, festival))
    cup['pose.bones["Bip_Weapon_R"].location'] = list(place)
    now = hand("R")
    cup_ok = all(len(now[(p, i)]) == 1 and abs(now[(p, i)][0][1] - x) < 1e-6 for p, v in cup.items()
                 if '"Bip01 R Finger' in p or '"Bip_Weapon_R"' in p for i, x in enumerate(v))
    right = hand("R")
    bpy.ops.cd_animator.play_on_key(key="l", face="anger", sound="sfx_social_hand_clap", sound_frame=15,
                                    prop="cd_t0000_abacus_0001", hand="LEFT")
    # The left hand grips as the grip clip's first frame has it, one key a channel; the right is left alone.
    grip = anim.first_pose(arm, packs.fetch_clip(idx, actioncharts.GRIP_CLIP))
    held = [(p, v) for p, v in grip.items() if '"Bip01 L Finger' in p or '"Bip_Weapon_L"' in p]
    left = hand("L")
    grip_ok = [len(held) > 20, hand("R") == right, len(left) == sum(len(v) for _p, v in held),
               all(len(left[(p, i)]) == 1 and abs(left[(p, i)][0][1] - x) < 1e-6 for p, v in held for i, x in enumerate(v))]
    # Blender shows the move as the game will: the abacus in his left hand in place of the cup, anger on his face.
    shown = sorted((o.name.split(".")[0], o.get("cd_socket")) for o in arm.children if o.get("cd_move_prop") == mover.name)
    parts = sorted((mesh.mesh_name(path), "LHand_Socket by its Basic_ChildSocket")
                   for _c, path, _f in packs.prefab(idx, "cd_t0000_abacus_0001"))
    worn = anim.face_action(arm)
    heard = [(s.frame_start, os.path.basename(s.sound.filepath), s.frame_final_duration > 0)
             for s in bpy.context.scene.sequence_editor.strips if s.get("cd_move_sound") == mover.name]
    seen_ok = (shown == parts and worn is not None and worn.get("cd_move_face") == mover.name
               and worn.name.startswith("f_cd_phm_act_anger_00_0001_kliff") and arm.animation_data.action == mover
               and heard == [(15, "sfx_social_hand_clap.ogg", True)])
    # A sound streamed from its own file decodes too, and one a plug-in makes as the game runs is refused.
    streamed = sounds.media(idx, "a_hard_wood_chop")[:4]
    try:
        sounds.media(idx, "explosion")
        made = "played"
    except sounds.SoundError:
        made = "refused"
    seen_ok = seen_ok and streamed == b"RIFF" and made == "refused"
    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    mapped = os.path.join(root, actioncharts.BY_PATH, "ui", "inputmap.xml")
    xml = open(mapped, encoding="utf-8-sig", newline="").read() if os.path.isfile(mapped) else ""
    facial_data = actioncharts.game_bytes(idx, actioncharts.FACIAL_CHART)
    facial = paac.Chart.parse(facial_data)
    face = actioncharts.face_key(facial, MOVER)
    move_ok = []
    for path, game in ((UPPER, game_upper), (LOWER, game_lower)):
        mine = chart(at(path)) if os.path.isfile(at(path)) else None
        keys = [a.key_hash for a in mine.actions] if mine else []
        move_ok.append(mine is not None and keys == sorted(keys) and len(mine.nodes) == len(game.nodes) + 1
                       and actioncharts.moves(mine, game) == [("1_pc/1_phm/" + MOVER, f"key_cda_{MOVER}", False, False, length,
                                                               [(0.0, actioncharts.face_event(face)),
                                                                (0.5, actioncharts.sound_event("sfx_social_hand_clap"))]
                                                               if path == LOWER else [],
                                                               [(0.0, "/character/prefab/6_object/tools/cd_t0000_abacus_0001.prefab",
                                                                 "LHand_Socket", "Basic_ChildSocket")]
                                                               if path == LOWER else [])])
    # The face, a copy of anger under the move's own key lasting the move, and the game's facial chart otherwise.
    mine = chart(at(actioncharts.FACIAL_CHART)) if os.path.isfile(at(actioncharts.FACIAL_CHART)) else None
    copied = mine.find_action(face) if mine else None
    anger = facial.action_nodes(facial.find_action(actioncharts.FACES["anger"]))
    face_ok = (copied is not None and [a.key_hash for a in mine.actions] == sorted(a.key_hash for a in mine.actions)
               and actioncharts.face_chart(mine, facial_data, face).pack() == facial_data
               and [(mine.anim_path(n), n.header.group_hash) for n in mine.action_nodes(copied)]
               == [(facial.anim_path(n), n.header.group_hash) for n in anger]
               and all(abs(n.header.duration - length / 30) < 1e-5
                       and abs(n.animation_speeds[0].time_end - length / 30 - 0.1) < 1e-5 for n in mine.action_nodes(copied)))
    # A second move's face goes in beside it, in key order, and taking the first out leaves the second.
    other = actioncharts.face_key(facial, "cd_phm_cdanim_other_00")
    two = actioncharts.face_chart(mine, facial_data, other, actioncharts.FACES["happy"], 2.0) if mine else None
    one = actioncharts.face_chart(two, facial_data, face) if two else None
    face_ok = (face_ok and [a.key_hash for a in two.actions] == sorted(a.key_hash for a in two.actions)
               and two.find_action(face) and two.find_action(other)
               and one.find_action(other) and not one.find_action(face) and len(one.actions) == len(facial.actions) + 1)
    kept = sorted(c for c, ns in actioncharts.pointed(chart(at(UPPER)), game_upper).items() if ns != [len(game_upper.nodes)])
    fails += report(refused == ["e", "k", "nosuchkey", "no such sound", "hand clap", "sfx_social_hand_clap", "no such prop",
                                "cup in his left hand"]
                    and len(every) > 7000 and "sfx_social_hand_clap" in every
                    and mover.get("cd_key") == "l" and mover.get("cd_face") == "anger"
                    and (mover.get("cd_sound"), mover.get("cd_sound_frame")) == ("sfx_social_hand_clap", 15)
                    and (mover.get("cd_prop"), mover.get("cd_prop_hand")) == ("cd_t0000_abacus_0001", "LEFT")
                    and all(move_ok) and face_ok and all(grip_ok) and cup_ok and seen_ok
                    and kept == ["1_pc/1_phm/" + FIRST, "1_pc/1_phm/" + SECOND]
                    and f'<Input Name="Key_CDA_{MOVER}">\r\n\t\t<KeyboardMouse Key="l" Method="downonce"/>' in xml,
                    f"a move on L: refused {refused}, {len(every)} sounds, charts {move_ok}, its face {face_ok}, "
                    f"left hand gripping {grip_ok}, a cup {cup_ok}, shown {shown} {worn.name if worn else None}, heard {heard}, wood chop {streamed}, explosion {made}, upper keeps {kept}, "
                    f"input map {bool(xml)}")

    bpy.ops.cd_animator.check_game()
    lines = cd_animator._in_game["charts"]
    fails += report(sorted(lines) == [("basic_lower.paac", MOVER, 1, True),
                                      ("basic_move_lv3.motionblending", RUNNER, 1, True),
                                      ("basic_move_lv3_new.motionblending", RUNNER, 1, True),
                                      ("basic_upper.paac", FIRST, 1, True), ("basic_upper.paac", MOVER, 1, True),
                                      ("basic_upper.paac", SECOND, 1, True)],
                    f"Check the game lists {lines}")

    # A loop, straight on the game's charts.
    loop_ok = []
    for path, game in ((UPPER, game_upper), (LOWER, game_lower)):
        data = actioncharts.game_bytes(idx, path)
        c = paac.Chart.parse(data)
        stop = path == actioncharts.STOP_CHART
        added = [(0.0, actioncharts.face_event(actioncharts.FACES["happy"])),
                 (0.0, actioncharts.sound_event("sfx_drum_hit_strong")),
                 (1.0, actioncharts.sound_event("sfx_social_hand_clap"))] if stop else []
        shown = [(0.0, "/character/prefab/6_object/tools/cd_t0000_abacus_0001.prefab", "RHand_Socket", "")] if stop else []
        actioncharts.add_move(c, "1_pc/1_phm/" + MOVER, "key_cda_loop", length, loop=True, travel=True, stop=stop,
                              events=added, props=shown)
        act = c.actions[-1]
        ours = len(game.frame_event_buffer) // 4
        events = c.nodes[act.node_first].frame_event_instances
        idle_events = game.nodes[game.find_action(actioncharts.IDLE).node_first].frame_event_instances
        out = [c.branches[c.slots[i].branch_index] for i in range(act.slot_first, act.slot_first + act.slot_count)]
        idle = c.find_action(actioncharts.IDLE)
        idle_out = [c.branches[c.slots[i].branch_index] for i in range(idle.slot_first + 1, idle.slot_first + idle.slot_count)]
        made = actioncharts._without(c, data, "nothing.paa", path)
        rebuilt = paac.Chart.parse(data)
        for m in actioncharts.moves(paac.Chart.parse(c.pack()), game):
            actioncharts.add_move(rebuilt, m[0], m[1], m[4], m[2], m[3], stop, m[5], m[6])
        again = paac.Chart.parse(c.pack())
        into = next(b for b in c.branches if b.target_hash == act.key_hash and b.keycond_count == 1)
        loop_ok.append(out[-1].kind == 7 and out[-1].target_hash == act.key_hash
                       and not any(b.kind == 7 and b.target_hash != act.key_hash for b in out)
                       and (out[0].kind == 4 and out[0].target_hash == actioncharts.IDLE
                            and out[0].keycond_first == into.keycond_first
                            and abs(c.slots[act.slot_first].time_min - actioncharts.STOP_AFTER) < 1e-6) == stop
                       and not any(b.keycond_count for b in out[stop:])
                       and {b.target_hash for b in out[stop:-1]}
                       == {b.target_hash for b in idle_out if b.kind != 7 and not actioncharts._standing(c, b.target_hash)}
                       and (path == UPPER or 0xFC18618C in {b.target_hash for b in out})
                       and made is None
                       and actioncharts.moves(again, game) == [("1_pc/1_phm/" + MOVER, "key_cda_loop", True, True, length, added,
                                                                 shown)]
                       and [e.ordinal for e in events] == list(range(len(events)))
                       and [e.time for e in events] == sorted(e.time for e in events)
                       and [(e.time, e.event_index) for e in events if e.event_index < ours]
                       == [(e.time, e.event_index) for e in idle_events]
                       and [(e.time, c.frame_event(e.event_index)) for e in events
                            if e.event_index >= ours and c.frame_event(e.event_index)[0] != actioncharts.PROP_EVENT] == added
                       and (not stop or events[0].event_index >= ours
                            and added[2][1][48] == hashlittle(b"sfx_social_hand_clap", 0xC5EDE))
                       and actioncharts.moves(rebuilt, game) == actioncharts.moves(again, game)
                       and again.nodes[act.node_first].header.unk_40 & 0xFF == actioncharts.ROOT_MOTION
                       and game.nodes[game.find_action(actioncharts.IDLE).node_first].header.unk_40 & 0xFF == 0
                       and abs(again.nodes[act.node_first].animation_speeds[0].time_end - (length / 30 + 0.1)) < 1e-4)
    fails += report(all(loop_ok), f"a looping move that travels, upper and lower: {loop_ok}")
    facial = paac.Chart.parse(actioncharts.game_bytes(idx, actioncharts.CHARTS + "upperaction/99_facial/pc_phm_facial.paac"))
    missing = [n for n, k in actioncharts.FACES.items() if not facial.find_action(k)]
    fails += report(not missing, f"every expression is an action of his facial chart, missing {missing}")

    bpy.ops.cd_animator.remove_from_game(name=MOVER)
    up = differs(chart(at(UPPER)), game_upper)
    fails += report(not os.path.exists(at(LOWER)) and not os.path.exists(mapped)
                    and not os.path.exists(at(actioncharts.FACIAL_CHART))
                    and (up[0], sorted(up[1]), up[2]) == ([0, 1], sorted(["1_pc/1_phm/" + FIRST + ".paa",
                                                                          "1_pc/1_phm/" + SECOND + ".paa"]), True),
                    f"took the move out: basic_lower, his facial chart and the input map gone, upper {up}")

    bpy.ops.cd_animator.remove_from_game(name=FIRST)
    up = differs(chart(at(UPPER)), game_upper)
    left_first = [n for n in os.listdir(root) if n.startswith(FIRST)]
    bpy.ops.cd_animator.remove_from_game(name=SECOND)
    bpy.ops.cd_animator.remove_from_game(name=RUNNER)
    left = sorted(os.listdir(root))
    fails += report(up == ([1], ["1_pc/1_phm/" + SECOND + ".paa"], True) and not left_first and left == [],
                    f"took the first out: upper {up}; took the others out: left {left}")
    arm.animation_data.action = mover
    bpy.ops.cd_animator.play_on_key(key="")
    gone = [o.name for o in arm.children if o.get("cd_move_prop")]
    gone += [s.name for s in bpy.context.scene.sequence_editor.strips if s.get("cd_move_sound")]
    fails += report(not gone and anim.face_action(arm) is None,
                    f"clearing the key took off his prop, face and sound: left {gone}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
