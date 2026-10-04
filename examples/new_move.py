"""Give Kliff a new move: press L while standing and he waves.

    blender -b --factory-startup --python examples/new_move.py -- [--send] [out folder]

Four files make it:

  * cd_phm_cdanim_wave_00, a new clip: his standing idle with the right arm
    out to the side, the forearm up and rocking side to side with the palm
    forward, two seconds;
  * basic_upper.paac and basic_lower.paac, each with a new action, CDA_Wave,
    that plays the clip, because the lower layer's moves hide the upper's. It
    is a copy of the idle action (26107D3C) with its own key and node, and its
    one exit is the idle's own end branch, back to idle when the clip ends.
    With all the idle's exits it left again at once: standing still already
    meets some of their conditions. The idle gets one more exit, a branch on
    the key condition key_cda_move1 into CDA_Wave;
  * ui/inputmap.xml with the input Key_CDA_Move1 on L, pressed once, in the
    CharacterAction group.

Each chart's actions stay sorted by key, as every shipped chart's are. Into
out/new_move by default; with --send into the loader's folder, the charts and
input map under by_path.
"""

import copy
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import actioncharts, export, ingame, packs  # noqa: E402
from cd_animator.formats import paac, paz  # noqa: E402
from cd_animator.formats.hashlittle import hashlittle  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
IDLE_CLIP = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
NAME = "cd_phm_cdanim_wave_00"
FRAMES = 60
UPPER = actioncharts.CHARTS + "upperaction/1_pc/1_phm/basic_upper.paac"
IDLE = 0x26107D3C
LOWER = actioncharts.CHARTS + "loweraction/1_pc/1_phm/basic_lower.paac"
ACTION_NAME = "CDA_Wave"
KEY = "key_cda_move1"
INPUT = "Key_CDA_Move1"
INPUTMAP = "ui/inputmap.xml"
H = lambda s: hashlittle(s.encode(), 0xC5EDE)  # noqa: E731


def aim(arm, name, goal):
    """Turn bone `name` about its head so it points along `goal` (world)."""
    pb = arm.pose.bones[name]
    m = pb.matrix.copy()
    head = m.translation.copy()
    turn = (pb.tail - pb.head).normalized().rotation_difference(goal.normalized()).to_matrix().to_4x4()
    new = turn @ Matrix.Translation(-head) @ m
    new.translation = head
    pb.matrix = new
    bpy.context.view_layer.update()


def palm(arm):
    """The right palm's facing (world): pinky to index, crossed with hand to
    fingers. On the idle it points in at the thigh."""
    pb = arm.pose.bones
    w = arm.matrix_world
    across = w @ pb["Bip01 R Finger1"].head - w @ pb["Bip01 R Finger4"].head
    along = w @ pb["Bip01 R Finger2"].head - w @ pb["Bip01 R Hand"].head
    return across.cross(along).normalized()


def roll(arm, name, facing, goal, amount):
    """Turn bone `name` about its own length by `amount` of the angle that
    brings `facing` round to `goal`, both seen across the bone."""
    pb = arm.pose.bones[name]
    axis = (pb.tail - pb.head).normalized()
    a = facing - axis * facing.dot(axis)
    b = goal - axis * goal.dot(axis)
    if a.length < 1e-6 or b.length < 1e-6:
        return
    angle = math.atan2(axis.dot(a.cross(b)), a.dot(b)) * amount
    m = pb.matrix.copy()
    head = m.translation.copy()
    new = Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-head) @ m
    new.translation = head
    pb.matrix = new
    bpy.context.view_layer.update()


def wave(arm):
    """A wave with the right hand: the upper arm out to the side and a little
    above the shoulder, the elbow bent so the forearm stands up, and the
    forearm rocking side to side two and a half times, eased in and out."""
    scene = bpy.context.scene
    up_name, fore_name = "Bip01 R UpperArm", "Bip01 R Forearm"
    side = -1.0 if arm.data.bones[up_name].head_local.x < 0 else 1.0
    for f in range(FRAMES + 1):
        scene.frame_set(f)
        ease = max(0.0, min(1.0, f / 10, (FRAMES - f) / 10))
        ease = ease * ease * (3 - 2 * ease)
        up, fore = arm.pose.bones[up_name], arm.pose.bones[fore_name]
        rest_up = (up.tail - up.head).normalized()
        aim(arm, up_name, rest_up.lerp(Vector((side * 0.8, -0.15, 0.45)).normalized(), ease))
        rest_fore = (fore.tail - fore.head).normalized()
        sway = math.sin(f / FRAMES * 5 * math.pi)
        aim(arm, fore_name, rest_fore.lerp(Vector((side * (0.1 + 0.45 * sway), -0.2, 1.0)).normalized(), ease))
        # The palm forward, to whoever is in front of him; the arm alone
        # leaves it wherever the shortest turn put it.
        forward = (arm.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
        roll(arm, fore_name, palm(arm), forward, ease)
        up.keyframe_insert("rotation_quaternion", frame=f)
        fore.keyframe_insert("rotation_quaternion", frame=f)


def last_name(chart, base):
    """`base`, or `base` with a number, whose key sorts after every action
    of the chart, so adding it moves no action to a new position."""
    top = max(a.key_hash for a in chart.actions)
    n = 0
    while H(f"{base}_{n}" if n else base) <= top:
        n += 1
    return f"{base}_{n}" if n else base


def add_move(chart, clip_path, template_clip):
    """The wave action into `chart`, and the key branch into it on every
    action that plays `template_clip`. Returns the action's name."""
    name = last_name(chart, ACTION_NAME)
    acts = {a.key_hash: a for a in chart.actions}
    idle = acts[IDLE]
    names = chart.strings[0]
    if KEY not in names:
        names.append(KEY)
    token = len(chart.condition_offsets)
    chart.condition_offsets.append(len(chart.condition_words))
    chart.condition_words += [0xE9, names.index(KEY), H(KEY), 0, 0]

    # A plain key exit of this chart to copy: one key token and no other condition.
    template = next(i for i, sl in enumerate(chart.slots)
                    if chart.branches[sl.branch_index].kind == 4 and chart.branches[sl.branch_index].keycond_count == 1
                    and chart.branches[sl.branch_index].cond_count == 0 and sl.filter_count == 0)
    branch = copy.deepcopy(chart.branches[chart.slots[template].branch_index])
    branch.target_hash = H(name)
    branch.target_hash2 = 0
    branch.keycond_first, branch.keycond_count = token, 1
    branch.cond_count = 0
    branch.input_hash = 0
    chart.branches.append(branch)
    slot = copy.deepcopy(chart.slots[template])
    slot.branch_index = len(chart.branches) - 1
    slot.cond_count = slot.filter_count = 0

    # Only the idle's end branch, back to idle: its other exits fire on
    # conditions standing still already meets.
    exits = (next(i for i in range(idle.slot_first, idle.slot_first + idle.slot_count)
                  if chart.branches[chart.slots[i].branch_index].kind == 7), 1)
    want = template_clip.lower() + ".paa"
    standing = [a for a in chart.actions
                if any((chart.anim_path(chart.nodes[i]) or "").lower() == want
                       for i in range(a.node_first, a.node_first + a.node_count))]
    for a in standing:
        moved = [copy.deepcopy(chart.slots[i]) for i in range(a.slot_first, a.slot_first + a.slot_count)]
        a.slot_first, a.slot_count = len(chart.slots), len(moved) + 1
        chart.slots += [copy.deepcopy(slot)] + moved

    node = copy.deepcopy(chart.nodes[idle.node_first])
    chart.strings[1].append(clip_path + ".paa")
    node.header.anim_index = node.header.anim_index_a = len(chart.strings[1]) - 1
    chart.nodes.append(node)
    act = idle.copy()
    act.key_hash = H(name)
    act.node_first, act.node_count = len(chart.nodes) - 1, 1
    act.slot_first, act.slot_count = exits
    chart.actions.append(act)
    print(f"{name} ({H(name):08X}) after every action; the key branch on {len(standing)} actions")
    return name


def add_input(xml):
    """The input map with Key_CDA_Move1 on L in the CharacterAction group."""
    group = '<InputGroup Name="CharacterAction" LayerName="Action" EnableConsume="False">'
    if INPUT in xml:
        return xml
    entry = f'\r\n\t<Input Name="{INPUT}">\r\n\t\t<KeyboardMouse Key="l" Method="downonce"/>\r\n\t</>'
    assert group in xml
    return xml.replace(group, group + entry, 1)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    send = "--send" in argv
    # --key=key_interaction tries a key the game already has, without the input map.
    global KEY
    key = next((a.split("=", 1)[1] for a in argv if a.startswith("--key=")), None)
    KEY = key or KEY
    rest = [a for a in argv if a != "--send" and not a.startswith("--key=")]
    out = rest[0] if rest else os.path.join(ROOT, "out", "new_move")
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE")
    arm = bpy.context.view_layer.objects.active
    idx = packs.index()
    bpy.ops.cd_animator.game_new_clip(clip=IDLE_CLIP, clip_name=NAME, frames=FRAMES, start="MOTION")
    action = arm.animation_data.action
    wave(arm)
    folder = ingame.folder() if send else out
    if send:
        ingame.need_by_path()
    os.makedirs(folder, exist_ok=True)
    if send:
        _n, written, _p = ingame.send(arm, action, folder)
    else:
        written, _p = export.export_with_companions(arm, action, os.path.join(folder, NAME + ".paa"))
    # Both layers: the lower layer's moves, a jump among them, hide the upper's.
    charts = []
    for path in (UPPER, LOWER):
        chart = paac.Chart.parse(actioncharts.game_bytes(idx, path))
        add_move(chart, actioncharts.new_path(action, NAME), IDLE_CLIP)
        data = chart.pack()
        assert paac.Chart.parse(data).pack() == data
        charts.append((path, data))
    xml_entry = next(e for e in paz.read_index(os.path.join(idx.folder, "0012", "0.pamt"), {"xml"})
                     if e.path.lower() == INPUTMAP)
    xml = add_input(paz.read(xml_entry).decode("utf-8-sig"))
    files = charts + ([] if key else [(INPUTMAP, ("\ufeff" + xml).encode("utf-8"))])
    for path, blob in files:
        target = os.path.join(folder, actioncharts.BY_PATH, *path.split("/")) if send else \
            os.path.join(folder, path.rsplit("/", 1)[-1])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(blob)
        written.append(target)
    print("wrote", ", ".join(os.path.basename(w) for w in written), "to", folder)
    sys.stdout.flush()
    os._exit(0)


main()
