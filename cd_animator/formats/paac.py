"""Crimson Desert action charts (.paac): the game's state machines, which
say which clip each state plays.

From Broomy's research (its chart schema, MIT), read from the game's own
reader for build 1.0.0.3392 and checked on 1.0.0.3462. A chart is a flat
run of count-prefixed arrays with no offsets, so it parses to the last
byte and packs back byte for byte from the tree; 558 of the game's 560
charts do. The two commonactioninfo charts are another kind.

A node is one clip and its timed parameters; it names the clip by an index
into the chart's second string table (strings[1]), which holds .paa paths
relative to character/motion/. An action, the state, owns a run of nodes.

The DLC build (3392) changed the layout against 2976, so a chart from
before it does not read here. The node header grew from 0x9C to 0xA8 bytes
and gained an eleventh array. A node's frame event condition tokens moved
into the chart's condition words, and each frame event entry gained a word
that names them. Actions grew to 0x120 bytes, branches to 56 and slots to
32. Condition token ids and frame event types were renumbered
(condition_token_2976, frame_event_type_2976), and the chart gained one
section at its end.

The 3392 readers are at top level 0x214A4C0, node 0x2149030, chart tail
0x214AE40 and branch section 0x2149AD0 (2976: 0x1F67A00, 0x1F66560,
0x1F68370, 0x1F670B0).

    from cd_animator.formats.paac import Chart
    c = Chart.parse(open("ride_tank_upper.paac", "rb").read())
    a = c.actions[0]
    a.key_hash, c.action_nodes(a), c.action_branches(a)
    data = c.pack()                       # every count and offset is recomputed from the lists

Every fixed size record is a Rec: named fields come from LAYOUTS below, everything the schema cannot
name is an `unk_XX` field (XX = hex byte offset inside the record).  Floats are f32.  Section and
record names are the game's own load error labels where the game has one (AnimationInfo,
frameTag, branchInstanceArray, conditionInstanceArray, ...).  Pure standard library, Python 3.8+.
"""
import struct

__all__ = ["Chart", "Node", "Rec", "ParseError", "LAYOUTS", "STRING_LIST_NAMES", "FRAME_EVENT_WORDS",
           "CONDITION_TOKEN_WORDS"]


class ParseError(Exception):
    pass


# --------------------------------------------------------------------------------------------
# fixed records
# --------------------------------------------------------------------------------------------
_FMT = {"u8": ("<B", 1), "u16": ("<H", 2), "u32": ("<I", 4), "f32": ("<f", 4), "i32": ("<i", 4),
        "i16": ("<h", 2)}


def _fill(size, named):
    """Complete a partial field list with unk_XX gap fields (u32 when aligned, else u16/u8)."""
    named = sorted(named)
    out, pos = [], 0

    def gap(a, b):
        while a < b:
            if a % 4 == 0 and b - a >= 4:
                t, n = "u32", 4
            elif a % 2 == 0 and b - a >= 2:
                t, n = "u16", 2
            else:
                t, n = "u8", 1
            out.append((a, t, "unk_%02X" % a))
            a += n

    for off, t, name in named:
        if off < pos:
            raise ValueError("overlapping field %s at %x" % (name, off))
        gap(pos, off)
        out.append((off, t, name))
        pos = off + _FMT[t][1]
    gap(pos, size)
    if pos > size:
        raise ValueError("layout overruns record")
    return out


class Layout:
    def __init__(self, name, size, named):
        self.name, self.size = name, size
        self.fields = _fill(size, named)
        self.names = [f[2] for f in self.fields]
        self.index = {n: i for i, n in enumerate(self.names)}
        self.struct = struct.Struct("<" + "".join(_FMT[t][0][1] for _, t, _ in self.fields))
        assert self.struct.size == size, (name, self.struct.size, size)


class Rec:
    """One fixed size record: values in layout order, attribute access by field name."""
    __slots__ = ("_L", "_v")

    def __init__(self, layout, values=None):
        object.__setattr__(self, "_L", layout)
        object.__setattr__(self, "_v", list(values) if values is not None else
                           [0.0 if t == "f32" else 0 for _, t, _ in layout.fields])

    @classmethod
    def parse(cls, layout, buf, off=0):
        return cls(layout, layout.struct.unpack_from(buf, off))

    def pack(self):
        return self._L.struct.pack(*self._v)

    def __getattr__(self, n):
        try:
            return self._v[self._L.index[n]]
        except KeyError:
            raise AttributeError(n)

    def __setattr__(self, n, val):
        try:
            self._v[self._L.index[n]] = val
        except KeyError:
            raise AttributeError(n)

    def copy(self):
        return Rec(self._L, self._v)

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, memo):
        return self.copy()

    def as_dict(self):
        return dict(zip(self._L.names, self._v))

    def __repr__(self):
        return "%s(%s)" % (self._L.name, ", ".join(
            "%s=%s" % (n, ("0x%X" % v) if isinstance(v, int) and v > 0xFFFF else v)
            for n, v in zip(self._L.names, self._v) if v not in (0, 0.0)))


def _L(name, size, *fields):
    return Layout(name, size, list(fields))


# Field names follow paac_schema.md; the doc marks which names are guesses.
LAYOUTS = {
    # ---- AnimationInfoData, the 0xA8 byte block that starts every node (read in place) -------
    # 3392 inserted four bytes at 2976's +0x40 and four at +0x5C, and an eleventh array entry.
    "AnimationInfoData": _L(
        "AnimationInfoData", 0xA8,
        (0x04, "f32", "duration"),         # <0 means "use the clip length"
        (0x08, "u32", "group_hash"),       # the rider's group hash; 0 plays for anyone
        # per array i: u16 byte offset of the array inside the node's array area (running sum of
        # the earlier count*size, recomputed on pack) at 0x70+4i, u8 count at 0x72+4i.  The node
        # reader 0x2149030 reads only the count byte; the byte after it is not always 0 on 3392.
        *[(0x70 + 4 * i, "u16", "arr%d_offset" % i) for i in range(11)],
        *[(0x72 + 4 * i, "u8", "arr%d_count" % i) for i in range(11)],
        (0x9C, "u16", "anim_index_a"),     # index into strings[1] (.paa), always equal to anim_index
        (0x9E, "u16", "anim_index"),       # index into strings[1]
        (0xA0, "u16", "unk_A0"),
        (0xA2, "u16", "blend_index_a"),    # index into strings[5] (.motionblending), 0xFFFF none
        (0xA4, "u16", "blend_index_b"),    # index into strings[5], 0xFFFF none
    ),
    # ---- the eleven AnimationInfo arrays; names are the game's load error labels ---------------
    # frameTag: a branch whose frame_tag matches may only fire while the playback time is inside
    # [time_start, time_end] of a window with that tag (check in 0x25152D0)
    "FrameTag": _L("FrameTag", 12, (0x00, "f32", "time_start"), (0x04, "f32", "time_end"), (0x08, "u8", "tag")),
    "AnimationSpeedInfo": _L("AnimationSpeedInfo", 16, (0x00, "f32", "time_start"), (0x04, "f32", "time_end"),
                             (0x08, "f32", "play_rate"), (0x0C, "u32", "flags")),
    "MoveSpeedInfo": _L("MoveSpeedInfo", 0x68, (0x00, "f32", "time_start"), (0x04, "f32", "time_end")),
    "AiMoveSpeedInfo": _L("AiMoveSpeedInfo", 0x94),
    "VerticalMoveSpeedInfo": _L("VerticalMoveSpeedInfo", 24, (0x00, "f32", "time_start"), (0x04, "f32", "time_end")),
    "DefenceInfo": _L("DefenceInfo", 36, (0x00, "f32", "time_start"), (0x04, "f32", "time_end"),
                      (0x08, "u32", "kind"), (0x0C, "f32", "angle_min"), (0x10, "f32", "angle_max")),
    "CharacterClimbTagInfo": _L("CharacterClimbTagInfo", 12, (0x00, "f32", "time_start"), (0x04, "f32", "time_end")),
    "OnHitEventInfo": _L("OnHitEventInfo", 96, (0x00, "f32", "time_start"), (0x04, "f32", "time_end")),
    "StumbleOnHitInfo": _L("StumbleOnHitInfo", 12),
    "AiReviseTurnInfo": _L("AiReviseTurnInfo", 12, (0x00, "f32", "time_start"), (0x04, "f32", "time_end"),
                           (0x08, "f32", "angle")),
    "JustTimeFrameTagInfo": _L("JustTimeFrameTagInfo", 16),   # new in 3392
    # frame event instance: when playback passes `time`, the event whose payload starts at word
    # `event_index` of chart.frame_event_buffer fires.  unk_10 is 0xFFFFFFFF on 2976 and 0x0001FFFF
    # on 3392 in every instance.
    "FrameEventInstance": _L("FrameEventInstance", 20, (0x00, "f32", "time"), (0x04, "f32", "time_end"),
                             (0x08, "u32", "event_index"), (0x0C, "u32", "ordinal"), (0x10, "u32", "unk_10")),
    # ---- chart level records -------------------------------------------------------------------
    # "actionChart": one 0x120 byte record per action (the state).  3392 rewrote +0x7C..+0x83 (both
    # words 0xFFFFFFFF in most actions), moved 2976's +0x80..+0x103 by 4 and rebuilt the tail; the
    # loader reads a u16 at +0x112 (0xFFFF none) and writes a byte at +0x111.
    "Action": _L(
        "Action", 0x120,
        (0x18, "u32", "key_hash"),         # hashlittle(name, 0xC5EDE); branch targets match it
        (0x54, "u32", "node_first"),       # node range (the loader reads +0x54 and +0xEE)
        (0xAC, "u32", "list64_index"),     # 2976 +0xA8 (guess)
        (0xB0, "u32", "list32a_index"),    # 2976 +0xAC (guess)
        (0xE4, "u16", "slot_first"),       # range of chart.slots
        (0xE6, "u16", "slot_first_hi"),    # always 0xFFFF
        (0xE8, "u16", "slot_count"),
        (0xEE, "u16", "node_count"),
        (0x112, "u16", "contents_index"),  # 0xFFFF none; the loader looks it up in contents_group_table
    ),
    # branchInstanceArray, element 1: the branch itself.  +0x00..+0x2B as on 2976; the tail grew.
    "Branch": _L(
        "Branch", 56,
        (0x00, "f32", "unk_00_f"),
        (0x08, "f32", "time_a"),           # blend length in frames
        (0x0C, "f32", "time_b"),           # guess: blend length for layer 1, -1 = unset
        (0x14, "u32", "target_hash"),      # key_hash of the target action (layer 0)
        (0x18, "u32", "target_hash2"),     # target for layer 1 when non zero
        (0x1C, "u8", "kind"),              # 4 input, 5, 7 animation end, 20, 12
        (0x1D, "u8", "flags"),
        (0x20, "u32", "input_hash"),       # hashlittle(input name, 0xC5EDE); 0 when not input driven
        (0x24, "u16", "cond_first"),       # first token of the branch condition (index into condition_offsets)
        (0x26, "u16", "keycond_first"),    # first token of the key condition
        (0x2A, "u8", "cond_count"),
        (0x2B, "u8", "keycond_count"),
        (0x2D, "u8", "frame_tag"),         # 0x22 = none (0x28 on 2976), else must match a FrameTag tag
        (0x2E, "u8", "frame_tag2"),        # always 0x22 in shipped charts
        (0x2F, "u8", "unk_2F"),            # 0x1E (30) by default
        (0x34, "u16", "unk_34_ffff"),      # new in 3392, 0xFFFF in every shipped branch
    ),
    # branchInstanceArray, element 3: one entry of an action's branch list; points at a branch and
    # adds a time window, a condition and an input filter.  3392 inserted +0x12..+0x15.
    "Slot": _L("Slot", 32,
               (0x00, "u32", "unk_00_hash"),
               (0x04, "f32", "time_min"),      # branch only fires inside [time_min, time_max]
               (0x08, "f32", "time_max"),      # FLT_MAX = open end
               (0x0C, "u16", "branch_index"),  # index into chart.branches
               (0x0E, "u16", "cond_first"),    # slot condition tokens, used when flags & 0x0C
               (0x10, "u16", "filter_first"),  # range in chart.list32b of input hashes
               (0x12, "u16", "contents_index"),  # new in 3392: 0xFFFF none, the loader looks it up
               (0x14, "u8", "contents_on"),    # new in 3392: 1 in the files, rewritten by the loader
               (0x1C, "u8", "filter_count"),
               (0x1D, "u8", "flags"),
               (0x1E, "u8", "cond_count"),
               (0x1F, "u8", "unk_1F")),
    "DefaultSocket": _L("DefaultSocket", 40, (0x00, "u16", "index")),
    "ActionRec12": _L("ActionRec12", 12),          # three u32 hashes, shares the "actionChart" label
    "BranchRec8": _L("BranchRec8", 8),             # branchInstanceArray, element 2
    "KeyGuideInstance": _L("KeyGuideInstance", 28),
    "KeyGuidePair": _L("KeyGuidePair", 8),
}

NODE_ARR_LAYOUTS = ["FrameTag", "AnimationSpeedInfo", "MoveSpeedInfo", "AiMoveSpeedInfo", "VerticalMoveSpeedInfo",
                    "DefenceInfo", "CharacterClimbTagInfo", "OnHitEventInfo", "StumbleOnHitInfo",
                    "AiReviseTurnInfo", "JustTimeFrameTagInfo"]
NODE_ARR_ATTRS = ["frame_tags", "animation_speeds", "move_speeds", "ai_move_speeds", "vertical_move_speeds",
                  "defence_infos", "climb_tags", "on_hit_events", "stumble_on_hits", "ai_revise_turns",
                  "just_time_frame_tags"]
NODE_ARR_SIZES = [LAYOUTS[n].size for n in NODE_ARR_LAYOUTS]
NODE_ARRAYS = len(NODE_ARR_LAYOUTS)
assert NODE_ARR_SIZES == [12, 16, 0x68, 0x94, 24, 36, 12, 96, 12, 12, 16]
NO_FRAME_TAG = 0x22         # Branch.frame_tag meaning "no window" (cmp r14b,22h at 0x25155BA)
# the ten string tables, by content (the game only calls them "stringTable")
STRING_LIST_NAMES = ["names", "anim_paa", "camera_paa", "effect", "pafx", "motionblending",
                     "bone", "item", "baseseq", "prefab"]


# Words per entry, observed on 3392.  frame_event_buffer: the low u16 of an entry's first word is its type
# and decides the entry length.  Word 1 is (u8 1, u8 condition token count, u16 first condition token in
# chart.condition_offsets); on 2976 the tokens were the node's own.  3392 inserted a word at index 2
# (0x0000FFFF when unused), so a 2976 payload word k >= 2 is word k + 1 here.  Types from 0x37 up are
# 2976's plus 2 (frame_event_type_2976).  Lengths are the shortest gap from an entry to the next
# referenced one over the 558 shipped charts, so a type whose entries are always followed by
# unreferenced words may read long.  Condition tokens: the first word is the id; 3392 renumbered the
# ids (condition_token_2976) and kept their lengths.
FRAME_EVENT_WORDS = {
    0x0: 4, 0x1: 4, 0x2: 4, 0x3: 4, 0x4: 27, 0x5: 11, 0x6: 4, 0x7: 77, 0x8: 4, 0x9: 11, 0xA: 21, 0xB: 66,
    0xC: 8, 0xD: 6, 0xE: 29, 0xF: 8, 0x11: 5, 0x12: 5, 0x13: 8, 0x14: 6, 0x15: 6, 0x16: 7, 0x17: 4, 0x18: 3,
    0x19: 61, 0x1A: 6, 0x1B: 4, 0x1D: 5, 0x1E: 4, 0x1F: 3, 0x20: 4, 0x21: 4, 0x23: 6, 0x24: 4, 0x25: 37,
    0x26: 6, 0x27: 64, 0x28: 8, 0x29: 3, 0x2A: 5, 0x2B: 6, 0x2C: 24, 0x2D: 5, 0x2E: 4, 0x2F: 11, 0x30: 14,
    0x31: 5, 0x32: 7, 0x33: 12, 0x34: 3, 0x35: 14, 0x36: 6, 0x37: 14, 0x39: 90, 0x3A: 16, 0x3B: 92, 0x3D: 8,
    0x3E: 8, 0x3F: 6, 0x40: 4, 0x41: 4, 0x42: 8, 0x43: 59, 0x44: 30, 0x45: 6, 0x46: 12, 0x47: 15, 0x48: 10,
    0x49: 4, 0x4B: 15, 0x4C: 19, 0x4D: 5, 0x4E: 7, 0x4F: 10, 0x50: 8, 0x51: 5, 0x52: 18, 0x53: 4, 0x54: 6,
    0x55: 4, 0x57: 5, 0x59: 15, 0x5B: 6, 0x5C: 4, 0x5D: 6, 0x5E: 6, 0x5F: 5, 0x60: 9, 0x61: 7, 0x62: 7,
    0x63: 17, 0x64: 5, 0x66: 6, 0x67: 13, 0x68: 9, 0x6F: 4, 0x70: 5, 0x71: 147, 0x72: 85, 0x73: 12, 0x74: 3,
    0x75: 5, 0x76: 7, 0x79: 7, 0x7A: 4, 0x7B: 4, 0x7C: 9, 0x7D: 8, 0x7E: 13, 0x7F: 6, 0x80: 11, 0x81: 9,
    0x82: 6, 0x83: 54, 0x84: 9, 0x85: 10, 0x86: 4, 0x88: 11, 0x89: 8, 0x8A: 3, 0x8B: 13, 0x8C: 3, 0x8D: 6,
    0x90: 10, 0x91: 10, 0x92: 6, 0x93: 11, 0x94: 15, 0x95: 5, 0x96: 7, 0x98: 17, 0x99: 3, 0x9C: 47, 0x9D: 5,
    0x9E: 3, 0xA0: 4, 0xA1: 14, 0xA2: 21, 0xA3: 19, 0xA4: 4, 0xA5: 6, 0xA6: 6, 0xA7: 4, 0xA8: 4, 0xAA: 4,
    0xAB: 5, 0xAD: 4, 0xAE: 3, 0xB0: 10, 0xB3: 6, 0xB6: 5,
}


def frame_event_type_2976(t):
    """The 3392 type of a 2976 frame event type."""
    return t + 2 if t >= 0x37 else t


_TOKEN_STEPS = [(0x0, 0), (0xE7, 1), (0x164, 2), (0x1A0, 3), (0x1AD, 5), (0x1CD, 6), (0x1E8, 7), (0x1F4, 8),
                (0x22A, 9), (0x22F, 10), (0x230, 11), (0x243, 12), (0x26E, 16), (0x272, 17), (0x275, 18)]


def condition_token_2976(i):
    """The 3392 id of a 2976 condition token id.  161,569 paired branch conditions of the shipped charts
    agree with these steps, and so does the per-leaf flag table the leaf dispatcher indexes (2976
    +0x57A1FD0, 3392 +0x5B40730).  AND, OR and NOT (0x275..0x277 on 2976) are 0x287..0x289."""
    return i + [d for s, d in _TOKEN_STEPS if i >= s][-1]


TOKEN_AND, TOKEN_OR, TOKEN_NOT = 0x287, 0x288, 0x289

CONDITION_TOKEN_WORDS = {
    0x0: 2, 0x1: 1, 0x2: 1, 0x3: 1, 0x4: 1, 0x5: 1, 0x6: 1, 0x7: 1, 0x8: 1, 0x9: 1, 0xC: 1, 0xD: 1, 0xE: 1,
    0x10: 1, 0x13: 1, 0x14: 1, 0x15: 1, 0x16: 1, 0x17: 1, 0x18: 1, 0x21: 1, 0x22: 1, 0x23: 1, 0x24: 1, 0x25: 1,
    0x27: 1, 0x29: 1, 0x2C: 1, 0x32: 1, 0x33: 1, 0x36: 1, 0x37: 1, 0x38: 1, 0x39: 1, 0x3A: 1, 0x3B: 1, 0x3C: 1,
    0x3D: 1, 0x3E: 1, 0x3F: 1, 0x40: 1, 0x41: 1, 0x45: 1, 0x49: 1, 0x4A: 1, 0x4E: 1, 0x4F: 1, 0x5C: 1, 0x5D: 1,
    0x5E: 1, 0x5F: 1, 0x61: 1, 0x62: 1, 0x65: 1, 0x66: 1, 0x67: 1, 0x68: 1, 0x69: 1, 0x6A: 1, 0x6D: 1, 0x6E: 1,
    0x74: 1, 0x79: 1, 0x7B: 1, 0x7C: 1, 0x7D: 1, 0x7F: 1, 0x80: 1, 0x81: 1, 0x82: 1, 0x83: 1, 0x84: 1, 0x86: 1,
    0x88: 1, 0x89: 1, 0x8B: 1, 0x8D: 1, 0x8E: 1, 0x8F: 1, 0x90: 1, 0x92: 1, 0x93: 1, 0x94: 1, 0x96: 1, 0x97: 1,
    0x9B: 1, 0x9C: 1, 0x9D: 1, 0x9F: 1, 0xA1: 1, 0xA2: 1, 0xA3: 1, 0xA4: 1, 0xA5: 1, 0xA6: 1, 0xA7: 1, 0xAC: 1,
    0xAE: 1, 0xB0: 1, 0xB1: 1, 0xB2: 1, 0xB3: 1, 0xB5: 1, 0xB6: 1, 0xB7: 1, 0xB8: 5, 0xBA: 5, 0xBB: 5, 0xBC: 1,
    0xBD: 1, 0xBE: 1, 0xBF: 1, 0xC0: 1, 0xC1: 1, 0xC2: 1, 0xC4: 5, 0xC5: 5, 0xC6: 5, 0xC7: 5, 0xC9: 5, 0xCA: 5,
    0xCC: 5, 0xCE: 5, 0xD1: 5, 0xD4: 5, 0xD5: 5, 0xD6: 5, 0xD7: 5, 0xD8: 5, 0xD9: 5, 0xDA: 5, 0xDB: 5, 0xDC: 5,
    0xDD: 5, 0xDF: 5, 0xE1: 5, 0xE2: 5, 0xE3: 5, 0xE4: 5, 0xE5: 5, 0xE8: 5, 0xE9: 5, 0xEA: 5, 0xEB: 5, 0xEC: 5,
    0xED: 5, 0xEE: 5, 0xEF: 5, 0xF0: 5, 0xF1: 5, 0xF2: 5, 0xF4: 5, 0xF5: 5, 0xF6: 5, 0xF7: 5, 0xF8: 5, 0xFB: 5,
    0xFD: 5, 0xFF: 1, 0x100: 1, 0x101: 5, 0x104: 5, 0x105: 5, 0x106: 5, 0x107: 5, 0x108: 5, 0x109: 5, 0x10A: 5,
    0x10B: 5, 0x10D: 5, 0x10E: 5, 0x10F: 5, 0x110: 5, 0x111: 5, 0x113: 5, 0x116: 5, 0x117: 1, 0x118: 5,
    0x11B: 5, 0x11E: 5, 0x11F: 1, 0x120: 5, 0x122: 5, 0x123: 5, 0x124: 5, 0x125: 5, 0x126: 1, 0x127: 5,
    0x128: 5, 0x129: 5, 0x12A: 5, 0x12B: 5, 0x12C: 5, 0x12D: 1, 0x12E: 5, 0x130: 5, 0x131: 5, 0x133: 5,
    0x134: 5, 0x136: 5, 0x137: 5, 0x138: 5, 0x139: 5, 0x13A: 5, 0x13B: 5, 0x13C: 5, 0x13D: 5, 0x13E: 5,
    0x13F: 5, 0x145: 5, 0x146: 5, 0x147: 5, 0x148: 5, 0x14A: 5, 0x14B: 5, 0x14C: 5, 0x14E: 1, 0x151: 5,
    0x152: 5, 0x153: 1, 0x154: 1, 0x155: 5, 0x156: 1, 0x157: 5, 0x159: 5, 0x15B: 5, 0x15C: 5, 0x15D: 1,
    0x15E: 1, 0x15F: 1, 0x160: 1, 0x161: 5, 0x162: 5, 0x163: 1, 0x164: 5, 0x166: 5, 0x167: 5, 0x168: 1,
    0x169: 5, 0x16D: 5, 0x16E: 5, 0x170: 5, 0x171: 5, 0x172: 5, 0x173: 5, 0x174: 5, 0x175: 1, 0x176: 5,
    0x177: 5, 0x178: 5, 0x179: 5, 0x17A: 5, 0x17B: 5, 0x17C: 5, 0x17D: 1, 0x17F: 5, 0x180: 5, 0x181: 5,
    0x185: 5, 0x186: 1, 0x188: 1, 0x18A: 1, 0x18B: 5, 0x18C: 1, 0x18D: 5, 0x18E: 5, 0x18F: 5, 0x190: 5,
    0x192: 5, 0x193: 5, 0x194: 1, 0x196: 5, 0x197: 5, 0x198: 5, 0x199: 5, 0x19A: 5, 0x19B: 5, 0x19C: 5,
    0x19D: 5, 0x19E: 5, 0x19F: 1, 0x1A0: 5, 0x1A1: 5, 0x1A3: 1, 0x1A5: 1, 0x1A6: 1, 0x1A7: 5, 0x1A8: 5,
    0x1A9: 5, 0x1AA: 5, 0x1AC: 1, 0x1AE: 1, 0x1AF: 5, 0x1B2: 5, 0x1B3: 5, 0x1B4: 5, 0x1B6: 5, 0x1B7: 5,
    0x1B8: 1, 0x1B9: 5, 0x1BA: 5, 0x1BB: 5, 0x1BC: 5, 0x1BE: 5, 0x1BF: 5, 0x1C1: 5, 0x1C2: 5, 0x1C3: 5,
    0x1C4: 5, 0x1C5: 5, 0x1C6: 5, 0x1C7: 5, 0x1C8: 5, 0x1C9: 5, 0x1CA: 5, 0x1CB: 5, 0x1CC: 5, 0x1CD: 5,
    0x1CE: 5, 0x1D0: 1, 0x1D1: 5, 0x1D3: 5, 0x1D4: 5, 0x1D5: 5, 0x1D6: 5, 0x1D7: 5, 0x1D8: 5, 0x1D9: 5,
    0x1DA: 5, 0x1DB: 5, 0x1DC: 5, 0x1DD: 5, 0x1E0: 5, 0x1E2: 5, 0x1E3: 5, 0x1E4: 5, 0x1E5: 5, 0x1E6: 5,
    0x1E7: 5, 0x1E8: 1, 0x1E9: 5, 0x1EA: 5, 0x1EB: 5, 0x1EC: 1, 0x1EF: 5, 0x1F0: 5, 0x1F1: 5, 0x1F2: 5,
    0x1F3: 5, 0x1F4: 1, 0x1F6: 5, 0x1F7: 5, 0x1F9: 5, 0x1FA: 5, 0x1FC: 5, 0x1FD: 5, 0x1FE: 5, 0x1FF: 5,
    0x200: 5, 0x201: 5, 0x202: 5, 0x203: 1, 0x204: 5, 0x205: 5, 0x206: 5, 0x207: 5, 0x209: 5, 0x20A: 5,
    0x20B: 5, 0x20C: 5, 0x20D: 5, 0x210: 5, 0x213: 5, 0x214: 5, 0x215: 5, 0x216: 5, 0x218: 5, 0x219: 5,
    0x21A: 5, 0x21B: 5, 0x21E: 5, 0x21F: 5, 0x220: 1, 0x221: 5, 0x222: 5, 0x223: 5, 0x224: 5, 0x225: 1,
    0x226: 1, 0x227: 1, 0x228: 5, 0x229: 5, 0x22A: 5, 0x22B: 5, 0x22E: 5, 0x22F: 1, 0x230: 1, 0x231: 1,
    0x233: 1, 0x234: 1, 0x235: 1, 0x236: 1, 0x237: 5, 0x239: 5, 0x23B: 1, 0x23C: 1, 0x242: 5, 0x243: 5,
    0x244: 5, 0x245: 5, 0x246: 5, 0x247: 5, 0x249: 1, 0x24A: 1, 0x24B: 1, 0x24C: 1, 0x24D: 5, 0x24F: 5,
    0x250: 5, 0x251: 5, 0x252: 5, 0x254: 5, 0x255: 1, 0x256: 5, 0x257: 5, 0x258: 5, 0x259: 5, 0x25D: 5,
    0x25E: 5, 0x25F: 5, 0x260: 5, 0x261: 1, 0x262: 5, 0x264: 5, 0x266: 5, 0x267: 5, 0x268: 5, 0x269: 5,
    0x26A: 5, 0x26B: 1, 0x26C: 5, 0x26D: 5, 0x26E: 5, 0x26F: 5, 0x270: 5, 0x271: 5, 0x272: 5, 0x273: 1,
    0x274: 5, 0x276: 5, 0x278: 5, 0x279: 5, 0x27E: 5, 0x27F: 5, 0x281: 5, 0x283: 5, 0x284: 1, 0x287: 1,
    0x288: 1, 0x289: 1,
}


# --------------------------------------------------------------------------------------------
# reader / writer helpers
# --------------------------------------------------------------------------------------------
class _Reader:
    def __init__(self, data):
        self.d, self.p = data, 0

    def need(self, n):
        if self.p + n > len(self.d):
            raise ParseError("read of %d bytes at 0x%X runs past EOF (0x%X)" % (n, self.p, len(self.d)))

    def u8(self):
        self.need(1)
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        self.need(2)
        v, = struct.unpack_from("<H", self.d, self.p)
        self.p += 2
        return v

    def u32(self):
        self.need(4)
        v, = struct.unpack_from("<I", self.d, self.p)
        self.p += 4
        return v

    def raw(self, n):
        self.need(n)
        v = self.d[self.p:self.p + n]
        self.p += n
        return bytes(v)

    def recs(self, layout, n):
        self.need(n * layout.size)
        out = [Rec.parse(layout, self.d, self.p + i * layout.size) for i in range(n)]
        self.p += n * layout.size
        return out

    def words(self, n, fmt):
        sz = struct.calcsize(fmt)
        self.need(n * sz)
        v = list(struct.unpack_from("<%d%s" % (n, fmt), self.d, self.p))
        self.p += n * sz
        return v


def _w(out, fmt, *vals):
    out.append(struct.pack("<" + fmt, *vals))


def _pack_str_list(out, strings):
    _w(out, "H", len(strings))
    for s in strings:
        b = s.encode("ascii") + b"\0"
        if len(b) > 255:
            raise ValueError("string too long for u8 length: %r" % s)
        _w(out, "B", len(b))
        out.append(b)


def _words(out, fmt, vals):
    out.append(struct.pack("<%d%s" % (len(vals), fmt), *vals))


# --------------------------------------------------------------------------------------------
# tree
# --------------------------------------------------------------------------------------------
class Node:
    """One AnimationInfo (read by 0x2149030): the animation clip and its timed parameters.  An action
    owns a run of consecutive nodes (Action.node_first/node_count).

    header                  AnimationInfoData (0xA8 bytes)
    arrays[0..10]           eleven arrays of fixed records; the same lists are also reachable as
                            frame_tags, animation_speeds, move_speeds, ai_move_speeds,
                            vertical_move_speeds, defence_infos, climb_tags, on_hit_events,
                            stumble_on_hits, ai_revise_turns, just_time_frame_tags
    frame_event_instances   FrameEventInstance list (u8 count), "_frameEventInstanceBuffer"

    2976 nodes also carried their frame events' condition tokens and a random frame event list; on
    3392 the tokens are in the chart's condition_words and a frame event entry names them.
    """

    def __init__(self):
        self.header = Rec(LAYOUTS["AnimationInfoData"])
        self.arrays = [[] for _ in range(NODE_ARRAYS)]
        self.frame_event_instances = []

    frame_tags = property(lambda s: s.arrays[0])
    animation_speeds = property(lambda s: s.arrays[1])
    move_speeds = property(lambda s: s.arrays[2])
    ai_move_speeds = property(lambda s: s.arrays[3])
    vertical_move_speeds = property(lambda s: s.arrays[4])
    defence_infos = property(lambda s: s.arrays[5])
    climb_tags = property(lambda s: s.arrays[6])
    on_hit_events = property(lambda s: s.arrays[7])
    stumble_on_hits = property(lambda s: s.arrays[8])
    ai_revise_turns = property(lambda s: s.arrays[9])
    just_time_frame_tags = property(lambda s: s.arrays[10])

    @classmethod
    def parse(cls, r):
        n = cls()
        n.header = Rec.parse(LAYOUTS["AnimationInfoData"], r.raw(0xA8))
        h = n.header
        for i in range(NODE_ARRAYS):
            n.arrays[i] = r.recs(LAYOUTS[NODE_ARR_LAYOUTS[i]], h._v[h._L.index["arr%d_count" % i]])
        n.frame_event_instances = r.recs(LAYOUTS["FrameEventInstance"], r.u8())
        return n

    def pack(self, out):
        h = Rec(self.header._L, self.header._v)
        off = 0
        for i in range(NODE_ARRAYS):
            if len(self.arrays[i]) > 255:
                raise ValueError("node array %d has more than 255 records" % i)
            h._v[h._L.index["arr%d_count" % i]] = len(self.arrays[i])
            h._v[h._L.index["arr%d_offset" % i]] = off
            off += len(self.arrays[i]) * NODE_ARR_SIZES[i]
        out.append(h.pack())
        for i in range(NODE_ARRAYS):
            for rec in self.arrays[i]:
                out.append(rec.pack())
        if len(self.frame_event_instances) > 255:
            raise ValueError("node has more than 255 frame event instances")
        _w(out, "B", len(self.frame_event_instances))
        for rec in self.frame_event_instances:
            out.append(rec.pack())


class Chart:
    """A whole .paac file ("ActionChartPackage").  Attribute order is the file order."""

    def __init__(self):
        self.nodes = []                   # [Node]; u32 count first
        self.list64 = []                  # u64 list   (ctx+0x248)
        self.list32a = []                 # u32 list   (ctx+0x258)
        self.list32b = []                 # u32 list   (ctx+0x268), input hashes used by Slot.filter_*
        self.strings = [[] for _ in range(10)]   # ten string tables of str, see STRING_LIST_NAMES
        self.action_speed_rate = 1.0      # f32 ctx+0x27C, load label "ActionSpeedRate"
        self.default_action_hash = 0      # u32 ctx+0x280, key_hash of the entry action (guess)
        self.unk_284 = 0                  # u32 ctx+0x284
        self.unk_278_f = 1.0              # f32 ctx+0x278
        self.is_end_behavior = 0          # u8 ctx+0x2A6, "isEndBehaviorActionChart"
        self.is_npc_schedule = 0          # u8 ctx+0x2A7, "isNPCScheduleActionChart"
        self.hash_list = []               # u32 list   (ctx+0x290), CountInfo[0]
        self.default_sockets = []         # DefaultSocket list (ctx+0x208), "DefaultSocket"
        self.include_names = []           # u16 list into strings[0] (ctx+0x210), "_includeActionChartNameStringTableIndices"
        self.actions = []                 # Action list (ctx+0x228), "actionChart"
        self.action_rec12 = []            # ActionRec12 list (ctx+0x230)
        self.condition_words = []         # u32 list, "conditionInstanceArray" data (ctx+0x110)
        self.condition_offsets = []       # u16 list, token start inside condition_words (ctx+0x128)
        self.branches = []                # Branch list (ctx+0x130), "branchInstanceArray"
        self.branch_rec8 = []             # BranchRec8 list (ctx+0x140)
        self.slots = []                   # Slot list (ctx+0x150)
        self.keyguide_instances = []      # KeyGuideInstance list (ctx+0x170), u16 count, "keyGuideInstanceArray"
        self.keyguide_pairs = []          # KeyGuidePair list (ctx+0x160)
        self.keyguide_event_buffer = b""  # raw bytes (ctx+0x180), "_keyGuideFrameEventBuffer"
        self.keyguide_event_instances = []  # FrameEventInstance list (ctx+0x190), u8 count
        self.frame_event_buffer = b""     # raw bytes, 4 byte words (ctx+0x1A0), "_frameEventBuffer"
        self.frame_event_instances = []   # FrameEventInstance list (ctx+0x1B0), u8 count
        self.contents_group_table = b""   # raw bytes (ctx+0x1C0), new in 3392; Action and Slot contents_index read it

    # ---- parse ------------------------------------------------------------------------------
    @classmethod
    def parse(cls, data, trace=None):
        """Parse a chart.  `trace`, if a list, receives (section_name, end_offset) after every
        section so a checker can compare them with the positions the game's own reader reaches."""
        r = _Reader(bytes(data))
        c = cls()
        mark = (lambda name: trace.append((name, r.p))) if trace is not None else (lambda name: None)
        n = r.u32()
        c.nodes = []
        for _ in range(n):
            c.nodes.append(Node.parse(r))
            mark("node")
        c.list64 = r.words(r.u32(), "Q")
        c.list32a = r.words(r.u32(), "I")
        c.list32b = r.words(r.u32(), "I")
        mark("lists")
        for i in range(10):
            lst = []
            for _ in range(r.u16()):
                ln = r.u8()
                b = r.raw(ln)
                if ln == 0 or b[-1] != 0 or 0 in b[:-1] or any(x > 127 for x in b):
                    raise ParseError("string %d/%d at 0x%X is not plain NUL terminated ASCII" % (i, len(lst), r.p))
                lst.append(b[:-1].decode("ascii"))
            c.strings[i] = lst
            mark("strings%d" % i)
        c.action_speed_rate, = struct.unpack("<f", r.raw(4))
        c.default_action_hash = r.u32()
        c.unk_284 = r.u32()
        c.unk_278_f, = struct.unpack("<f", r.raw(4))
        c.is_end_behavior = r.u8()
        c.is_npc_schedule = r.u8()
        mark("scalars")
        # 0x2591840: u16 name count + ten u16 element counts; every shipped chart has all zero
        if r.u16() or any(r.u16() for _ in range(10)):
            raise ParseError("reflection stub (0x278B300) is non-empty; its element readers are not decoded")
        mark("stub")
        n_hash, n_sock, n_inc, n_act, n_rec12 = (r.u16() for _ in range(5))     # "CountInfo"
        if n_sock > 255 or n_hash > 255 or n_inc > 255:
            raise ParseError("count above 255 in the 10 byte CountInfo block")
        mark("counts")
        c.hash_list = r.words(n_hash, "I")
        mark("hash_list")
        c.default_sockets = r.recs(LAYOUTS["DefaultSocket"], n_sock)
        mark("default_sockets")
        c.include_names = r.words(n_inc, "H")
        mark("include_names")
        c.actions = r.recs(LAYOUTS["Action"], n_act)
        mark("actions")
        c.action_rec12 = r.recs(LAYOUTS["ActionRec12"], n_rec12)
        mark("action_rec12")
        nb = r.u32()
        if nb % 4:
            raise ParseError("condition data length not a multiple of 4")
        c.condition_words = r.words(nb // 4, "I")
        mark("condition_words")
        c.condition_offsets = r.words(r.u32(), "H")
        mark("condition_offsets")
        c.branches = r.recs(LAYOUTS["Branch"], r.u32())
        mark("branches")
        c.branch_rec8 = r.recs(LAYOUTS["BranchRec8"], r.u32())
        mark("branch_rec8")
        c.slots = r.recs(LAYOUTS["Slot"], r.u32())
        mark("slots")
        c.keyguide_instances = r.recs(LAYOUTS["KeyGuideInstance"], r.u16())
        mark("keyguide_instances")
        c.keyguide_pairs = r.recs(LAYOUTS["KeyGuidePair"], r.u32())
        mark("keyguide_pairs")
        c.keyguide_event_buffer = r.raw(r.u32())
        mark("keyguide_event_buffer")
        c.keyguide_event_instances = r.recs(LAYOUTS["FrameEventInstance"], r.u8())
        mark("keyguide_event_instances")
        c.frame_event_buffer = r.raw(r.u32())
        mark("frame_event_buffer")
        c.frame_event_instances = r.recs(LAYOUTS["FrameEventInstance"], r.u8())
        mark("frame_event_instances")
        c.contents_group_table = r.raw(r.u32())
        mark("contents_group_table")
        if r.p != len(r.d):
            raise ParseError("parse stopped at 0x%X of 0x%X" % (r.p, len(r.d)))
        return c

    # ---- pack -------------------------------------------------------------------------------
    def pack(self):
        out = []
        _w(out, "I", len(self.nodes))
        for nd in self.nodes:
            nd.pack(out)
        _w(out, "I", len(self.list64))
        _words(out, "Q", self.list64)
        for lst in (self.list32a, self.list32b):
            _w(out, "I", len(lst))
            _words(out, "I", lst)
        for lst in self.strings:
            _pack_str_list(out, lst)
        _w(out, "f", self.action_speed_rate)
        _w(out, "I", self.default_action_hash)
        _w(out, "I", self.unk_284)
        _w(out, "f", self.unk_278_f)
        _w(out, "BB", self.is_end_behavior, self.is_npc_schedule)
        out.append(b"\0" * 22)
        for v in (len(self.hash_list), len(self.default_sockets), len(self.include_names), len(self.actions),
                  len(self.action_rec12)):
            _w(out, "H", v)
        _words(out, "I", self.hash_list)
        out.extend(x.pack() for x in self.default_sockets)
        _words(out, "H", self.include_names)
        out.extend(x.pack() for x in self.actions)
        out.extend(x.pack() for x in self.action_rec12)
        _w(out, "I", len(self.condition_words) * 4)
        _words(out, "I", self.condition_words)
        _w(out, "I", len(self.condition_offsets))
        _words(out, "H", self.condition_offsets)
        _w(out, "I", len(self.branches))
        out.extend(x.pack() for x in self.branches)
        _w(out, "I", len(self.branch_rec8))
        out.extend(x.pack() for x in self.branch_rec8)
        _w(out, "I", len(self.slots))
        out.extend(x.pack() for x in self.slots)
        _w(out, "H", len(self.keyguide_instances))
        out.extend(x.pack() for x in self.keyguide_instances)
        _w(out, "I", len(self.keyguide_pairs))
        out.extend(x.pack() for x in self.keyguide_pairs)
        _w(out, "I", len(self.keyguide_event_buffer))
        out.append(self.keyguide_event_buffer)
        _w(out, "B", len(self.keyguide_event_instances))
        out.extend(x.pack() for x in self.keyguide_event_instances)
        _w(out, "I", len(self.frame_event_buffer))
        out.append(self.frame_event_buffer)
        _w(out, "B", len(self.frame_event_instances))
        out.extend(x.pack() for x in self.frame_event_instances)
        _w(out, "I", len(self.contents_group_table))
        out.append(self.contents_group_table)
        return b"".join(out)

    # ---- convenience views (read only) -------------------------------------------------------
    def action_nodes(self, action):
        return self.nodes[action.node_first:action.node_first + action.node_count]

    def action_slots(self, action):
        return self.slots[action.slot_first:action.slot_first + action.slot_count]

    def action_branches(self, action):
        return [self.branches[s.branch_index] for s in self.action_slots(action)]

    def find_action(self, key_hash):
        return next((a for a in self.actions if a.key_hash == key_hash), None)

    def token(self, index):
        """Condition token `index` as a list of u32 words (id first).

        A token ends where the next token in word order begins; the id decides its length (see
        paac_schema.md section 6), so the end is found from the sorted offsets."""
        starts = sorted(set(self.condition_offsets))
        s = self.condition_offsets[index]
        e = next((x for x in starts if x > s), len(self.condition_words))
        return self.condition_words[s:e]

    def frame_event(self, index):
        """Payload words of the frame event entry that starts at word `index` of frame_event_buffer.

        The entry length comes from FRAME_EVENT_WORDS (observed per type); None if the type is new."""
        words = struct.unpack("<%dI" % (len(self.frame_event_buffer) // 4), self.frame_event_buffer)
        n = FRAME_EVENT_WORDS.get(words[index] & 0xFFFF)
        return None if n is None else list(words[index:index + n])

    def condition(self, first, count):
        """Tokens [first, first+count) of a branch condition, a prefix expression."""
        return [self.token(i) for i in range(first, first + count)]

    def anim_path(self, node):
        i = node.header.anim_index
        return self.strings[1][i] if i < len(self.strings[1]) else None

    def blend_paths(self, node):
        h = node.header
        return [self.strings[5][i] for i in (h.blend_index_a, h.blend_index_b) if i < len(self.strings[5])]


if __name__ == "__main__":  # pragma: no cover
    import sys
    for p in sys.argv[1:]:
        d = open(p, "rb").read()
        c = Chart.parse(d)
        print(p, len(d), "nodes", len(c.nodes), "actions", len(c.actions), "branches", len(c.branches),
              "roundtrip", c.pack() == d)
