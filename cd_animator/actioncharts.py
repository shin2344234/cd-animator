"""Point the game's action charts and blends at clips under new names.

A clip under a name no pack has plays only if a chart or a blend names it.
An action chart (formats/paac.py) names each clip a node plays by an index
into its table of clip paths, so pointing a node at a new clip means adding
the new path to that table and setting the node's index to it. Nothing else
in the chart moves: no node is added or removed, and the game's own paths
keep their indexes. A blend (formats/motionblend.py) lists the clips it
mixes, each once, and its examples name them by index, so a slot of that
list gets the new path in place of the old and the list keeps its length.
A blend plays wherever a chart node names it.

The loader serves most files by name, but a file under by_path in its
folder at the game's path for it goes in for that path only (loader 0.2.0
and later). Blend names are unique but for 44 of the 1,688, the male and
female versions of a blend among them, so every edited chart and blend
goes there, and the game reads it in place of its own at the next start. Several new clips can share one file: each send
starts from the copy already in the folder. Taking a clip out puts its
nodes and slots back on the game's clips, and deletes the copy once it
matches the game's again.

A move is a new action in Kliff's two charts, basic_upper and basic_lower,
that plays a new clip when a key is pressed while he stands: a copy of his
standing idle with its own node, whose one exit is the idle's end branch,
back to idle when the clip ends. Every action that plays his idle clip
gets a branch into it on the key's condition, and the input map
(ui/inputmap.xml) gets the key's input. Both layers need it, as the lower
layer's moves hide the upper's. The game keeps every chart's actions
sorted by key, so the move's name is one whose key sorts last. A move
can loop instead, an emote until he moves: its end branch points back at
itself, as the upper idle's does, and it takes the idle's other ways out
but those into the sand, cliff and alert idles. The game starts walks,
jumps and attacks from outside the idle's exits, so those end it too.
Taking a move or a pointed clip out of a chart makes the chart again from
the game's, with what stays.

A move can start one of his faces too. Its node gets the frame event his
meditation closes his eyes with, naming a copy of the face in his facial
chart that lasts the move, or a loop's round and a little, since a face
otherwise plays its own 16 s whatever the body does. It can play one of
the game's sounds, with the frame event his evade plays its whoosh with,
and show a prop in his hand, as his abacus idle shows the abacus.

Action names are hashes. The names table of a chart (strings[0]) holds the
names of other things, so 136 of the game's 84,133 actions have a name
anywhere in the game; an action is shown by its key instead.
"""
import bisect
import copy
import json
import os
import re
import struct
from struct import error as struct_error

from . import packs
from .anim import FPS
from .formats import motionblend, paac, paz
from .formats.hashlittle import hashlittle

BY_PATH = "by_path"
CHARTS = "actionchart/bin__/"
SUFFIX = ".paac"
BLENDS = "character/binary/motionblending/"
BLEND_SUFFIX = ".motionblending"
MOVE_CHARTS = (CHARTS + "upperaction/1_pc/1_phm/basic_upper.paac", CHARTS + "loweraction/1_pc/1_phm/basic_lower.paac")
# A loop's key stops it in the lower chart only, whose clip shows. Each layer takes keys from its own idle, so with
# a stop in both, a press while one layer was still busy flipped the two out of step and left the upper in its
# idle under a dance, where its idle's variations pulled the lower layer out of it, as with no upper copy at all.
STOP_CHART = MOVE_CHARTS[1]
MOVE_FOLDER = "1_pc/1_phm/"            # clips Kliff's skeleton plays
IDLE_CLIP = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
IDLE = 0x26107D3C                      # his standing idle, in both charts
LOOP_BLEND = 6.0                       # a loop's blend into its own start, as the lower idle's end branch has
# The low byte of a node's word at 0x40, 1 when the game moves the character by the clip's B_MoveControl_01: the
# dodge roll, the dash and the step back have it. The idle has 0, which leaves movement to move speed records.
ROOT_MOTION = 0x01
STOP_AFTER = 0.13                      # s into a loop before its key stops it, the shortest wait of the game's key slots
# Kliff's expressions, actions of his facial chart by the game's names for them. No branch leads into that chart. A
# body node's frame event of type 0x40 starts one of its actions, as his meditation closes his eyes and his roar
# angers him. A face plays its node's duration, about 16 s for most, unless another starts, and then his resting
# face comes back. Starting the one already playing starts it over.
FACIAL_CHART = CHARTS + "upperaction/99_facial/pc_phm_facial.paac"
FACE_EVENT = 0x40
# A node's frame event of type 0x41 plays one of the game's sounds, a Wwise event its bank info names, by
# hashlittle of the name at word 48. 3,724 of those in Kliff's charts set no other word but these.
SOUND_EVENT = 0x41
# A frame event of type 0x3D shows a prop. Word 2 holds the prefab's place in the chart's prefab table (strings[9])
# and, above it, the socket's in the bone table (strings[6]), and word 3's low half the place of the prop's own
# socket that goes on it, its grip, 0xFFFF for none. His writing idle's start and loop nodes show theirs in mode 0,
# while their node plays; its end node shows them in mode 2 and hides them in mode 1 at 1.83 s.
PROP_EVENT = 0x3D
HANDS = {"RIGHT": "RHand_Socket", "LEFT": "LHand_Socket"}
GRIP = "Basic_ChildSocket"             # the grip 285 of the game's prop events name, its festival cups' among them
# A clip whose first frame grips with both hands at their sockets, a sword in each. Its fingers curl a mean 20.9
# degrees from bind, up to 64.9, where his idle's curl 5.0, and Bip_Weapon_R and _L sit 6.3 and 6.2 cm from bind.
GRIP_CLIP = "1_pc/1_phm/cd_phm_dualsword_01_01_stand_idle_000"
# Grips that clip holds wrong, by the grip's parent bone and place in metres, each with a clip whose first frame holds
# a prop by it in the right hand, the only hand the game holds them in, and the location Kliff's Bip_Weapon_R takes
# for it. The game's cups and spoon_0003 grip on Bip_Weapon_L, 13 cm off the hand's socket. At the cup festival the
# right weapon bone turns 98 degrees and moves 12.6 cm, closing the fist on the handle, where the dual-sword idle's
# turns 18 degrees and leaves the cup around his wrist. Mirrored onto the left hand, that pose leaves the cup 13 cm
# off the palm, as the grip is off to one side. The festival's characters stand at 0.8 of the skeleton and Kliff at
# 1.026, and the bone's offset, the socket and the cup grow with that scale while the fingers keep their size, so on
# him the clip's own location leaves the cup 4.6 cm off his palm. Its location here is solved in Blender with both
# built at their own proportions, putting his fist where the festival character's sits on the cup.
GRIP_CLIPS = {("Bip_Weapon_L", (-0.13, -0.049, -0.031)):
              ("1_pc/7_pdm/01_npc/cd_ss00075_062_pdmcupfestival_1act_pdm1_ing_00", (0.03222, -0.09381, -0.05845))}
FACE_AFTER = 0.5                       # s a loop's face outlasts a round, so the next round starts it over first
FACES = {"happy": 0xA3557CFE, "anger": 0x0DC86234, "sadness": 0x2DA58C98, "fear": 0xDEEA3A8A,
         "eyes_closed": 0xD4F119D0, "whistle": 0x63A43B71, "crowd": 0x3CA96A65, "crowd_happy": 0x35ED3BB7,
         "crowd_anger": 0xA361BDCB, "crowd_sadness": 0x79C5509E, "battle": 0x80DAC573, "attack": 0x9CB4F219,
         "hurt": 0xD6683A1D, "win": 0x86127453, "win_2": 0xA1881D5B, "win_3": 0x7F271370, "gamble": 0xA5B06B28,
         "cheat": 0xE6C841D9, "wait": 0x175AC98C, "swim": 0x9E780E5A, "dead": 0x8854ED68}
INPUTMAP = "ui/inputmap.xml"
INPUTMAPS = (INPUTMAP, "ui/inputmap_common.xml")   # the second has the menus' keys, the skill view's K among them
_GROUP = '<InputGroup Name="CharacterAction" LayerName="Action" EnableConsume="False">'


class ChartError(Exception):
    pass


def chart_paths(idx):
    if getattr(idx, "_chart_paths", None) is None:
        idx._chart_paths = sorted(p for p in idx.by_path if p.startswith(CHARTS) and p.endswith(SUFFIX))
    return idx._chart_paths


def blend_paths(idx):
    if getattr(idx, "_blend_paths", None) is None:
        idx._blend_paths = sorted(p for p in idx.by_path if p.startswith(BLENDS) and p.endswith(BLEND_SUFFIX))
    return idx._blend_paths


def is_blend(path):
    return path.lower().endswith(BLEND_SUFFIX)


def chart_name(path):
    return path.rsplit("/", 1)[-1]


def short(path):
    """A chart's path as the game's charts name it, such as
    upperaction/1_pc/1_phm/basic_upper, or a blend's under
    motionblending/, such as phm_locomotion/basic_move_walk."""
    if is_blend(path):
        return path[len(BLENDS):-len(BLEND_SUFFIX)]
    return path[len(CHARTS):-len(SUFFIX)]


def _by_name(idx):
    """{file name: path} of the charts and blends whose name is the game's
    only file of that name, which 0.22.0 put in the folder by name."""
    if getattr(idx, "_files_by_name", None) is None:
        names = {}
        for p in chart_paths(idx) + blend_paths(idx):
            names.setdefault(chart_name(p), []).append(p)
        idx._files_by_name = {n: ps[0] for n, ps in names.items() if len(ps) == 1}
    return idx._files_by_name


def game_bytes(idx, path):
    return paz.read(idx.by_path[path])


def _table(chart):
    return chart.strings[1]


class _Blend:
    """A blend with the add-on's view of it: its clip list as text."""

    def __init__(self, data):
        self.mb = motionblend.parse(data)
        self.clips = [c.decode("ascii") for c in self.mb.root.values.get("_animationFileNames", [])]

    def pack(self):
        self.mb.root.values["_animationFileNames"] = [c.encode("ascii") for c in self.clips]
        return motionblend.write(self.mb)


def _parse(path, data):
    return _Blend(data) if is_blend(path) else paac.Chart.parse(data)


def _uses_file(idx):
    stamp = "_".join(str(int(t)) for t in idx.stamp)
    return os.path.join(packs.cache_root(), f"clip_uses_{stamp}.json")


def _all_uses(idx):
    """{"clips": {clip path under character/motion/ without .paa, lower
    case: [[chart path, node, action key] or [blend path, slot, None]]},
    "blends": {blend path: chart nodes that name it}} for every chart the
    reader parses and every blend."""
    if getattr(idx, "_chart_uses", None) is not None:
        return idx._chart_uses
    path = _uses_file(idx)
    try:
        with open(path, encoding="utf-8") as f:
            idx._chart_uses = json.load(f)
        return idx._chart_uses
    except (OSError, ValueError):
        pass
    clips, blends = {}, {}
    for p in chart_paths(idx):
        try:
            c = paac.Chart.parse(game_bytes(idx, p))
        except paac.ParseError:
            continue
        owner = {}
        for a in c.actions:
            for i in range(a.node_first, a.node_first + a.node_count):
                owner[i] = a.key_hash
        table = _table(c)
        for i, n in enumerate(c.nodes):
            k = n.header.anim_index
            if k < len(table) and table[k].lower().endswith(".paa"):
                clips.setdefault(table[k][:-4].lower(), []).append([p, i, owner.get(i, 0)])
            for b in {n.header.blend_index_a, n.header.blend_index_b}:
                if b < len(c.strings[5]):
                    name = c.strings[5][b].lower()
                    blends[name] = blends.get(name, 0) + 1
    for p in blend_paths(idx):
        try:
            b = _Blend(game_bytes(idx, p))
        except (motionblend.FormatError, struct_error, UnicodeDecodeError):
            continue
        for i, c in enumerate(b.clips):
            if c.lower().endswith(".paa"):
                clips.setdefault(c[:-4].lower(), []).append([p, i, None])
    idx._chart_uses = {"clips": clips, "blends": blends}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(idx._chart_uses, f)
    except OSError:
        pass
    return idx._chart_uses


def uses(idx, clip):
    """[(chart path, node, action key)] of every chart node that plays
    `clip`, a path under character/motion/ without .paa, then [(blend
    path, slot, None)] of every blend that mixes it."""
    return [tuple(u) for u in _all_uses(idx)["clips"].get(clip.lower(), [])]


def blend_users(idx, path):
    """How many chart nodes name the blend at `path`."""
    return _all_uses(idx)["blends"].get(path.lower(), 0)


def template_clip(action):
    """The game clip a new clip was started from, as a path under
    character/motion/, or None when it came from a file elsewhere."""
    t = action.get("cd_template")
    if not t:
        return None
    return packs.cached_clip(t)


def new_path(action, name):
    """The path under character/motion/ the charts give a new clip: the
    template's folder and the new name."""
    t = template_clip(action)
    folder = t.rsplit("/", 1)[0] + "/" if t and "/" in t else ""
    return folder + name


def point(chart, nodes, clip):
    """Point `nodes` of `chart` at `clip` (under character/motion/, no
    .paa), adding its path to the chart's clip table if it is not there.
    For a blend, `nodes` are slots of its clip list, which take the new
    path in place of the old."""
    want = clip + ".paa"
    if isinstance(chart, _Blend):
        for i in nodes:
            if not 0 <= i < len(chart.clips):
                raise ChartError(f"the blend has no clip {i}")
            chart.clips[i] = want
        return
    table = _table(chart)
    low = [s.lower() for s in table]
    if want.lower() in low:
        k = low.index(want.lower())
    else:
        k = len(table)
        if k > 0xFFFF:
            raise ChartError(f"the chart's clip table is full ({k} paths)")
        if len(want) + 1 > 255:
            raise ChartError(f"{want} is longer than a chart path may be")
        chart.strings[1].append(want)
    for i in nodes:
        if not 0 <= i < len(chart.nodes):
            raise ChartError(f"the chart has no node {i}")
        h = chart.nodes[i].header
        h.anim_index = k
        h.anim_index_a = k


def unpoint(chart, game, clip):
    """Put every node of `chart` that plays `clip` back on the clip the
    game's chart `game` gives it, then drop added paths no node plays.
    Returns the nodes put back; for a blend, the slots."""
    want = (clip + ".paa").lower()
    if isinstance(chart, _Blend):
        back = [i for i, c in enumerate(chart.clips) if c.lower() == want and c != game.clips[i]]
        for i in back:
            chart.clips[i] = game.clips[i]
        return back
    low = [s.lower() for s in _table(chart)]
    back = []
    for i, n in enumerate(chart.nodes):
        k = n.header.anim_index
        if k < len(low) and low[k] == want:
            g = game.nodes[i].header
            n.header.anim_index = g.anim_index
            n.header.anim_index_a = g.anim_index_a
            back.append(i)
    used = {n.header.anim_index for n in chart.nodes} | {n.header.anim_index_a for n in chart.nodes}
    keep = len(game.strings[1])
    for k in range(len(chart.strings[1]) - 1, keep - 1, -1):
        if k in used:
            continue
        del chart.strings[1][k]
        for n in chart.nodes:
            if n.header.anim_index > k:
                n.header.anim_index -= 1
            if n.header.anim_index_a > k:
                n.header.anim_index_a -= 1
    return back


def pointed(chart, game):
    """{clip path under character/motion/ without .paa: [nodes]} of the
    nodes in `chart` that play a clip other than the game's chart's; for a
    blend, its slots."""
    out = {}
    if isinstance(chart, _Blend):
        for i, (c, g) in enumerate(zip(chart.clips, game.clips)):
            if c.lower() != g.lower():
                out.setdefault(c[:-4] if c.lower().endswith(".paa") else c, []).append(i)
        return out
    table, gtable = _table(chart), _table(game)
    for i, (n, g) in enumerate(zip(chart.nodes, game.nodes)):
        k, gk = n.header.anim_index, g.header.anim_index
        if k < len(table) and (gk >= len(gtable) or table[k].lower() != gtable[gk].lower()):
            out.setdefault(table[k][:-4] if table[k].lower().endswith(".paa") else table[k], []).append(i)
    for i in range(len(game.nodes), len(chart.nodes)):
        k = chart.nodes[i].header.anim_index
        if k < len(table):
            out.setdefault(table[k][:-4] if table[k].lower().endswith(".paa") else table[k], []).append(i)
    return out


def _hash(name):
    return hashlittle(name.encode(), 0xC5EDE)


def input_name(clip):
    """The input a move's key raises, from its clip's name."""
    return "Key_CDA_" + clip.rsplit("/", 1)[-1]


def _last_name(chart, base):
    """`base` with a number whose key sorts after every action of the chart."""
    # ponytail: each move halves the room left above the top key, so the
    # search doubles per move; fine to a dozen or so moves a chart.
    top = max(a.key_hash for a in chart.actions)
    n = 0
    while _hash(f"{base}_{n}") <= top:
        n += 1
    return f"{base}_{n}"


def _standing(chart, key):
    """True when action `key` of `chart` is a standing idle, such as the
    sand, cliff or alert idle Kliff's idle turns into where he stands."""
    for a in chart.actions:
        if a.key_hash == key and a.node_count:
            return "_std_idle" in (chart.anim_path(chart.nodes[a.node_first]) or "").lower()
    return False


def face_event(key):
    """The words of the frame event that starts facial action `key`, as
    the game's nodes start theirs, its blends 0.3333 s."""
    return [FACE_EVENT, 0x20000, 0, key, 0x3EAAA64C, 0x3EAAA64C, 1]


def sound_event(name):
    """The words of the frame event that plays the game's sound `name`."""
    words = [0] * 58
    words[0], words[48], words[52], words[54], words[55], words[57] = (
        SOUND_EVENT, _hash(name.lower()), 0xBF800000, 0x10000, 0xFFFF0000, 0x50000)
    return words


def prop_path(path):
    """The path a chart names a prefab by, which is its game path with a
    leading slash and no bin__ folder."""
    return "/" + path.replace("/bin__/", "/", 1)


def _place(table, text):
    """`text`'s place in a chart's string table, added at the end if the
    table lacks it."""
    low = [t.lower() for t in table]
    if text.lower() in low:
        return low.index(text.lower())
    if len(table) >= 0xFFFF or len(text) + 1 > 255:
        raise ChartError(f"the chart has no room for {text}")
    table.append(text)
    return len(table) - 1


def _add_event(chart, node, seconds, words):
    """Give `node` the frame event `words` at `seconds`, before its others
    at that time. Every node of the game keeps its events sorted by time
    and numbered in order."""
    event = paac.Rec(paac.LAYOUTS["FrameEventInstance"])
    event.time, event.time_end, event.unk_10 = seconds, -1.0, 0xFFFFFFFF
    event.event_index = len(chart.frame_event_buffer) // 4
    chart.frame_event_buffer += struct.pack("<%dI" % len(words), *words)
    events = node.frame_event_instances
    events.insert(bisect.bisect_left([e.time for e in events], seconds), event)
    for i, e in enumerate(events):
        e.ordinal = i


def add_move(chart, clip, key, frames, loop=False, travel=False, stop=True, events=(), props=()):
    """Add to `chart` a move that plays `clip` (under character/motion/, no
    .paa), `frames` long, on the key condition `key`, an input name in lower
    case, with a branch into it on every action that plays Kliff's idle. A
    move that loops plays its clip again at the end, until its key is
    pressed again, with `stop`, or one of the idle's ways out but into
    another standing idle fires, his walk among them. A move that travels moves him as the
    clip's B_MoveControl_01 goes. `events`, [(seconds, words)], go on
    the move's node, its face and its sound, and `props`, [(seconds,
    prefab path as charts name it, socket, the prefab's own socket that
    goes on it or "")], show those props while it plays."""
    acts = {a.key_hash: a for a in chart.actions}
    if IDLE not in acts:
        raise ChartError("the chart has no standing idle to start a move from")
    idle = acts[IDLE]
    name = _last_name(chart, "CDA_Move")
    names = chart.strings[0]
    if key not in names:
        names.append(key)
    token = len(chart.condition_offsets)
    chart.condition_offsets.append(len(chart.condition_words))
    chart.condition_words += [0xE9, names.index(key), _hash(key), 0, 0]

    # The key branch, from a plain key exit of this chart: one key token and no other condition.
    def plain(sl):
        b = chart.branches[sl.branch_index]
        return b.kind == 4 and b.keycond_count == 1 and b.cond_count == 0 and sl.filter_count == 0
    template = next(i for i, sl in enumerate(chart.slots) if plain(sl))
    branch = copy.deepcopy(chart.branches[chart.slots[template].branch_index])
    branch.target_hash, branch.target_hash2 = _hash(name), 0
    branch.keycond_first, branch.keycond_count = token, 1
    branch.cond_count = 0
    branch.input_hash = 0
    chart.branches.append(branch)
    slot = copy.deepcopy(chart.slots[template])
    slot.branch_index = len(chart.branches) - 1
    slot.cond_count = slot.filter_count = 0

    # Only the idle's end branch out: standing still meets some of its other exits' conditions at once.
    end = next(i for i in range(idle.slot_first, idle.slot_first + idle.slot_count)
               if chart.branches[chart.slots[i].branch_index].kind == 7)
    # A loop's ways out, taken before the idle's slots move: the idle's own, but its end, those into the
    # other standing idles, which fire from the ground he stands on, and other moves' keys.
    ways_out = [copy.deepcopy(chart.slots[i]) for i in range(idle.slot_first, idle.slot_first + idle.slot_count)
                if chart.branches[chart.slots[i].branch_index].kind != 7
                and not chart.branches[chart.slots[i].branch_index].keycond_count
                and not _standing(chart, chart.branches[chart.slots[i].branch_index].target_hash)]
    want = IDLE_CLIP + ".paa"
    for a in chart.actions:
        if any((chart.anim_path(chart.nodes[i]) or "").lower() == want
               for i in range(a.node_first, a.node_first + a.node_count)):
            moved = [copy.deepcopy(chart.slots[i]) for i in range(a.slot_first, a.slot_first + a.slot_count)]
            a.slot_first, a.slot_count = len(chart.slots), len(moved) + 1
            chart.slots += [copy.deepcopy(slot)] + moved

    node = copy.deepcopy(chart.nodes[idle.node_first])
    # A node ends its action at its duration or the clip's end, whichever comes first. The game's nodes mostly
    # last their clip, with the speed record 0.1 s longer; the upper idle's 3 s cut longer moves short.
    node.header.duration = frames / FPS
    for r in node.animation_speeds:
        r.time_end = frames / FPS + 0.1
    if travel:
        node.header.unk_40 = node.header.unk_40 & ~0xFF | ROOT_MOTION
    # Last first, as each goes before the node's others at its time, so they keep their order through a rebuild.
    for seconds, words in reversed(events):
        _add_event(chart, node, seconds, words)
    for seconds, prefab, socket, grip in reversed(props):
        where = _place(chart.strings[6], socket) << 16 | _place(chart.strings[9], prefab)
        held = 0xFFFF0000 | _place(chart.strings[6], grip) if grip else 0xFFFFFFFF
        _add_event(chart, node, seconds, [PROP_EVENT, 0, where, held, 0x0101FFFF])
    chart.nodes.append(node)
    point(chart, [len(chart.nodes) - 1], clip)
    act = idle.copy()
    act.key_hash = _hash(name)
    act.node_first, act.node_count = len(chart.nodes) - 1, 1
    act.slot_first, act.slot_count = end, 1
    if loop:
        # The idle's end branch, pointed back at the move, as the upper idle's points at the idle.
        again = copy.deepcopy(chart.branches[chart.slots[end].branch_index])
        again.target_hash, again.target_hash2 = act.key_hash, 0
        again.time_a = LOOP_BLEND
        chart.branches.append(again)
        last = copy.deepcopy(chart.slots[end])
        last.branch_index = len(chart.branches) - 1
        act.slot_first, act.slot_count = len(chart.slots), len(ways_out) + 1
        if stop:
            # Its key again stops it, blending into the idle as the idle's end does, but not straight away, so the
            # press that started it cannot.
            halt = copy.deepcopy(branch)
            halt.target_hash, halt.target_hash2 = IDLE, 0
            halt.time_a = LOOP_BLEND
            chart.branches.append(halt)
            out = copy.deepcopy(slot)
            out.branch_index = len(chart.branches) - 1
            out.time_min = STOP_AFTER
            ways_out.insert(0, out)
            act.slot_count += 1
        chart.slots += ways_out + [last]
    chart.actions.append(act)


def face_key(facial, clip):
    """The key of the facial action a move playing `clip` starts: a name
    of the clip's own whose key sorts after every action of the game's
    facial chart `facial`."""
    top = max(a.key_hash for a in facial.actions)
    leaf = clip.rsplit("/", 1)[-1].lower()
    n = 0
    while _hash(f"CDA_Face_{leaf}_{n}") <= top:
        n += 1
    return _hash(f"CDA_Face_{leaf}_{n}")


def face_chart(chart, game_data, key, face=0, seconds=0.0):
    """The facial chart made again from the game's, `game_data`, with the
    actions `chart` adds but `key`, and with `face`, a copy of that game
    action under `key` lasting `seconds`, so the expression ends with the
    move. The game keeps a chart's actions sorted by key, and in this one
    nothing names an action by its place."""
    new = paac.Chart.parse(game_data)
    known = {a.key_hash for a in new.actions}
    added = [(a, chart.action_nodes(a)) for a in chart.actions if a.key_hash not in known and a.key_hash != key]
    if face:
        act = new.find_action(face)
        if act is None:
            raise ChartError(f"his facial chart has no action {face:08X}")
        nodes = [copy.deepcopy(n) for n in new.action_nodes(act)]
        for n in nodes:
            n.header.duration = seconds
            for r in n.animation_speeds:
                r.time_end = seconds + 0.1
        act = act.copy()
        act.key_hash = key
        added.append((act, nodes))
    for act, nodes in added:
        act = act.copy()
        act.node_first, act.node_count = len(new.nodes), len(nodes)
        new.nodes += [copy.deepcopy(n) for n in nodes]
        new.actions.append(act)
    new.actions.sort(key=lambda a: a.key_hash)
    return new


def _added(chart, game, node):
    """([(seconds, words)], [(seconds, prefab, socket, grip)]) of the frame
    events `node` has beyond the game's, those whose words lie past the
    game's own, its props apart."""
    first = len(game.frame_event_buffer) // 4
    events, props = [], []
    for e in node.frame_event_instances:
        words = chart.frame_event(e.event_index) if e.event_index >= first else None
        if words and words[0] & 0xFFFF == PROP_EVENT:
            grip = words[3] & 0xFFFF
            props.append((e.time, chart.strings[9][words[2] & 0xFFFF], chart.strings[6][words[2] >> 16],
                          chart.strings[6][grip] if grip != 0xFFFF else ""))
        elif words:
            events.append((e.time, words))
    return events, props


def moves(chart, game):
    """[(clip, key, loop, travel, frames, events, props)] of the moves in
    `chart`, the actions the game's chart `game` lacks, in the order they
    went in."""
    known = {a.key_hash for a in game.actions}
    out = []
    for a in chart.actions:
        if a.key_hash in known:
            continue
        clip = chart.anim_path(chart.nodes[a.node_first]) or ""
        b = next(b for b in chart.branches if b.target_hash == a.key_hash and b.keycond_count == 1)
        o = chart.condition_offsets[b.keycond_first]
        loop = any(chart.branches[chart.slots[i].branch_index].kind == 7
                   and chart.branches[chart.slots[i].branch_index].target_hash == a.key_hash
                   for i in range(a.slot_first, a.slot_first + a.slot_count))
        out.append((clip[:-4] if clip.lower().endswith(".paa") else clip,
                    chart.strings[0][chart.condition_words[o + 1]], loop,
                    bool(chart.nodes[a.node_first].header.unk_40 & ROOT_MOTION),
                    round(chart.nodes[a.node_first].header.duration * FPS), *_added(chart, game, chart.nodes[a.node_first])))
    return out


def _leaf(clip):
    return clip.rsplit("/", 1)[-1].lower() + ".paa"


def _without(chart, game_data, leaf, path):
    """`chart` made again from the game's, with its moves and pointed nodes
    but those whose clip file is `leaf`, or None when none is."""
    game = paac.Chart.parse(game_data)
    mine = moves(chart, game)
    points = {c: [n for n in ns if n < len(game.nodes)] for c, ns in pointed(chart, game).items()}
    points = {c: ns for c, ns in points.items() if ns}
    if leaf not in {_leaf(m[0]) for m in mine} | {_leaf(c) for c in points}:
        return None
    new = paac.Chart.parse(game_data)
    for c, k, loop, travel, frames, events, props in mine:
        if _leaf(c) != leaf:
            add_move(new, c, k, frames, loop, travel, path == STOP_CHART, events, props)
    for c, ns in points.items():
        if _leaf(c) != leaf:
            point(new, ns, c)
    return new


def _game_xml(idx, path):
    cache = idx.__dict__.setdefault("_xml", {})
    if path not in cache:
        entry = next(e for e in paz.read_index(os.path.join(idx.folder, "0012", "0.pamt"), {"xml"})
                     if e.path.lower() == path)
        cache[path] = paz.read(entry).decode("utf-8-sig")
    return cache[path]


def game_inputmap(idx):
    return _game_xml(idx, INPUTMAP)


def _keys(xml):
    """Every keyboard and mouse key name in an input map."""
    return {k for ks in re.findall(r'<KeyboardMouse\b[^<>]*\bKey="([^"]+)"', xml) for k in ks.split()}


def bound_keys(idx):
    """{keyboard key: an input of the game's on it}, from both input maps.
    A Key of four names or more is a row of the keyboard, such as
    "f g h j k l ; &quot;", not a binding."""
    out = {}
    for path in INPUTMAPS:
        xml = _game_xml(idx, path)
        inputs = [(m.start(), m.group(1)) for m in re.finditer(r'<Input Name="([^"]+)"', xml)]
        starts = [i for i, _n in inputs]
        for m in re.finditer(r'<KeyboardMouse\b[^<>]*\bKey="([^"]+)"', xml):
            keys = m.group(1).split()
            if len(keys) <= 3:
                at = bisect.bisect_right(starts, m.start()) - 1
                for k in keys:
                    out.setdefault(k, inputs[at][1] if at >= 0 else "something")
    return out


def free_keys(idx):
    """The keyboard keys the game names but binds to nothing."""
    every = set().union(*(_keys(_game_xml(idx, p)) for p in INPUTMAPS))
    return sorted(k for k in every - set(bound_keys(idx)) if k.isalnum())


def face_clip(idx, key):
    """The clip the game's facial action `key` plays on Kliff's face, a
    path under character/motion/ with no extension, from the action's
    first node for him, group 0. Some actions have several and the game
    picks one."""
    chart = paac.Chart.parse(game_bytes(idx, FACIAL_CHART))
    node = next(n for n in chart.action_nodes(chart.find_action(key)) if n.header.group_hash == 0)
    return chart.anim_path(node)[:-len(".paa")]


def check_key(idx, key):
    """Refuse a key the game has no name for, or one it already binds."""
    free = ", ".join(free_keys(idx))
    if key not in set().union(*(_keys(_game_xml(idx, p)) for p in INPUTMAPS)):
        raise ChartError(f'The game has no key named "{key}". Free keys: {free}')
    bound = bound_keys(idx)
    if key in bound:
        raise ChartError(f'"{key}" already does {bound[key]} in the game. Free keys: {free}')


def _entry(name, key):
    return f'\r\n\t<Input Name="{name}">\r\n\t\t<KeyboardMouse Key="{key}" Method="downonce"/>\r\n\t</>'


def _drop_input(xml, name):
    return re.sub(r'\r\n\t<Input Name="%s">.*?</>' % re.escape(name), "", xml, count=1, flags=re.S)


def _write_inputmap(idx, root, xml):
    """Write the input map under by_path, or delete it once it is the game's."""
    target = _target(root, INPUTMAP)
    if xml == game_inputmap(idx):
        if os.path.isfile(target):
            os.remove(target)
            _prune(os.path.dirname(target), root)
        return
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(("﻿" + xml).encode("utf-8"))


def _folder_inputmap(idx, root):
    at = _target(root, INPUTMAP)
    if not os.path.isfile(at):
        return game_inputmap(idx)
    with open(at, encoding="utf-8-sig", newline="") as f:
        return f.read()


def send_move(idx, root, clip, key, frames, loop=False, travel=False, face=0, sound=None, prop=None):
    """Write into the loader folder `root` Kliff's two charts with a move
    that plays `clip`, `frames` long, on `key`, looping with `loop`, moving
    him as the clip travels with `travel`, starting the expression `face`,
    an action of FACES, playing `sound`, a sound's name and the seconds
    into the move, showing `prop`, a prefab's game path, a socket and the
    prefab's grip or "", while it plays, and the input map with the key.
    Returns the charts written."""
    check_key(idx, key)
    name = input_name(clip)
    xml = _drop_input(_folder_inputmap(idx, root), name)
    other = re.search(r'<Input Name="(Key_CDA_[^"]+)">\s*<KeyboardMouse Key="%s"' % re.escape(key), xml)
    if other:
        raise ChartError(f'"{key}" already plays {other.group(1)[len("Key_CDA_"):]}')
    written, events = [], []
    if face:
        # A copy of the face that lasts the move, or a loop's round and a little, which the next round starts over.
        facial, game, mine = current(idx, root, FACIAL_CHART)
        own = face_key(game, clip)
        new = face_chart(facial, game_bytes(idx, FACIAL_CHART), own, face, frames / FPS + (FACE_AFTER if loop else 0.0))
        written.append(_write(root, FACIAL_CHART, new.pack(), mine))
        events.append((0.0, face_event(own)))
    if sound:
        events.append((sound[1], sound_event(sound[0])))
    for path in MOVE_CHARTS:
        chart, _game, mine = current(idx, root, path)
        # Like the stop, the face, the sound and the prop go in the chart whose clip shows only. A stopped loop's
        # upper copy plays on unseen and would start them again each round.
        shown = [(0.0, prop_path(prop[0]), prop[1], prop[2])] if prop else []
        add_move(chart, clip, name.lower(), frames, loop, travel, path == STOP_CHART,
                 *((events, shown) if path == STOP_CHART else ((), ())))
        written.append(_write(root, path, chart.pack(), mine))
    _write_inputmap(idx, root, xml.replace(_GROUP, _GROUP + _entry(name, key), 1))
    return written


def _target(root, path):
    """Where a chart or blend goes in the loader folder: under by_path, at
    the game's path for it."""
    return os.path.join(root, BY_PATH, *path.split("/"))


def _copy_in(root, path):
    """The file's copy in the loader folder `root`, or None: the one at
    its game path under by_path, else one by its name elsewhere, as 0.22.0
    wrote them."""
    at = _target(root, path)
    if os.path.isfile(at):
        return at
    want = chart_name(path).lower()
    for here, dirs, names in os.walk(root):
        if os.path.normcase(os.path.abspath(here)) == os.path.normcase(os.path.abspath(os.path.join(root, BY_PATH))):
            dirs[:] = []
            continue
        dirs.sort()
        for n in sorted(names):
            if n.lower() == want:
                return os.path.join(here, n)
    return None


def _size(doc):
    return len(doc.clips) if isinstance(doc, _Blend) else len(doc.nodes)


def current(idx, root, path):
    """(chart, game chart, file in the folder or None): the folder's copy
    of a chart or blend if it has one, else the game's."""
    game = _parse(path, game_bytes(idx, path))
    mine = _copy_in(root, path) if root and os.path.isdir(root) else None
    if mine and mine != _target(root, path) and _by_name(idx).get(chart_name(path)) != path:
        mine = None   # a file of that name, but not this one's
    if mine:
        with open(mine, "rb") as f:
            chart = _parse(path, f.read())
        n, g = _size(chart), _size(game)
        if n < g or n != g and isinstance(chart, _Blend):
            raise ChartError(f"{mine} does not match the game's {chart_name(path)}; it was not made from this "
                             "version of the game's file")
    else:
        chart = _parse(path, game_bytes(idx, path))
    return chart, game, mine


def send(idx, root, clip, plays):
    """Write into the loader folder `root` the charts and blends that
    point `plays` ([(path, node or slot)]) at `clip`. Returns the files
    written."""
    by_chart = {}
    for path, node in plays:
        by_chart.setdefault(path, []).append(node)
    written = []
    for path, nodes in sorted(by_chart.items()):
        chart, _game, mine = current(idx, root, path)
        point(chart, nodes, clip)
        written.append(_write(root, path, chart.pack(), mine))
    return written


def _write(root, path, data, mine):
    """Write a chart or blend under by_path, deleting an old copy elsewhere."""
    target = _target(root, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(data)
    if mine and mine != target:
        os.remove(mine)
        _prune(os.path.dirname(mine), root)
    return target


def _ours(idx, root):
    """(file, game path) of each chart and blend in the folder `root`:
    those under by_path at a game path, and those elsewhere by name."""
    under = os.path.normcase(os.path.abspath(os.path.join(root, BY_PATH)))
    by_name = _by_name(idx)
    for here, dirs, names in os.walk(root):
        dirs.sort()
        inside = os.path.normcase(os.path.abspath(here)).startswith(under)
        for n in sorted(names):
            f = os.path.join(here, n)
            if inside:
                path = os.path.relpath(f, os.path.join(root, BY_PATH)).replace("\\", "/").lower()
                if (path.startswith(CHARTS) and path.endswith(SUFFIX) or is_blend(path)) and path in idx.by_path:
                    yield f, path
            elif by_name.get(n.lower()):
                yield f, by_name[n.lower()]


def _clips_of(doc):
    return doc.clips if isinstance(doc, _Blend) else _table(doc)


def _prune(folder, root):
    """Remove `folder` and the folders above it while empty, up to `root`."""
    root = os.path.normcase(os.path.abspath(root))
    folder = os.path.abspath(folder)
    while os.path.normcase(folder) != root and os.path.normcase(folder).startswith(root):
        try:
            os.rmdir(folder)
        except OSError:
            return
        folder = os.path.dirname(folder)


def take_out(idx, root, clip):
    """Put back every node and slot of the charts and blends in `root`
    that plays `clip`, a path under character/motion/ or only the clip's
    name, as the loader matches files; delete a file that then matches the
    game's. Returns (rewritten, deleted) file paths."""
    rewritten, deleted = [], []
    if not os.path.isdir(root):
        return rewritten, deleted
    leaf = clip.rsplit("/", 1)[-1].lower() + ".paa"
    for f, path in list(_ours(idx, root)):
        with open(f, "rb") as h:
            chart = _parse(path, h.read())
        game_data = game_bytes(idx, path)
        if isinstance(chart, _Blend):
            game = _parse(path, game_data)
            named = {s[:-4] for s in _clips_of(chart) if s.rsplit("/", 1)[-1].lower() == leaf}
            if not [i for c in sorted(named) for i in unpoint(chart, game, c)]:
                continue
        elif path == FACIAL_CHART:
            key = face_key(paac.Chart.parse(game_data), clip)
            if not chart.find_action(key):
                continue
            chart = face_chart(chart, game_data, key)
        else:
            chart = _without(chart, game_data, leaf, path)
            if chart is None:
                continue
        data = chart.pack()
        if data == game_data:
            os.remove(f)
            _prune(os.path.dirname(f), root)
            deleted.append(f)
        else:
            with open(f, "wb") as h:
                h.write(data)
            rewritten.append(f)
    if os.path.isfile(_target(root, INPUTMAP)):
        _write_inputmap(idx, root, _drop_input(_folder_inputmap(idx, root), input_name(clip)))
    return rewritten, deleted


def in_folder(idx, root):
    """[(file, {clip: [nodes or slots]})] for the game's charts and blends
    in `root`."""
    if not os.path.isdir(root):
        return []
    out = []
    for f, path in _ours(idx, root):
        if path == FACIAL_CHART:
            continue   # its added actions copy the game's faces, and name no new clip
        with open(f, "rb") as h:
            chart = _parse(path, h.read())
        out.append((f, pointed(chart, _parse(path, game_bytes(idx, path)))))
    return out
