"""Crimson Desert action charts (.paac): the game's state machines, which
say which clip each state plays.

From Broomy's research (its chart schema, MIT), reverse engineered from
the game's own reader for build 1.0.0.2976. A chart is a flat run of count-prefixed
arrays with no offsets, so it parses to the last byte and packs back byte
for byte from the tree; 556 of the game's 558 charts do.

A node is one clip and its timed parameters; it names the clip by an index
into the chart's second string table (strings[1]), which holds .paa paths
relative to character/motion/. An action, the state, owns a run of nodes.

Reverse engineered from the game's own deserializer (top level RVA 0x1F67A00, AnimationInfo reader
0x1F66560, chart tail reader 0x1F68370 + 0x1F684D9, see paac_schema.md for every RVA).  The format is
a flat sequence of count-prefixed arrays; nothing is compressed and no field is a file offset, so a
chart parses to exactly the last byte and packs back byte for byte from the tree.

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
    # ---- AnimationInfoData, the 0x9C byte block that starts every node (read in place) -------
    "AnimationInfoData": _L(
        "AnimationInfoData", 0x9C,
        (0x04, "f32", "duration"),         # <0 means "use the clip length" (0x232E6F3..0x232E810)
        (0x08, "u32", "group_hash"),       # compared with a hash at 0x2308AE7
        # per array i: u16 byte offset of the array inside the node's array area (running sum of
        # the earlier count*size, recomputed on pack) at 0x68+4i, u8 count at 0x6A+4i (read by the
        # loader at 0x1F665EA..0x1F6678F); the high byte of the count is always 0.
        *[(0x68 + 4 * i, "u16", "arr%d_offset" % i) for i in range(10)],
        *[(0x6A + 4 * i, "u8", "arr%d_count" % i) for i in range(10)],
        (0x90, "u16", "anim_index_a"),     # index into strings[1] (.paa), always equal to anim_index
        (0x92, "u16", "anim_index"),       # index into strings[1]; hashed at 0x1F66AC0
        (0x94, "u16", "unk_94"),
        (0x96, "u16", "blend_index_a"),    # index into strings[5] (.motionblending), 0xFFFF none (0x1F66B01)
        (0x98, "u16", "blend_index_b"),    # index into strings[5], 0xFFFF none (0x1F66B7A)
    ),
    # ---- the ten AnimationInfo arrays; names are the game's load error labels ----------------
    # frameTag: a branch whose frame_tag matches may only fire while the playback time is inside
    # [time_start, time_end] of a window with that tag (check at 0x232E860..0x232E8D9)
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
    # frame event instance: when playback passes `time`, the event whose payload starts at word
    # `event_index` of chart.frame_event_buffer fires (node post pass at 0x1F66A78 reads +8)
    "FrameEventInstance": _L("FrameEventInstance", 20, (0x00, "f32", "time"), (0x04, "f32", "time_end"),
                             (0x08, "u32", "event_index"), (0x0C, "u32", "ordinal"), (0x10, "u32", "unk_10")),
    # ---- chart level records -------------------------------------------------------------------
    # "actionChart": one 0x114 byte record per action (the state), ctx+0x228
    "Action": _L(
        "Action", 0x114,
        (0x18, "u32", "key_hash"),         # hashlittle(name, 0xC5EDE); branch targets match it (0x2308A1C)
        (0x54, "u32", "node_first"),       # node range, 0x2308AB9 / 0x1F680E3
        (0xA8, "u32", "list64_index"),     # fits chart.list64 (guess)
        (0xAC, "u32", "list32a_index"),    # fits chart.list32a (guess)
        (0xE0, "u16", "slot_first"),       # range of chart.slots
        (0xE2, "u16", "slot_first_hi"),    # always 0xFFFF
        (0xE4, "u16", "slot_count"),
        (0xEA, "u16", "node_count"),       # 0x2308AA8
    ),
    # branchInstanceArray, element 1: the branch itself
    "Branch": _L(
        "Branch", 52,
        (0x00, "f32", "unk_00_f"),
        (0x08, "f32", "time_a"),           # guess: blend length in frames
        (0x0C, "f32", "time_b"),           # guess: blend length for layer 1, -1 = unset
        (0x14, "u32", "target_hash"),      # key_hash of the target action (layer 0), 0x232CF5C
        (0x18, "u32", "target_hash2"),     # target for layer 1 when non zero, 0x232CF65
        (0x1C, "u8", "kind"),              # 4 input, 5, 7 animation end, 20, 12; bit 1 tested at 0x232E493
        (0x1D, "u8", "flags"),
        (0x20, "u32", "input_hash"),       # hashlittle(input name, 0xC5EDE); 0 when not input driven
        (0x24, "u16", "cond_first"),       # first token of the branch condition (index into condition_offsets)
        (0x26, "u16", "keycond_first"),    # first token of the key condition (index into condition_offsets)
        (0x2A, "u8", "cond_count"),        # 0x232E973
        (0x2B, "u8", "keycond_count"),     # 0x232E5CA
        (0x2D, "u8", "frame_tag"),         # 0x28 = none, else must match a FrameTag tag (0x232E6B5)
        (0x2E, "u8", "frame_tag2"),        # always 0x28 in shipped charts
        (0x2F, "u8", "unk_2F"),            # 0x1E (30) by default
    ),
    # branchInstanceArray, element 3: one entry of an action's branch list (ctx+0x150); points at
    # a branch and adds a time window, a condition and an input filter.  Read in place by 0x232D5C0.
    "Slot": _L("Slot", 28,
               (0x00, "u32", "unk_00_hash"),
               (0x04, "f32", "time_min"),      # branch only fires inside [time_min, time_max] (0x232DA74)
               (0x08, "f32", "time_max"),      # FLT_MAX = open end
               (0x0C, "u16", "branch_index"),  # index into chart.branches (0x232DC32)
               (0x0E, "u16", "cond_first"),    # slot condition tokens, used when flags & 0x0C (0x232DB01)
               (0x10, "u16", "filter_first"),  # range in chart.list32b of input hashes (0x232DEF1..0x232DF47)
               (0x18, "u8", "filter_count"),
               (0x19, "u8", "flags"),
               (0x1A, "u8", "cond_count"),
               (0x1B, "u8", "unk_1B")),
    "DefaultSocket": _L("DefaultSocket", 40, (0x00, "u16", "index")),
    "ActionRec12": _L("ActionRec12", 12),          # three u32 hashes, shares the "actionChart" label
    "BranchRec8": _L("BranchRec8", 8),             # branchInstanceArray, element 2 (ctx+0x140)
    "KeyGuideInstance": _L("KeyGuideInstance", 28),
    "KeyGuidePair": _L("KeyGuidePair", 8),
}

NODE_ARR_LAYOUTS = ["FrameTag", "AnimationSpeedInfo", "MoveSpeedInfo", "AiMoveSpeedInfo", "VerticalMoveSpeedInfo",
                    "DefenceInfo", "CharacterClimbTagInfo", "OnHitEventInfo", "StumbleOnHitInfo",
                    "AiReviseTurnInfo"]
NODE_ARR_ATTRS = ["frame_tags", "animation_speeds", "move_speeds", "ai_move_speeds", "vertical_move_speeds",
                  "defence_infos", "climb_tags", "on_hit_events", "stumble_on_hits", "ai_revise_turns"]
NODE_ARR_SIZES = [LAYOUTS[n].size for n in NODE_ARR_LAYOUTS]
assert NODE_ARR_SIZES == [12, 16, 0x68, 0x94, 24, 36, 12, 96, 12, 12]
# the ten string tables, by content (the game only calls them "stringTable")
STRING_LIST_NAMES = ["names", "anim_paa", "camera_paa", "effect", "pafx", "motionblending",
                     "bone", "item", "baseseq", "prefab"]


# Words per entry, observed.  frame_event_buffer: the low u16 of an entry's first word is its type and
# decides the entry length.  Condition tokens: the first word is the id.  Both tables come from the 556
# shipped charts (entries are measured from the gap to the next referenced entry), 149 event types and
# 460 token ids; ids missing here have not been seen.
FRAME_EVENT_WORDS = {
    0x0: 3, 0x1: 3, 0x2: 3, 0x3: 3, 0x4: 24, 0x5: 10, 0x6: 3, 0x7: 74, 0x8: 3, 0x9: 10,
    0xA: 19, 0xB: 65, 0xC: 7, 0xD: 5, 0xE: 28, 0xF: 7, 0x11: 4, 0x12: 4, 0x13: 4, 0x14: 5,
    0x15: 5, 0x16: 6, 0x17: 3, 0x18: 2, 0x19: 60, 0x1A: 5, 0x1B: 3, 0x1D: 4, 0x1E: 3, 0x1F: 2,
    0x20: 3, 0x21: 3, 0x22: 3, 0x23: 5, 0x24: 3, 0x25: 36, 0x26: 5, 0x27: 63, 0x28: 7, 0x29: 2,
    0x2A: 4, 0x2B: 5, 0x2C: 22, 0x2D: 4, 0x2E: 3, 0x2F: 10, 0x30: 13, 0x31: 4, 0x32: 6,
    0x33: 10, 0x34: 2, 0x35: 13, 0x36: 5, 0x37: 88, 0x38: 15, 0x39: 90, 0x3B: 7, 0x3C: 7,
    0x3D: 5, 0x3E: 3, 0x3F: 3, 0x40: 7, 0x41: 58, 0x42: 29, 0x43: 5, 0x44: 11, 0x45: 14,
    0x46: 9, 0x47: 3, 0x49: 14, 0x4A: 18, 0x4B: 4, 0x4C: 6, 0x4D: 9, 0x4E: 7, 0x4F: 4,
    0x50: 17, 0x51: 3, 0x52: 5, 0x53: 3, 0x55: 4, 0x57: 14, 0x59: 5, 0x5A: 3, 0x5B: 5, 0x5C: 5,
    0x5D: 4, 0x5E: 8, 0x5F: 6, 0x60: 6, 0x61: 16, 0x62: 4, 0x64: 5, 0x65: 12, 0x66: 8, 0x6D: 3,
    0x6E: 4, 0x6F: 146, 0x70: 84, 0x71: 11, 0x72: 2, 0x73: 3, 0x74: 6, 0x77: 6, 0x78: 3,
    0x79: 3, 0x7A: 8, 0x7B: 7, 0x7C: 12, 0x7D: 5, 0x7E: 10, 0x7F: 8, 0x80: 5, 0x81: 43,
    0x82: 8, 0x83: 9, 0x84: 3, 0x86: 10, 0x87: 7, 0x88: 2, 0x89: 12, 0x8A: 2, 0x8B: 5, 0x8E: 9,
    0x8F: 9, 0x90: 5, 0x91: 10, 0x92: 14, 0x93: 4, 0x94: 6, 0x96: 16, 0x97: 2, 0x9A: 46,
    0x9B: 4, 0x9C: 2, 0x9E: 3, 0x9F: 13, 0xA0: 20, 0xA1: 18, 0xA2: 3, 0xA3: 5, 0xA4: 5,
    0xA5: 3, 0xA6: 3, 0xA8: 3, 0xA9: 4, 0xAB: 3, 0xAC: 2, 0xAE: 9,
}

CONDITION_TOKEN_WORDS = {
    0x0: 2, 0x1: 1, 0x2: 1, 0x3: 1, 0x4: 1, 0x5: 1, 0x6: 1, 0x7: 1, 0x8: 1, 0x9: 1, 0xC: 1,
    0xD: 1, 0xE: 1, 0x10: 1, 0x13: 1, 0x14: 1, 0x15: 1, 0x16: 1, 0x17: 1, 0x18: 1, 0x21: 1,
    0x22: 1, 0x23: 1, 0x24: 1, 0x25: 1, 0x27: 1, 0x29: 1, 0x2C: 1, 0x32: 1, 0x33: 1, 0x36: 1,
    0x37: 1, 0x38: 1, 0x39: 1, 0x3A: 1, 0x3B: 1, 0x3C: 1, 0x3D: 1, 0x3E: 1, 0x3F: 1, 0x40: 1,
    0x41: 1, 0x45: 1, 0x49: 1, 0x4A: 1, 0x4E: 1, 0x4F: 1, 0x5C: 1, 0x5D: 1, 0x5E: 1, 0x5F: 1,
    0x61: 1, 0x62: 1, 0x65: 1, 0x66: 1, 0x67: 1, 0x68: 1, 0x69: 1, 0x6A: 1, 0x6D: 1, 0x6E: 1,
    0x74: 1, 0x79: 1, 0x7B: 1, 0x7C: 1, 0x7D: 1, 0x7F: 1, 0x80: 1, 0x81: 1, 0x82: 1, 0x83: 1,
    0x84: 1, 0x86: 1, 0x88: 1, 0x89: 1, 0x8B: 1, 0x8D: 1, 0x8E: 1, 0x8F: 1, 0x90: 1, 0x92: 1,
    0x93: 1, 0x94: 1, 0x96: 1, 0x97: 1, 0x9B: 1, 0x9C: 1, 0x9D: 1, 0x9F: 1, 0xA1: 1, 0xA2: 1,
    0xA3: 1, 0xA4: 1, 0xA5: 1, 0xA6: 1, 0xA7: 1, 0xAC: 1, 0xAE: 1, 0xB0: 1, 0xB1: 1, 0xB2: 1,
    0xB3: 1, 0xB5: 1, 0xB6: 1, 0xB7: 1, 0xB8: 5, 0xBA: 5, 0xBB: 5, 0xBC: 1, 0xBD: 1, 0xBE: 1,
    0xBF: 1, 0xC0: 1, 0xC1: 1, 0xC2: 1, 0xC4: 5, 0xC5: 5, 0xC6: 5, 0xC7: 5, 0xC9: 5, 0xCA: 5,
    0xCC: 5, 0xCE: 5, 0xD1: 5, 0xD4: 5, 0xD5: 5, 0xD6: 5, 0xD7: 5, 0xD8: 5, 0xD9: 5, 0xDA: 5,
    0xDB: 5, 0xDC: 5, 0xDD: 5, 0xDF: 5, 0xE1: 5, 0xE2: 5, 0xE3: 5, 0xE4: 5, 0xE5: 5, 0xE7: 5,
    0xE8: 5, 0xE9: 5, 0xEA: 5, 0xEB: 5, 0xEC: 5, 0xED: 5, 0xEE: 5, 0xEF: 5, 0xF0: 5, 0xF1: 5,
    0xF3: 5, 0xF4: 5, 0xF5: 5, 0xF6: 5, 0xF7: 5, 0xFA: 5, 0xFC: 5, 0xFE: 1, 0xFF: 1, 0x100: 5,
    0x103: 5, 0x104: 5, 0x105: 5, 0x106: 5, 0x107: 5, 0x108: 5, 0x109: 5, 0x10A: 5, 0x10C: 5,
    0x10D: 5, 0x10E: 5, 0x10F: 5, 0x110: 5, 0x112: 5, 0x115: 5, 0x116: 1, 0x117: 5, 0x11A: 5,
    0x11D: 5, 0x11E: 1, 0x11F: 5, 0x121: 5, 0x122: 5, 0x123: 5, 0x124: 5, 0x125: 1, 0x126: 5,
    0x127: 5, 0x128: 5, 0x129: 5, 0x12A: 5, 0x12B: 5, 0x12C: 1, 0x12D: 5, 0x12F: 5, 0x130: 5,
    0x132: 5, 0x133: 5, 0x135: 5, 0x136: 5, 0x137: 5, 0x138: 5, 0x139: 5, 0x13A: 5, 0x13B: 5,
    0x13C: 5, 0x13D: 5, 0x13E: 5, 0x144: 5, 0x145: 5, 0x146: 5, 0x147: 5, 0x149: 5, 0x14A: 5,
    0x14B: 5, 0x14D: 1, 0x150: 5, 0x151: 5, 0x152: 1, 0x153: 1, 0x154: 5, 0x155: 1, 0x156: 5,
    0x158: 5, 0x15A: 5, 0x15B: 5, 0x15C: 1, 0x15D: 1, 0x15E: 1, 0x15F: 1, 0x160: 5, 0x161: 5,
    0x162: 1, 0x163: 5, 0x164: 5, 0x165: 5, 0x166: 1, 0x167: 5, 0x16B: 5, 0x16C: 5, 0x16E: 5,
    0x16F: 5, 0x170: 5, 0x171: 5, 0x172: 5, 0x173: 1, 0x174: 5, 0x175: 5, 0x176: 5, 0x177: 5,
    0x178: 5, 0x179: 5, 0x17A: 5, 0x17B: 1, 0x17D: 5, 0x17E: 5, 0x17F: 5, 0x183: 5, 0x184: 1,
    0x186: 1, 0x188: 1, 0x189: 5, 0x18A: 1, 0x18B: 5, 0x18C: 5, 0x18D: 5, 0x18E: 5, 0x190: 5,
    0x191: 5, 0x192: 1, 0x194: 5, 0x195: 5, 0x196: 5, 0x197: 5, 0x198: 5, 0x199: 5, 0x19A: 5,
    0x19B: 5, 0x19C: 5, 0x19D: 1, 0x19E: 5, 0x19F: 5, 0x1A0: 1, 0x1A2: 1, 0x1A3: 1, 0x1A4: 5,
    0x1A5: 5, 0x1A6: 5, 0x1A7: 5, 0x1A9: 1, 0x1AB: 1, 0x1AC: 5, 0x1AD: 5, 0x1AE: 5, 0x1AF: 5,
    0x1B1: 5, 0x1B2: 5, 0x1B3: 1, 0x1B4: 5, 0x1B5: 5, 0x1B6: 5, 0x1B7: 5, 0x1B9: 5, 0x1BA: 5,
    0x1BC: 5, 0x1BD: 5, 0x1BE: 5, 0x1BF: 5, 0x1C0: 5, 0x1C1: 5, 0x1C2: 5, 0x1C3: 5, 0x1C4: 5,
    0x1C5: 5, 0x1C6: 5, 0x1C7: 5, 0x1C8: 5, 0x1C9: 5, 0x1CB: 1, 0x1CC: 5, 0x1CD: 5, 0x1CE: 5,
    0x1CF: 5, 0x1D0: 5, 0x1D1: 5, 0x1D2: 5, 0x1D3: 5, 0x1D4: 5, 0x1D5: 5, 0x1D6: 5, 0x1D7: 5,
    0x1DA: 5, 0x1DC: 5, 0x1DD: 5, 0x1DE: 5, 0x1DF: 5, 0x1E0: 5, 0x1E1: 5, 0x1E2: 1, 0x1E3: 5,
    0x1E4: 5, 0x1E5: 5, 0x1E6: 1, 0x1E8: 5, 0x1E9: 5, 0x1EA: 5, 0x1EB: 5, 0x1EC: 5, 0x1ED: 1,
    0x1EF: 5, 0x1F0: 5, 0x1F2: 5, 0x1F3: 5, 0x1F4: 5, 0x1F5: 5, 0x1F6: 5, 0x1F7: 5, 0x1F8: 5,
    0x1F9: 5, 0x1FA: 5, 0x1FB: 1, 0x1FC: 5, 0x1FD: 5, 0x1FE: 5, 0x1FF: 5, 0x201: 5, 0x202: 5,
    0x203: 5, 0x204: 5, 0x205: 5, 0x208: 5, 0x20B: 5, 0x20C: 5, 0x20D: 5, 0x20E: 5, 0x210: 5,
    0x211: 5, 0x212: 5, 0x213: 5, 0x216: 5, 0x217: 5, 0x218: 1, 0x219: 5, 0x21A: 5, 0x21B: 5,
    0x21C: 5, 0x21D: 1, 0x21E: 1, 0x21F: 1, 0x220: 5, 0x221: 5, 0x222: 5, 0x223: 5, 0x226: 5,
    0x227: 1, 0x228: 1, 0x229: 1, 0x22A: 1, 0x22B: 1, 0x22C: 1, 0x22D: 1, 0x22E: 5, 0x22F: 5,
    0x230: 1, 0x231: 1, 0x237: 5, 0x238: 5, 0x239: 5, 0x23A: 5, 0x23B: 5, 0x23C: 5, 0x23E: 1,
    0x23F: 1, 0x240: 1, 0x241: 1, 0x242: 5, 0x243: 5, 0x244: 5, 0x245: 5, 0x246: 5, 0x248: 5,
    0x249: 1, 0x24A: 5, 0x24B: 5, 0x24C: 5, 0x24D: 5, 0x251: 5, 0x252: 5, 0x253: 5, 0x254: 5,
    0x255: 1, 0x256: 5, 0x258: 5, 0x25A: 5, 0x25B: 5, 0x25C: 5, 0x25D: 5, 0x25E: 5, 0x25F: 1,
    0x260: 5, 0x261: 5, 0x262: 5, 0x263: 5, 0x264: 5, 0x265: 5, 0x266: 5, 0x267: 1, 0x268: 5,
    0x26A: 5, 0x26C: 5, 0x26D: 5, 0x26E: 5, 0x26F: 5, 0x271: 5, 0x272: 5, 0x273: 1, 0x275: 1,
    0x276: 1, 0x277: 1,
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
    """One AnimationInfo (a 0x50 byte runtime object built by 0x1F66560): the animation clip and
    its timed parameters.  An action owns a run of consecutive nodes (Action.node_first/node_count).

    header                  AnimationInfoData (0x9C bytes)
    arrays[0..9]            ten arrays of fixed records; the same lists are also reachable as
                            frame_tags, animation_speeds, move_speeds, ai_move_speeds,
                            vertical_move_speeds, defence_infos, climb_tags, on_hit_events,
                            stumble_on_hits, ai_revise_turns
    frame_event_words       u32 list, "actionChartFrameEvent_InstanceArray" data (condition tokens)
    frame_event_offsets     u16 list, start of each token inside frame_event_words
    frame_event_instances   FrameEventInstance list (u8 count), "_frameEventInstanceBuffer"
    random_frame_events     list of (u32 list, u8 list), "_randomFrameEventArray"; empty in shipped charts
    """

    def __init__(self):
        self.header = Rec(LAYOUTS["AnimationInfoData"])
        self.arrays = [[] for _ in range(10)]
        self.frame_event_words = []
        self.frame_event_offsets = []
        self.frame_event_instances = []
        self.random_frame_events = []

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

    @classmethod
    def parse(cls, r):
        n = cls()
        n.header = Rec.parse(LAYOUTS["AnimationInfoData"], r.raw(0x9C))
        h = n.header
        for i in range(10):
            if h._v[h._L.index["unk_%02X" % (0x6B + 4 * i)]]:
                raise ParseError("nonzero high byte of array count %d" % i)
            n.arrays[i] = r.recs(LAYOUTS[NODE_ARR_LAYOUTS[i]], h._v[h._L.index["arr%d_count" % i]])
        nbytes = r.u32()
        if nbytes % 4:
            raise ParseError("node frame event data length %d not a multiple of 4" % nbytes)
        n.frame_event_words = r.words(nbytes // 4, "I")
        n.frame_event_offsets = r.words(r.u32(), "H")
        n.frame_event_instances = r.recs(LAYOUTS["FrameEventInstance"], r.u8())
        for _ in range(r.u8()):
            m = r.u8()
            n.random_frame_events.append((r.words(m, "I"), r.words(m, "B")))
        return n

    def pack(self, out):
        h = Rec(self.header._L, self.header._v)
        off = 0
        for i in range(10):
            if len(self.arrays[i]) > 255:
                raise ValueError("node array %d has more than 255 records" % i)
            h._v[h._L.index["arr%d_count" % i]] = len(self.arrays[i])
            h._v[h._L.index["arr%d_offset" % i]] = off
            off += len(self.arrays[i]) * NODE_ARR_SIZES[i]
        out.append(h.pack())
        for i in range(10):
            for rec in self.arrays[i]:
                out.append(rec.pack())
        _w(out, "I", len(self.frame_event_words) * 4)
        _words(out, "I", self.frame_event_words)
        _w(out, "I", len(self.frame_event_offsets))
        _words(out, "H", self.frame_event_offsets)
        _w(out, "B", len(self.frame_event_instances))
        for rec in self.frame_event_instances:
            out.append(rec.pack())
        _w(out, "B", len(self.random_frame_events))
        for words, bytes_ in self.random_frame_events:
            _w(out, "B", len(words))
            _words(out, "I", words)
            _words(out, "B", bytes_)


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
            raise ParseError("reflection stub (0x2591840) is non-empty; its element readers are not decoded")
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
