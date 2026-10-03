"""Keyframe codec for Crimson Desert .paa animation clips (build 2.03.02).

Decodes and re-encodes every layout the game ships: full clips
(character/motion/...) and LOD clips (character/motion/motion_lod__/...,
the "_lod.paa" files), for any skeleton. On 3 October 2026 all 280,011 full
clips of pack group 0009 but three, and all 267,132 LOD clips, parsed to their
last byte with every block's key count matching the lead.

Layout (all integers little-endian)

    0x00  "PAR ", u8 2 (animation), u8 version (3), 10 bytes 00..09
    0x10  u16 flags
    0x12  u16 tag marker: 0 for no tag, 0xC000 for a UTF-8 tag (u16 byte
          length, NUL included, then the bytes), 0x8000 for a UTF-16 tag
          (u16 length in characters, no NUL). Tags are Korean keywords such
          as "<male>;<broom>;".
          FLAG_SOURCE: u32 hashlittle(<the full clip's bytes>, 0xC5EDE)

    then the lead, each field present only when its flag is set:
          FLAG_REC1      10 x f32  a transform: scale xyz, quat xyzw, pos xyz
          FLAG_REC2      10 x f32  a second transform, same layout
          FLAG_REF       f32       ref_scale (0.9723 on Kliff's clips)
          FLAG_SKELETON  u8 length and the skeleton's path, no NUL
          always         f32       duration in seconds
          FLAG_KINDS     u16 n (5), then n u16 block counts, one per key kind
          otherwise      u16 count of KIND_HALF blocks, u16 of KIND_FLOAT
          always         u32       total key bytes of all blocks

    then the blocks, ordered by kind: one per animated bone, in an order
    derived from the skeleton. Bones without keys are absent. A block holds
    scale, rotation and position keys, each list after its own count:

      KIND_HALF   u32 hashlittle(bone name, 0xC5EDE)
                  u16 n, n x { u16 frame, 3 x binary16 }      scale
                  u16 n, n x { u16 frame, 4 x binary16 }      quat xyzw
                  u16 n, n x { u16 frame, 3 x binary16 }      position
      KIND_FLOAT  as KIND_HALF, but position keys are
                  { u16 frame, u16 aux, 3 x f32 }. aux is uninitialised
                  padding, the same stale number in every key; it is kept
                  so the round trip is exact, and new keys write 0.
      KIND_I8     (LOD clips) u8 counts and u8 frames:
                  u32 hash, u8 n, n x { u8 frame, 3 x i8 / 32 }  scale
                  u8 n, n x { u8 frame, 4 x i8 / 64 }            quat
                  u8 n, n x { u8 frame, 3 x i8 / 32 }            position

Frame numbers count 30 fps frames, except in KIND_I8 blocks, which count 1/5
second ticks (frame / 6). Kinds 0 and 4 are counted but no clip uses them.

A LOD clip carries its full clip's flags with LOD_FLAGS added (checked on
3,000 pairs): FLAG_SOURCE, 0x80 and FLAG_KINDS. Its KIND_I8 blocks come from
the full clip's KIND_HALF bones and its KIND_HALF blocks from the KIND_FLOAT
ones. Flags 0x08, 0x20 and 0x80 change nothing in the layout and are kept as
read.

Scale keys are rare outside facial clips: most body tracks that have them
hold 1.0 on two keys. The block field earlier versions called "flags" (0 in
every broom clip) is the scale key count.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field as dc_field

from . import paa as _paa

from .hashlittle import hashlittle

HASH_SEED = 0xC5EDE

FLAG_REC1 = 0x01
FLAG_REF = 0x02
FLAG_REC2 = 0x04
FLAG_SOURCE = 0x10
FLAG_SKELETON = 0x40
FLAG_KINDS = 0x100
LOD_FLAGS = 0x190

TAG_UTF8 = 0xC000
TAG_UTF16 = 0x8000

KIND_I8, KIND_HALF, KIND_FLOAT = 1, 2, 3
KIND_SLOTS = 5
LOD_TICK = 6        # 30 fps frames per KIND_I8 frame number

BONE_NAMES = [
    "Bip01", "B_TL_Position_02", "B_TL_Position_01", "B_MoveControl_01",
    "B_Body_00", "B_EnemyCatch_00", "B_CatchMe_00", "B_Rider_01", "B_Rider_02",
]


def bone_hash(name: str) -> int:
    return hashlittle(name.encode("cp949"), HASH_SEED)


def hash_names(names=BONE_NAMES):
    return {bone_hash(n): n for n in names}


NAME_BY_HASH = hash_names()
HASH_BY_NAME = {v: k for k, v in NAME_BY_HASH.items()}


def register_names(names):
    """Teach the decoder more bone names (hash -> name)."""
    for n in names:
        h = bone_hash(n)
        NAME_BY_HASH.setdefault(h, n)
        HASH_BY_NAME.setdefault(n, h)


def names_from_pab(pab_bytes: bytes):
    sk = _paa.read_pab(pab_bytes)
    return [b.name for b in sk.bones]


# Kliff's skeleton (phm_01.pab, 447 bones), shipped beside this file.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PHM_NAMES = os.path.join(_HERE, "phm_01_bones.txt")
if os.path.exists(_PHM_NAMES):
    with open(_PHM_NAMES, encoding="utf-8") as _f:
        register_names([ln.strip() for ln in _f if ln.strip()])


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class RotKey:
    frame: int
    x: float
    y: float
    z: float
    w: float


@dataclass
class PosKey:
    """A position or scale key."""
    frame: int
    x: float
    y: float
    z: float
    aux: int = 0          # KIND_FLOAT position keys only: the padding u16


@dataclass
class BoneTrack:
    name: str             # resolved bone name, or "unk_XXXXXXXX"
    name_hash: int
    rot_keys: list
    pos_keys: list
    kind: int = KIND_HALF
    scale_keys: list = dc_field(default_factory=list)


def frame_step(kind):
    """30 fps frames per stored frame number in a block of this kind."""
    return LOD_TICK if kind == KIND_I8 else 1


@dataclass
class Header:
    version: int
    flags: int
    tag_marker: int = 0
    tag: bytes = b""      # as stored: UTF-8 with its NUL, or UTF-16-LE
    source_hash: int = 0  # FLAG_SOURCE only

    @property
    def lod(self):
        return bool(self.flags & FLAG_SOURCE)

    @property
    def text(self):
        if self.tag_marker == TAG_UTF16:
            return self.tag.decode("utf-16-le")
        return self.tag.rstrip(b"\x00").decode("utf-8", "replace")


@dataclass
class Lead:
    rec1: tuple | None    # FLAG_REC1: scale xyz, quat xyzw, pos xyz
    rec2: tuple | None    # FLAG_REC2
    ref_scale: float | None
    duration: float
    skeleton: bytes | None = None
    slots: int = KIND_SLOTS   # FLAG_KINDS: how many block counts follow


@dataclass
class TrackData:
    lead: Lead
    bones: list                      # list[BoneTrack], in file order
    lod: bool = False


def _key_bytes(b):
    if b.kind == KIND_I8:
        return 4 * len(b.scale_keys) + 5 * len(b.rot_keys) + 4 * len(b.pos_keys)
    return 8 * len(b.scale_keys) + 10 * len(b.rot_keys) + (16 if b.kind == KIND_FLOAT else 8) * len(b.pos_keys)


# --------------------------------------------------------------------------
# Reader and writer
# --------------------------------------------------------------------------

def _name_of(h):
    return NAME_BY_HASH.get(h, f"unk_{h:08x}")


def read_header(data: bytes):
    """-> (Header, offset of the lead)."""
    if data[:4] != _paa.MAGIC or len(data) < 0x14:
        raise ValueError("not a PAR file")
    if data[4] != _paa.TYPE_ANIMATION:
        raise ValueError(f"not an animation (type {data[4]:#x})")
    if data[6:16] != _paa.CONST_BLOCK:
        raise ValueError("unexpected constant block at 0x06")
    flags, marker = struct.unpack_from("<HH", data, 0x10)
    off = 0x14
    tag = b""
    if marker == TAG_UTF8:
        n = struct.unpack_from("<H", data, off)[0]
        tag = bytes(data[off + 2:off + 2 + n])
        off += 2 + n
    elif marker == TAG_UTF16:
        n = struct.unpack_from("<H", data, off)[0]
        tag = bytes(data[off + 2:off + 2 + 2 * n])
        off += 2 + 2 * n
    elif marker != 0:
        raise ValueError(f"tag marker {marker:#x} at 0x12 is not one the add-on reads (flags {flags:#x})")
    src = 0
    if flags & FLAG_SOURCE:
        src = struct.unpack_from("<I", data, off)[0]
        off += 4
    return Header(data[5], flags, marker, tag, src), off


def read_track_data(t: bytes, flags: int, lod: bool = False) -> TrackData:
    """Parse the lead and blocks. `flags` is the header's."""
    n = len(t)
    off = 0
    rec1 = rec2 = ref = skeleton = None
    if flags & FLAG_REC1:
        rec1 = struct.unpack_from("<10f", t, off)
        off += 40
    if flags & FLAG_REC2:
        rec2 = struct.unpack_from("<10f", t, off)
        off += 40
    if flags & FLAG_REF:
        ref = struct.unpack_from("<f", t, off)[0]
        off += 4
    if flags & FLAG_SKELETON:
        k = t[off]
        skeleton = bytes(t[off + 1:off + 1 + k])
        off += 1 + k
    duration = struct.unpack_from("<f", t, off)[0]
    off += 4
    slots = KIND_SLOTS
    if flags & FLAG_KINDS:
        slots = struct.unpack_from("<H", t, off)[0]
        counts = struct.unpack_from(f"<{slots}H", t, off + 2)
        off += 2 + 2 * slots
        kinds = [k for k, m in enumerate(counts) for _ in range(m)]
    else:
        a, b = struct.unpack_from("<HH", t, off)
        off += 4
        kinds = [KIND_HALF] * a + [KIND_FLOAT] * b
    c = struct.unpack_from("<I", t, off)[0]
    off += 4
    odd = sorted(set(kinds) - {KIND_I8, KIND_HALF, KIND_FLOAT})
    if odd:
        raise ValueError(f"blocks of key kind {odd[0]}, which no known clip uses")
    lead = Lead(rec1, rec2, ref, duration, skeleton, slots)

    bones = []
    for i, kind in enumerate(kinds):
        if off + 7 > n:
            raise ValueError(f"block {i}: truncated at {off}")
        h = struct.unpack_from("<I", t, off)[0]
        off += 4
        if kind == KIND_I8:
            sk = []
            for _ in range(t[off]):
                fr, x, y, z = struct.unpack_from("<B3b", t, off + 1 + 4 * len(sk))
                sk.append(PosKey(fr, x / 32.0, y / 32.0, z / 32.0))
            off += 1 + 4 * len(sk)
            rk = []
            for _ in range(t[off]):
                fr, x, y, z, w = struct.unpack_from("<B4b", t, off + 1 + 5 * len(rk))
                rk.append(RotKey(fr, x / 64.0, y / 64.0, z / 64.0, w / 64.0))
            off += 1 + 5 * len(rk)
            pk = []
            for _ in range(t[off]):
                fr, x, y, z = struct.unpack_from("<B3b", t, off + 1 + 4 * len(pk))
                pk.append(PosKey(fr, x / 32.0, y / 32.0, z / 32.0))
            off += 1 + 4 * len(pk)
        else:
            sn = struct.unpack_from("<H", t, off)[0]
            sk = [PosKey(*struct.unpack_from("<H3e", t, off + 2 + 8 * j)) for j in range(sn)]
            off += 2 + 8 * sn
            rn = struct.unpack_from("<H", t, off)[0]
            rk = [RotKey(*struct.unpack_from("<H4e", t, off + 2 + 10 * j)) for j in range(rn)]
            off += 2 + 10 * rn
            pn = struct.unpack_from("<H", t, off)[0]
            off += 2
            pk = []
            if kind == KIND_FLOAT:
                for _ in range(pn):
                    fr, aux, x, y, z = struct.unpack_from("<HH3f", t, off)
                    pk.append(PosKey(fr, x, y, z, aux))
                    off += 16
            else:
                for _ in range(pn):
                    pk.append(PosKey(*struct.unpack_from("<H3e", t, off)))
                    off += 8
        if off > n:
            raise ValueError(f"block {i} runs past the end of the clip")
        bones.append(BoneTrack(_name_of(h), h, rk, pk, kind, sk))

    if off != n:
        raise ValueError(f"{n - off} bytes left after {len(kinds)} blocks")
    got = sum(_key_bytes(b) for b in bones)
    if got != c:
        raise ValueError(f"lead says {c} key bytes, blocks hold {got}")
    return TrackData(lead, bones, lod)


def _q8(v, scale):
    r = int(round(v * scale))
    return max(-128, min(127, r))


def write_track_data(td: TrackData, flags: int) -> bytes:
    ld = td.lead
    for flag, value, what in ((FLAG_REC1, ld.rec1, "first transform"), (FLAG_REC2, ld.rec2, "second transform"),
                              (FLAG_REF, ld.ref_scale, "ref scale"), (FLAG_SKELETON, ld.skeleton, "skeleton path")):
        if bool(flags & flag) != (value is not None):
            raise ValueError(f"flags {flags:#x} and the lead disagree about the {what}")
    kinds = [b.kind for b in td.bones]
    if kinds != sorted(kinds):
        raise ValueError("blocks must be ordered by key kind")
    out = bytearray()
    if ld.rec1 is not None:
        out += struct.pack("<10f", *ld.rec1)
    if ld.rec2 is not None:
        out += struct.pack("<10f", *ld.rec2)
    if ld.ref_scale is not None:
        out += struct.pack("<f", ld.ref_scale)
    if ld.skeleton is not None:
        out += bytes([len(ld.skeleton)]) + ld.skeleton
    out += struct.pack("<f", ld.duration)
    if flags & FLAG_KINDS:
        if kinds and kinds[-1] >= ld.slots:
            raise ValueError(f"key kind {kinds[-1]} does not fit {ld.slots} block counts")
        out += struct.pack(f"<H{ld.slots}H", ld.slots, *(kinds.count(k) for k in range(ld.slots)))
    else:
        if set(kinds) - {KIND_HALF, KIND_FLOAT}:
            raise ValueError("8-bit keys need flag 0x100")
        out += struct.pack("<HH", kinds.count(KIND_HALF), kinds.count(KIND_FLOAT))
    out += struct.pack("<I", sum(_key_bytes(b) for b in td.bones))
    for b in td.bones:
        out += struct.pack("<I", b.name_hash)
        if b.kind == KIND_I8:
            for keys in (b.scale_keys, b.rot_keys, b.pos_keys):
                if len(keys) > 255 or any(not 0 <= k.frame <= 255 for k in keys):
                    raise ValueError(f"{b.name}: an 8-bit block holds at most 255 keys on ticks 0 to 255")
            out.append(len(b.scale_keys))
            for k in b.scale_keys:
                out += struct.pack("<B3b", k.frame, *(_q8(v, 32) for v in (k.x, k.y, k.z)))
            out.append(len(b.rot_keys))
            for k in b.rot_keys:
                out += struct.pack("<B4b", k.frame, *(_q8(v, 64) for v in (k.x, k.y, k.z, k.w)))
            out.append(len(b.pos_keys))
            for k in b.pos_keys:
                out += struct.pack("<B3b", k.frame, *(_q8(v, 32) for v in (k.x, k.y, k.z)))
            continue
        out += struct.pack("<H", len(b.scale_keys))
        for k in b.scale_keys:
            out += struct.pack("<H3e", k.frame, k.x, k.y, k.z)
        out += struct.pack("<H", len(b.rot_keys))
        for k in b.rot_keys:
            out += struct.pack("<H4e", k.frame, k.x, k.y, k.z, k.w)
        out += struct.pack("<H", len(b.pos_keys))
        for k in b.pos_keys:
            if b.kind == KIND_FLOAT:
                out += struct.pack("<HH3f", k.frame, k.aux, k.x, k.y, k.z)
            else:
                out += struct.pack("<H3e", k.frame, k.x, k.y, k.z)
    return bytes(out)


def write_header(hdr: Header) -> bytes:
    out = bytearray(_paa.MAGIC)
    out.append(_paa.TYPE_ANIMATION)
    out.append(hdr.version)
    out += _paa.CONST_BLOCK
    out += struct.pack("<HH", hdr.flags, hdr.tag_marker)
    if hdr.tag_marker == TAG_UTF8:
        out += struct.pack("<H", len(hdr.tag)) + hdr.tag
    elif hdr.tag_marker == TAG_UTF16:
        out += struct.pack("<H", len(hdr.tag) // 2) + hdr.tag
    if hdr.flags & FLAG_SOURCE:
        out += struct.pack("<I", hdr.source_hash)
    return bytes(out)


def is_lod(data: bytes) -> bool:
    return (data[:4] == _paa.MAGIC and data[4] == _paa.TYPE_ANIMATION and len(data) > 0x12
            and bool(struct.unpack_from("<H", data, 0x10)[0] & FLAG_SOURCE))


def decode_file(data: bytes):
    """-> (Header, TrackData) for a full or LOD clip."""
    hdr, off = read_header(data)
    return hdr, read_track_data(data[off:], hdr.flags, hdr.lod)


def encode_file(hdr: Header, td: TrackData) -> bytes:
    return write_header(hdr) + write_track_data(td, hdr.flags)


def lod_source_hash(full_clip_bytes: bytes) -> int:
    """The value a LOD clip carries for its full clip."""
    return hashlittle(full_clip_bytes, HASH_SEED)


def get_bone(td: TrackData, name: str) -> BoneTrack:
    for b in td.bones:
        if b.name == name:
            return b
    raise KeyError(name)


# --------------------------------------------------------------------------
# Making a LOD clip from a full clip
# --------------------------------------------------------------------------
#
# The game's own LOD files follow rules this does reproduce (flags, lead,
# source hash, a fixed bone subset in a fixed order, 8-bit keys on a 1/5
# second tick) and one it does not: which keys it drops. Its keys sit on the
# ticks and look sampled from the full curve (mean error 0.005 to 0.02
# against the full clip sampled at frame 6 * tick). Here a key is dropped when
# linear interpolation between its kept neighbours stays inside a tolerance.

def _lerp_keys(a, b, t, quat):
    va = [getattr(a, c) for c in ("x", "y", "z", "w")[:4 if quat else 3]]
    vb = [getattr(b, c) for c in ("x", "y", "z", "w")[:4 if quat else 3]]
    if quat and sum(x * y for x, y in zip(va, vb)) < 0:
        vb = [-x for x in vb]
    v = [x * (1 - t) + y * t for x, y in zip(va, vb)]
    if quat:
        n = sum(x * x for x in v) ** 0.5 or 1.0
        v = [x / n for x in v]
    return v


def _sample(keys, frame, quat):
    if frame <= keys[0].frame:
        k = keys[0]
        return [getattr(k, c) for c in ("x", "y", "z", "w")[:4 if quat else 3]]
    if frame >= keys[-1].frame:
        k = keys[-1]
        return [getattr(k, c) for c in ("x", "y", "z", "w")[:4 if quat else 3]]
    for a, b in zip(keys, keys[1:]):
        if a.frame <= frame <= b.frame:
            return _lerp_keys(a, b, (frame - a.frame) / (b.frame - a.frame), quat)


def _thin(frames, vals, tol):
    """Indices to keep: ends, plus any key the straight line between kept
    neighbours misses by more than tol (Ramer-Douglas-Peucker on the values)."""
    keep = {0, len(frames) - 1}

    def rec(a, b):
        if b <= a + 1:
            return
        worst, wi = -1.0, None
        for i in range(a + 1, b):
            t = (frames[i] - frames[a]) / (frames[b] - frames[a])
            e = max(abs(vals[i][c] - (vals[a][c] * (1 - t) + vals[b][c] * t)) for c in range(len(vals[i])))
            if e > worst:
                worst, wi = e, i
        if worst > tol:
            keep.add(wi)
            rec(a, wi)
            rec(wi, b)

    rec(0, len(frames) - 1)
    return sorted(keep)


#: Kliff's LOD bone list, in the order every one of his 11 LOD clips uses.
#: A clip takes the bones of this list that it animates: 30 always, plus
#: Bip_Weapon_Attach_In_02 and B_WeaponIn_R_00 when the full clip has them.
KLIFF_LOD_SECTION1 = [
    "Bip_Weapon_C", "Bip01 R UpperArm", "Bip_Weapon_Attach_In_02", "Bip01 R Hand",
    "B_EnemyCatch_00", "Bip01 Pelvis", "Bip01 R Forearm", "B_CatchMe_00", "Bip01 L Hand",
    "Bip01 L Forearm", "Bip01 R Calf", "B_WeaponIn_L_00", "B_WeaponIn_R_00",
    "Bip01 L UpperArm", "Bip01 Head", "Bip01 L Calf", "Bip_Weapon_R", "Bip01 L Clavicle",
    "Bip01 R Thigh", "Bip_Weapon_B", "Bip_Weapon_L", "Bip01 Spine", "Bip01 L Thigh",
    "Bip01 Spine2", "Bip01 Neck", "Bip01 Spine1", "Bip01 R Foot", "Bip01 R Clavicle",
    "Bip01 L Foot", "Bip01 L Toe0", "Bip01 R Toe0", "Bip_Shield_L",
]
KLIFF_LOD_SECTION2 = ["B_MoveControl_01", "B_TL_Position_02", "B_TL_Position_04",
                      "B_TL_Position_03", "B_TL_Position_01", "Bip01"]


def make_lod(full_bytes: bytes, template_lod_bytes: bytes | None = None, rot_tol=0.02,
             pos_tol=0.03, half_rot_tol=0.003, half_pos_tol=0.01) -> bytes:
    """Build a _lod.paa for a full clip. Without a template the bone list and
    order are Kliff's (KLIFF_LOD_SECTION1/2); with one, any LOD clip of a rig
    gives the bones and their order. 8-bit position and scale keys clamp at
    +-3.97 (1/32 steps)."""
    fhdr, ftd = decode_file(full_bytes)
    if fhdr.lod:
        raise ValueError("the clip to make a LOD for is a LOD clip itself")
    if template_lod_bytes is not None:
        thdr, ttd = decode_file(template_lod_bytes)
        if not thdr.lod:
            raise ValueError("template is not a LOD clip")
        order = [(b.name, b.kind) for b in ttd.bones]
    else:
        order = [(n, KIND_I8) for n in KLIFF_LOD_SECTION1] + [(n, KIND_HALF) for n in KLIFF_LOD_SECTION2]
    fb = {b.name: b for b in ftd.bones}
    out = []
    for name, kind in order:
        f = fb.get(name)
        if f is None or f.kind != kind + 1:
            continue
        lists = ((f.scale_keys, False), (f.rot_keys, True), (f.pos_keys, False))
        new = []
        if kind == KIND_I8:
            for keys, quat in lists:
                dst = []
                if keys:
                    last = keys[-1].frame
                    ticks = [0] if len(keys) == 1 else list(range(0, int(round(last / 6.0)) + 1))
                    vals = [_sample(keys, min(6 * k, last), quat) for k in ticks]
                    for i in _thin(ticks, vals, rot_tol if quat else pos_tol):
                        dst.append(RotKey(ticks[i], *vals[i]) if quat else PosKey(ticks[i], *vals[i]))
                new.append(dst)
        else:
            for keys, quat in lists:
                dst = []
                if keys:
                    frames = [k.frame for k in keys]
                    vals = [[getattr(k, c) for c in ("x", "y", "z", "w")[:4 if quat else 3]] for k in keys]
                    for i in _thin(frames, vals, half_rot_tol if quat else half_pos_tol):
                        k = keys[i]
                        dst.append(RotKey(k.frame, k.x, k.y, k.z, k.w) if quat else PosKey(k.frame, k.x, k.y, k.z))
                new.append(dst)
        out.append(BoneTrack(f.name, f.name_hash, new[1], new[2], kind, new[0]))
    ld = ftd.lead
    lead = Lead(ld.rec1, ld.rec2, ld.ref_scale, ld.duration, ld.skeleton, KIND_SLOTS)
    hdr = Header(fhdr.version, fhdr.flags | LOD_FLAGS, 0, b"", lod_source_hash(full_bytes))
    return encode_file(hdr, TrackData(lead, out, True))


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_track_data(td: TrackData, frame_limit: int | None = None):
    """Sanity problems in a decoded clip, as a list of strings (empty is
    good): strictly rising frames, frames inside the clip, unit quaternions.
    8-bit blocks count 1/5 second ticks, everything else 30 fps frames."""
    problems = []
    frames30 = frame_limit if frame_limit is not None else int(round(td.lead.duration * 30)) + 1
    ticks5 = int(round(td.lead.duration * 5)) + 1
    for b in td.bones:
        lim = ticks5 if b.kind == KIND_I8 else frames30
        for label, keys in (("scale", b.scale_keys), ("rot", b.rot_keys), ("pos", b.pos_keys)):
            fr = [k.frame for k in keys]
            if any(f2 <= f1 for f1, f2 in zip(fr, fr[1:])):
                problems.append(f"{b.name}: {label} frames not strictly rising")
            if fr and fr[-1] > lim:
                problems.append(f"{b.name}: {label} frame {fr[-1]} past clip end {lim}")
        tol = 0.05 if b.kind == KIND_I8 else 0.005
        for k in b.rot_keys:
            n2 = k.x * k.x + k.y * k.y + k.z * k.z + k.w * k.w
            if abs(n2 - 1.0) > tol:
                problems.append(f"{b.name}: frame {k.frame} quaternion norm^2 {n2:.4f}")
                break
    return problems


def roundtrip_check(paths):
    """[(path, ok, len_in, len_out, n_bones)] for each clip."""
    results = []
    for path in paths:
        data = open(path, "rb").read()
        hdr, td = decode_file(data)
        back = encode_file(hdr, td)
        results.append((path, back == data, len(data), len(back), len(td.bones)))
    return results
