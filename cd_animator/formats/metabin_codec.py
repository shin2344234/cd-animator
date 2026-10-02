"""Reader and writer for .paa_metabin (the animation metadata sibling of a .paa).

One metabin per .paa clip, in pack group 0010 under
actionchart/bin__/animmeta/<same folder layout as the clip>/<clip>.paa_metabin.
It is a reflection-serialised `AnimationMetaData` object. Sizes seen: 99 to
112106 bytes. This module parses and rebuilds all 31723 metabins checked
(every cd_phm_*, cd_rd_*, and unique_kliff_* file in group 0010) byte for
byte; rider_and_metabin.md has the evidence and the confidence per field.

Layout (little-endian)

    0x00  82 bytes   PREAMBLE, identical in every file: the type header
                     (0xFFFF, 4, 15, 1, the 17 character name
                     "AnimationMetaData", type ids 0x51 and 0x4B, ...).
                     Kept verbatim.
    0x52  u8   flags     bit0 position keys present   bit1 rotation keys present
                         bit2 more than one position key   bit3 more than one rotation key
                         (matches all 31723 files; see expected_flags())
    0x53  u16  list1_count   0 in every file. Whatever it counts is never used.
    0x55  u16  phase_count
          phase_count x 22 bytes:  f32 t0, f32 t1, u8 a, u8 b, f32 x, f32 y, f32 z
                         a timed window (seconds) with two small selectors
                         and a vector. Seen on mount and dismount clips.
          u16  event_count
          event_count x 9 bytes:   f32 begin, f32 end, u8 type
                         timed tags in seconds, sorted by begin, type 0..7.
          u8   y, u8 z          two bytes, meaning unknown
          u32  motion_size      0 = no motion block, else 8 + 10*nrot + 8*npos
          [motion block]
              u32 nrot, u32 npos
              nrot x { u16 frame, 4 x binary16 x y z w }
              npos x { u16 frame, 3 x binary16 x y z }
                         a copy of the clip's B_MoveControl_01 track: the
                         rotation keys are identical to the clip's, the
                         position keys are a subset rounded to half floats
          f32  duration         clip length in seconds, = frames / 30, equal
                                to the duration inside the .paa lead

Times are seconds. The clip runs at 30 fps, so frame = round(seconds * 30).
Event and phase times fall on half frames. Events may run past the clip's
duration (a walkfast clip of 2.0 s has an event to 2.33 s).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .paa_codec import RotKey, PosKey

PREAMBLE = bytes.fromhex(
    "ffff0400000000000000000000000f00"
    "0000010011000000416e696d6174696f"
    "6e4d6574614461746100000000000001"
    "0000005100000000000000ffffffffff"
    "ffffff4b000000060000000000000000"
    "0005"
)
assert len(PREAMBLE) == 82

HEADER_END = 0x52


@dataclass
class Phase:
    t0: float
    t1: float
    a: int
    b: int
    x: float
    y: float
    z: float


@dataclass
class Event:
    begin: float
    end: float
    type: int


def rising_prefix(keys):
    """Longest prefix of a key list whose frames strictly rise."""
    n = 1 if keys else 0
    while n < len(keys) and keys[n].frame > keys[n - 1].frame:
        n += 1
    return keys[:n]


@dataclass
class MotionTrack:
    """rot_keys keeps the count the file stores. In 5551 of the 31723 files
    the rotation list is a rising run of keys followed by a stale copy of the
    original list's tail (keys were dropped, the count was not lowered), so
    use live_rot_keys() for the real keys. Position lists are clean."""
    rot_keys: list = field(default_factory=list)   # RotKey
    pos_keys: list = field(default_factory=list)   # PosKey (aux unused)

    def live_rot_keys(self):
        return rising_prefix(self.rot_keys)


@dataclass
class Metabin:
    flags: int
    phases: list
    events: list
    y: int
    z: int
    motion: MotionTrack | None
    duration: float
    preamble: bytes = PREAMBLE
    list1_count: int = 0

    def expected_flags(self) -> int:
        return expected_flags(self.motion)


def expected_flags(motion) -> int:
    nrot = len(motion.rot_keys) if motion else 0
    npos = len(motion.pos_keys) if motion else 0
    return (int(npos > 0) | (int(nrot > 0) << 1) | (int(npos > 1) << 2)
            | (int(nrot > 1) << 3))


def read_metabin(data: bytes) -> Metabin:
    n = len(data)
    if n < HEADER_END + 5:
        raise ValueError("metabin too short")
    pre = data[:HEADER_END]
    if pre != PREAMBLE:
        raise ValueError("unknown preamble (not an AnimationMetaData metabin of this layout)")
    o = HEADER_END
    flags = data[o]
    list1, nph = struct.unpack_from("<HH", data, o + 1)
    o += 5
    if list1:
        raise ValueError("list1_count is not 0; item size unknown")
    phases = []
    for _ in range(nph):
        t0, t1, a, b, x, y, z = struct.unpack_from("<2f2B3f", data, o)
        phases.append(Phase(t0, t1, a, b, x, y, z))
        o += 22
    ne = struct.unpack_from("<H", data, o)[0]
    o += 2
    events = []
    for _ in range(ne):
        b, e, t = struct.unpack_from("<2fB", data, o)
        events.append(Event(b, e, t))
        o += 9
    y, z = data[o], data[o + 1]
    o += 2
    size = struct.unpack_from("<I", data, o)[0]
    o += 4
    motion = None
    if size:
        nrot, npos = struct.unpack_from("<2I", data, o)
        if 8 + 10 * nrot + 8 * npos != size:
            raise ValueError("motion block size does not match its key counts")
        p = o + 8
        rk = []
        for _ in range(nrot):
            fr = struct.unpack_from("<H", data, p)[0]
            rk.append(RotKey(fr, *struct.unpack_from("<4e", data, p + 2)))
            p += 10
        pk = []
        for _ in range(npos):
            fr = struct.unpack_from("<H", data, p)[0]
            pk.append(PosKey(fr, *struct.unpack_from("<3e", data, p + 2)))
            p += 8
        motion = MotionTrack(rk, pk)
    o += size
    duration = struct.unpack_from("<f", data, o)[0]
    o += 4
    if o != n:
        raise ValueError(f"{n - o} bytes left after the duration")
    return Metabin(flags, phases, events, y, z, motion, duration, pre, list1)


def write_metabin(m: Metabin) -> bytes:
    out = bytearray(m.preamble)
    out += struct.pack("<BHH", m.flags, m.list1_count, len(m.phases))
    for p in m.phases:
        out += struct.pack("<2f2B3f", p.t0, p.t1, p.a, p.b, p.x, p.y, p.z)
    out += struct.pack("<H", len(m.events))
    for e in m.events:
        out += struct.pack("<2fB", e.begin, e.end, e.type)
    out += struct.pack("<BB", m.y, m.z)
    if m.motion is None:
        out += struct.pack("<I", 0)
    else:
        rk, pk = m.motion.rot_keys, m.motion.pos_keys
        out += struct.pack("<III", 8 + 10 * len(rk) + 8 * len(pk), len(rk), len(pk))
        for k in rk:
            out += struct.pack("<H4e", k.frame, k.x, k.y, k.z, k.w)
        for k in pk:
            out += struct.pack("<H3e", k.frame, k.x, k.y, k.z)
    out += struct.pack("<f", m.duration)
    return bytes(out)


def check_metabin(m: Metabin, clip_duration: float | None = None):
    """Problems as a list of strings (empty is good)."""
    problems = []
    if m.flags != m.expected_flags():
        problems.append(f"flags {m.flags} but the motion block implies {m.expected_flags()}")
    b = [e.begin for e in m.events]
    if b != sorted(b):
        problems.append("events are not sorted by begin time")
    for i, e in enumerate(m.events):
        if e.type > 7:
            problems.append(f"event {i}: type {e.type} outside 0..7")
        if e.end < e.begin:
            problems.append(f"event {i}: ends before it begins")
    if m.motion:
        for label, keys in (("rot", m.motion.live_rot_keys()), ("pos", m.motion.pos_keys)):
            fr = [k.frame for k in keys]
            if any(b2 <= b1 for b1, b2 in zip(fr, fr[1:])):
                problems.append(f"motion {label} frames not strictly rising")
            if fr and fr[-1] > round(m.duration * 30) + 1:
                problems.append(f"motion {label} runs past the duration")
    if clip_duration is not None and abs(clip_duration - m.duration) > 1e-6:
        problems.append(f"duration {m.duration} differs from the clip's {clip_duration}")
    return problems


def new_metabin(duration: float, events=(), phases=(), motion: MotionTrack | None = None,
                y: int = 0, z: int = 4) -> Metabin:
    """A metabin for a new clip, with the flags derived from the motion block.
    y and z default to the commonest values (0, 4); the broom's move clips
    use (0, 12). Their meaning is not known."""
    return Metabin(expected_flags(motion), list(phases), sorted(events, key=lambda e: e.begin),
                   y, z, motion, duration)


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        raw = open(path, "rb").read()
        mb = read_metabin(raw)
        print(path, "OK" if write_metabin(mb) == raw else "MISMATCH",
              f"flags={mb.flags} phases={len(mb.phases)} events={len(mb.events)} "
              f"motion={'-' if not mb.motion else (len(mb.motion.rot_keys), len(mb.motion.pos_keys))} "
              f"duration={mb.duration:.4f}")
