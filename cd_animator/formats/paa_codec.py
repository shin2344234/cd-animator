"""Per-bone keyframe codec for Crimson Desert .paa animation clips (build 2.03.02).

Decodes and re-encodes the track payload of both kinds of .paa clip:

  * full clips   (character/motion/..., header with a tag string), and
  * LOD clips    (character/motion/motion_lod__/..., the "_lod.paa" files,
                  a reduced copy with 8-bit keys),

for both rigs checked so far: the 9-bone flying-broom rig and Kliff's 447-bone
biped (phm_01.pab). Every file this module has been run against round-trips
byte for byte from decoded keys (see roundtrip_check() and
roundtrip_rider.py). rider_and_metabin.md has the evidence and the confidence
for every claim below.

Layout of a full clip (all integers little-endian)

    0x00  "PAR ", u8 2 (animation), u8 3 (version), 10 bytes 00..09
    0x10  u16 15, u16 0xC000, u16 tag_len, tag (UTF-8, NUL terminated)
          tag is "<korean for male>;<korean for broom>;" on every riding clip
    ....  3 x f32 scale (1, 1, 1)
    then the track data (paa.Animation.track_data):

      LEAD   84 bytes
        10 x f32   record A: quat xyzw, position xyz, scale xyz
        7  x f32   record B: quat xyzw, position xyz
        f32        ref_scale  (0.9723 on Kliff's clips, 0.0 on the broom's)
        f32        duration in seconds (same number the metabin ends with)
        u16 a      number of blocks in section 1 ("compact" bones)
        u16 b      number of blocks in section 2 ("full" bones)
        u32 c      total key bytes of all blocks (headers and hashes excluded)

      then a + b BLOCKS, section 1 first. One block per animated bone, in a
      fixed skeleton-derived order that is the same in every clip of a rig.
      Bones without keys are absent (their bind pose applies):

        u32  hashlittle(bone_name, 0xC5EDE)
        u16  flags            0 in every sample
        u16  rot_count
        rot_count x  { u16 frame, 4 x binary16 x y z w }          10 bytes
        u16  pos_count
        section 1:  pos_count x { u16 frame, 3 x binary16 x y z }  8 bytes
        section 2:  pos_count x { u16 frame, u16 aux, 3 x f32 }   16 bytes

      aux is uninitialised padding: it equals the same stale half float in
      every key of a track, and in every block of section 2 of a clip. It is
      kept per key so the round trip is exact; write 0 for new keys.

Layout of a LOD clip

    0x10  u16 415, u16 0, u32 source_hash = hashlittle(<the full clip's bytes>,
          0xC5EDE), 3 x f32 scale, then the same LEAD but with 16 tail bytes:
          ... duration, u32 5, u16 a, u16 b, u32 0, u32 c
    Section 1 blocks use 8-bit keys and u8 counts and frames:
        u32 hash, u8 flags, u8 rot_count,
        rot_count x { u8 frame, 4 x i8 }   (value = i8 / 64)
        u8 pos_count, pos_count x { u8 frame, 3 x i8 } (value = i8 / 32)
    Section 2 blocks use the full clip's section 1 shape (half floats, u16s).
    LOD frame numbers count 1/5 second ticks: round(full_frame / 6).

Frame numbers in a full clip are absolute frames at 30 fps (the highest one
is duration x 30).

Everything the old version of this module exposed still works for the broom:
read_track_data, write_track_data, decode_file, encode_file, get_bone,
roundtrip_check, hash_names, NAME_BY_HASH, HASH_BY_NAME, BONE_NAMES,
RotKey, PosKey, BoneTrack, TrackData. TrackData.lead_block is now a property
over the structured Lead.
"""

from __future__ import annotations

import os
import struct
import sys
from dataclasses import dataclass, field as dc_field

from . import paa as _paa

from .hashlittle import hashlittle

HASH_SEED = 0xC5EDE

#: Section 2 ("full") bones on the broom rig, kept for old callers. The real
#: rule is positional: the last `b` blocks of the clip are section 2.
FULL_POS_BONES = {"Bip01", "B_MoveControl_01"}

BONE_NAMES = [
    "Bip01", "B_TL_Position_02", "B_TL_Position_01", "B_MoveControl_01",
    "B_Body_00", "B_EnemyCatch_00", "B_CatchMe_00", "B_Rider_01", "B_Rider_02",
]

LOD_MARKER = 415
LOD_TAIL_CONST = 5
FLAG_SKELETON = 0x40    # header flag: the lead names the skeleton file


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
    frame: int
    x: float
    y: float
    z: float
    aux: int = 0          # section-2 float keys only: the padding u16


# key formats of a block
ROT_HALF, ROT_I8 = "half", "i8"
POS_HALF, POS_F32, POS_I8 = "half", "f32", "i8"


@dataclass
class BoneTrack:
    name: str             # resolved bone name, or "unk_XXXXXXXX"
    name_hash: int
    header_zero: int      # the block's flags field (u16, or u8 in LOD section 1); 0 in every sample
    rot_keys: list
    pos_keys: list
    pos_is_full: bool     # section 2 of a full clip: 16-byte float keys
    pos_track_const: int = 0   # aux of the first position key (old API)
    section: int = 1      # 1 or 2
    rot_fmt: str = ROT_HALF
    pos_fmt: str = POS_HALF

    @property
    def pos_count_hint(self):   # old API: the position count
        return len(self.pos_keys)


@dataclass
class Lead:
    rec_a: tuple          # 10 floats: quat xyzw, pos xyz, scale xyz
    rec_b: tuple          # 7 floats: quat xyzw, pos xyz
    ref_scale: float
    duration: float
    lod_const: int = LOD_TAIL_CONST   # LOD only: u32 after the duration (5)
    lod_zero: int = 0                 # LOD only: u32 before c (0)
    # Full clips whose header flags (the u16 at 0x10) have FLAG_SKELETON set
    # store the skeleton's path between ref_scale and the duration, as a u8
    # length and that many bytes ("character/model/1_pc/1_phm/phm_01.pab" on
    # Kliff's camel and iguana clips). None when absent.
    skeleton: bytes | None = None

    def pack(self, a, b, c, lod):
        out = struct.pack("<17f", *self.rec_a, *self.rec_b) + struct.pack("<f", self.ref_scale)
        if self.skeleton is not None:
            out += bytes([len(self.skeleton)]) + self.skeleton
        out += struct.pack("<f", self.duration)
        if lod:
            out += struct.pack("<IHHII", self.lod_const, a, b, self.lod_zero, c)
        else:
            out += struct.pack("<HHI", a, b, c)
        return out


@dataclass
class TrackData:
    lead: Lead
    bones: list                      # list[BoneTrack], in file order
    lod: bool = False

    @property
    def lead_block(self) -> bytes:   # old API: the verbatim lead bytes
        a = sum(1 for b in self.bones if b.section == 1)
        c = _key_bytes(self.bones, self.lod)
        return self.lead.pack(a, len(self.bones) - a, c, self.lod)


def _key_bytes(bones, lod):
    n = 0
    for b in bones:
        if lod and b.section == 1:
            n += 5 * len(b.rot_keys) + 4 * len(b.pos_keys)
        else:
            n += 10 * len(b.rot_keys) + (16 if b.pos_fmt == POS_F32 else 8) * len(b.pos_keys)
    return n


LEAD_SIZE = 84          # full clips
LOD_LEAD_SIZE = 92


# --------------------------------------------------------------------------
# Track data reader / writer
# --------------------------------------------------------------------------

def _name_of(h):
    return NAME_BY_HASH.get(h, f"unk_{h:08x}")


def read_track_data(t: bytes, lod: bool = False, flags: int = 0) -> TrackData:
    """Parse the track data region. `lod` selects the LOD clip layout;
    `flags` is the header u16 at 0x10, a full clip's flags or a LOD's
    marker; FLAG_SKELETON means the same in both."""
    n = len(t)
    rec = struct.unpack_from("<17f", t, 0)
    ref_scale = struct.unpack_from("<f", t, 68)[0]
    skeleton = None
    extra = 0
    if flags & FLAG_SKELETON:
        k = t[72]
        skeleton = bytes(t[73:73 + k])
        extra = 1 + k
    duration = struct.unpack_from("<f", t, 72 + extra)[0]
    if lod:
        lod_const, a, b, lod_zero, c = struct.unpack_from("<IHHII", t, 76 + extra)
        off = LOD_LEAD_SIZE + extra
    else:
        lod_const, lod_zero = LOD_TAIL_CONST, 0
        a, b, c = struct.unpack_from("<HHI", t, 76 + extra)
        off = LEAD_SIZE + extra
    lead = Lead(rec[:10], rec[10:17], ref_scale, duration, lod_const, lod_zero, skeleton)

    bones = []
    key_bytes = 0
    for i in range(a + b):
        sec = 1 if i < a else 2
        if off + 4 > n:
            raise ValueError(f"block {i}: truncated at {off}")
        h = struct.unpack_from("<I", t, off)[0]
        off += 4
        small = lod and sec == 1
        if small:
            flags, rn = t[off], t[off + 1]
            off += 2
            rk = []
            for _ in range(rn):
                fr = t[off]
                q = struct.unpack_from("<4b", t, off + 1)
                rk.append(RotKey(fr, *(v / 64.0 for v in q)))
                off += 5
            pn = t[off]
            off += 1
            pk = []
            for _ in range(pn):
                fr = t[off]
                p = struct.unpack_from("<3b", t, off + 1)
                pk.append(PosKey(fr, *(v / 32.0 for v in p)))
                off += 4
            key_bytes += 5 * rn + 4 * pn
            rf, pf = ROT_I8, POS_I8
        else:
            flags, rn = struct.unpack_from("<HH", t, off)
            off += 4
            rk = []
            for _ in range(rn):
                fr = struct.unpack_from("<H", t, off)[0]
                q = struct.unpack_from("<4e", t, off + 2)
                rk.append(RotKey(fr, *q))
                off += 10
            pn = struct.unpack_from("<H", t, off)[0]
            off += 2
            pk = []
            full = (sec == 2 and not lod)
            for _ in range(pn):
                if full:
                    fr, aux = struct.unpack_from("<HH", t, off)
                    p = struct.unpack_from("<3f", t, off + 4)
                    pk.append(PosKey(fr, *p, aux=aux))
                    off += 16
                else:
                    fr = struct.unpack_from("<H", t, off)[0]
                    p = struct.unpack_from("<3e", t, off + 2)
                    pk.append(PosKey(fr, *p))
                    off += 8
            key_bytes += 10 * rn + (16 if full else 8) * pn
            rf, pf = ROT_HALF, (POS_F32 if full else POS_HALF)
        const = pk[0].aux if pk and pf == POS_F32 else 0
        bones.append(BoneTrack(_name_of(h), h, flags, rk, pk, pf == POS_F32, const, sec, rf, pf))

    if off != n:
        raise ValueError(f"{n - off} bytes left after {a + b} blocks")
    if key_bytes != c:
        raise ValueError(f"lead says {c} key bytes, blocks hold {key_bytes}")
    return TrackData(lead, bones, lod)


def _q8(v, scale):
    r = int(round(v * scale))
    return max(-128, min(127, r))


def write_track_data(td: TrackData) -> bytes:
    lod = td.lod
    a = sum(1 for b in td.bones if b.section == 1)
    # section 1 must come first
    if any(b.section == 1 for b in td.bones[a:]):
        raise ValueError("section 1 blocks must precede section 2 blocks")
    out = bytearray(td.lead.pack(a, len(td.bones) - a, _key_bytes(td.bones, lod), lod))
    for b in td.bones:
        out += struct.pack("<I", b.name_hash)
        small = lod and b.section == 1
        if small:
            out += struct.pack("<BB", b.header_zero, len(b.rot_keys))
            for k in b.rot_keys:
                out += struct.pack("<B4b", k.frame, *(_q8(v, 64) for v in (k.x, k.y, k.z, k.w)))
            out += struct.pack("<B", len(b.pos_keys))
            for k in b.pos_keys:
                out += struct.pack("<B3b", k.frame, *(_q8(v, 32) for v in (k.x, k.y, k.z)))
        else:
            out += struct.pack("<HH", b.header_zero, len(b.rot_keys))
            for k in b.rot_keys:
                out += struct.pack("<H4e", k.frame, k.x, k.y, k.z, k.w)
            out += struct.pack("<H", len(b.pos_keys))
            for k in b.pos_keys:
                if b.pos_fmt == POS_F32:
                    out += struct.pack("<HH3f", k.frame, k.aux, k.x, k.y, k.z)
                else:
                    out += struct.pack("<H3e", k.frame, k.x, k.y, k.z)
    return bytes(out)


# --------------------------------------------------------------------------
# Whole-file wrappers
# --------------------------------------------------------------------------

@dataclass
class LodHeader:
    """Container fields of a _lod.paa (paa.read_paa rejects these files)."""
    version: int
    marker: int           # u16 at 0x10: 415 (0x19F), or 0x1DF with FLAG_SKELETON
                          # on clips whose lead names the skeleton
    zero: int             # u16 at 0x12
    source_hash: int      # u32 at 0x14: hashlittle(full clip bytes, 0xC5EDE)
    scale: tuple


def is_lod(data: bytes) -> bool:
    return (data[:4] == _paa.MAGIC and data[4] == _paa.TYPE_ANIMATION
            and struct.unpack_from("<H", data, 0x10)[0] & ~FLAG_SKELETON == LOD_MARKER)


def decode_file(data: bytes):
    """-> (container, TrackData). Container is a paa.Animation for a full
    clip, a LodHeader for a LOD clip."""
    if is_lod(data):
        if data[6:16] != _paa.CONST_BLOCK:
            raise ValueError("unexpected constant block at 0x06")
        marker, zero, src = struct.unpack_from("<HHI", data, 0x10)
        scale = struct.unpack_from("<3f", data, 0x18)
        hdr = LodHeader(data[5], marker, zero, src, scale)
        return hdr, read_track_data(data[0x24:], lod=True, flags=marker)
    anim = _paa.read_paa(data)
    return anim, read_track_data(anim.track_data, flags=anim.count_u16)


def encode_file(container, td: TrackData) -> bytes:
    if isinstance(container, LodHeader):
        out = bytearray(_paa.MAGIC)
        out.append(_paa.TYPE_ANIMATION)
        out.append(container.version)
        out += _paa.CONST_BLOCK
        out += struct.pack("<HHI", container.marker, container.zero, container.source_hash)
        out += struct.pack("<3f", *container.scale)
        out += write_track_data(td)
        return bytes(out)
    container.track_data = write_track_data(td)
    return _paa.write_paa(container)


def lod_source_hash(full_clip_bytes: bytes) -> int:
    """The value a LOD clip carries at 0x14 for its full clip."""
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
# The game's own LOD files follow rules this does reproduce (container, lead,
# source hash, a fixed bone subset in a fixed order, section 1 on a 1/5 second
# tick with 8-bit keys) and one it does not: which keys it drops. Its keys sit
# on the ticks and look sampled from the full curve (mean error 0.005 to 0.02
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
    gives the bones and their order. Section 1 position keys clamp at +-3.97
    (8-bit keys in 1/32 m steps)."""
    fcont, ftd = decode_file(full_bytes)
    if template_lod_bytes is not None:
        tcont, ttd = decode_file(template_lod_bytes)
        if not isinstance(tcont, LodHeader):
            raise ValueError("template is not a LOD clip")
        order = [(b.name, b.section) for b in ttd.bones]
    else:
        order = [(n, 1) for n in KLIFF_LOD_SECTION1] + [(n, 2) for n in KLIFF_LOD_SECTION2]
    fb = {b.name: b for b in ftd.bones}
    out = []
    for name, section in order:
        f = fb.get(name)
        if f is None or f.section != section:
            continue
        t = f
        rot, pos = [], []
        if t.section == 1:
            for keys, dst, quat, tol in ((f.rot_keys, rot, True, rot_tol), (f.pos_keys, pos, False, pos_tol)):
                if not keys:
                    continue
                last = keys[-1].frame
                ticks = list(range(0, int(round(last / 6.0)) + 1))
                if len(keys) == 1:
                    ticks = [0]
                vals = [_sample(keys, min(6 * k, last), quat) for k in ticks]
                for i in _thin(ticks, vals, tol):
                    v = vals[i]
                    dst.append(RotKey(ticks[i], *v) if quat else PosKey(ticks[i], *v))
            bt = BoneTrack(f.name, f.name_hash, 0, rot, pos, False, 0, 1, ROT_I8, POS_I8)
        else:
            for keys, dst, quat, tol in ((f.rot_keys, rot, True, half_rot_tol), (f.pos_keys, pos, False, half_pos_tol)):
                if not keys:
                    continue
                frames = [k.frame for k in keys]
                vals = [[getattr(k, c) for c in ("x", "y", "z", "w")[:4 if quat else 3]] for k in keys]
                for i in _thin(frames, vals, tol):
                    k = keys[i]
                    dst.append(RotKey(k.frame, k.x, k.y, k.z, k.w) if quat else PosKey(k.frame, k.x, k.y, k.z))
            bt = BoneTrack(f.name, f.name_hash, 0, rot, pos, False, 0, 2, ROT_HALF, POS_HALF)
        out.append(bt)
    ld = ftd.lead
    lead = Lead(ld.rec_a, ld.rec_b, ld.ref_scale, ld.duration, LOD_TAIL_CONST, 0, ld.skeleton)
    marker = LOD_MARKER | (FLAG_SKELETON if ld.skeleton is not None else 0)
    hdr = LodHeader(3, marker, 0, lod_source_hash(full_bytes), (1.0, 1.0, 1.0))
    return encode_file(hdr, TrackData(lead, out, True))


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_track_data(td: TrackData, frame_limit: int | None = None):
    """Sanity problems in a decoded clip, as a list of strings (empty is
    good): strictly rising frames, frames inside the clip, unit quaternions.
    A LOD clip's section 1 counts 1/5 second ticks, everything else counts
    30 fps frames."""
    problems = []
    frames30 = frame_limit if frame_limit is not None else int(round(td.lead.duration * 30)) + 1
    ticks5 = int(round(td.lead.duration * 5)) + 1
    for b in td.bones:
        small = td.lod and b.section == 1
        lim = ticks5 if small else frames30
        for label, keys in (("rot", b.rot_keys), ("pos", b.pos_keys)):
            fr = [k.frame for k in keys]
            if any(f2 <= f1 for f1, f2 in zip(fr, fr[1:])):
                problems.append(f"{b.name}: {label} frames not strictly rising")
            if fr and fr[-1] > lim:
                problems.append(f"{b.name}: {label} frame {fr[-1]} past clip end {lim}")
        tol = 0.05 if b.rot_fmt == ROT_I8 else 0.005
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
        cont, td = decode_file(data)
        back = encode_file(cont, td)
        results.append((path, back == data, len(data), len(back), len(td.bones)))
    return results


if __name__ == "__main__":
    import glob

    S = r"C:\scratchpad"
    FULL = S + r"\extracted\0009\character\motion\4_riding\cd_r0032_00_broom"
    LODD = S + r"\extracted\0009\character\motion\motion_lod__\4_riding\cd_r0032_00_broom"
    paths = sorted(glob.glob(os.path.join(FULL, "*.paa"))) + sorted(glob.glob(os.path.join(LODD, "*.paa")))
    ok_count = 0
    for path, ok, dlen, blen, nbones in roundtrip_check(paths):
        status = "OK" if ok else "MISMATCH"
        ok_count += ok
        print(f"{status:8s} {os.path.basename(path):65s} {dlen:5d}B  bones={nbones}")
    print(f"{ok_count}/{len(paths)} round-tripped byte-exact")
