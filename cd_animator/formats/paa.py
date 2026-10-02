"""Reader/writer for Crimson Desert's "PAR " character formats: .pab
skeletons and .paa animation clips (pack group 0009, e.g.
character/model/4_riding/cd_r0032_00_broom/cd_r0032_00_broom.pab and
character/motion/4_riding/cd_r0032_00_broom/cd_rd_broom_basic_00_00_*.paa).

Both are decrypted, decompressed file BYTES (as crimson_rs.extract_file
already returns them) -- this module does not touch PAZ/PAMT packing.

Confidence, so a caller can tell what is load-bearing:

  .pab skeleton (bones, hierarchy, bind pose)        -- HIGH. Validated:
      every bone record parses to an exact end-of-file with no leftover
      bytes, every quaternion is unit-norm, and the 9 decoded bones and
      parent links match the names CONTEXT.md recorded by hand.

  .paa container (magic/type/version/tag string/scale, track region
      boundaries, per-key TIME field)                -- HIGH for the
      container, MEDIUM for "count"/"unk" (their role is not pinned
      down, only their byte position and that they round-trip).

  .paa per-key rotation/position VALUE encoding       -- NOT SOLVED.
      See animation.md ("Track payload: what was and wasn't cracked").
      This module keeps that region as an opaque byte blob, which is
      why round-tripping is byte-exact despite the gap: unread bytes are
      never re-derived, only carried.

Round trip: read(data) then write(obj) reproduces `data` byte-for-byte
for every file this module has been run against (the 11 broom clips and
the broom .pab) -- see roundtrip_check() at the bottom.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field


MAGIC = b"PAR "

TYPE_SKELETON = 0x01
TYPE_ANIMATION = 0x02

# The 10-byte constant seen at 0x06 in both .pab and .paa headers in this
# build. Never observed to differ; kept verbatim rather than assumed.
CONST_BLOCK = bytes(range(10))


# --------------------------------------------------------------------------
# .pab skeleton
# --------------------------------------------------------------------------

@dataclass
class Bone:
    name: str                 # decoded CP949 -> str; ASCII in every sample seen
    parent: int                # index into Skeleton.bones, -1 for a root
    scale: tuple                # (x, y, z) float32
    quat: tuple                 # (x, y, z, w) float32
    trans: tuple                 # (x, y, z) float32
    flags: bytes               # 2 raw bytes, meaning not decoded
    matrices: bytes = b""        # raw bytes of the 4 bind/inverse-bind matrices
                                 # (offset 0x004..0x104 of the payload). Redundant
                                 # with scale/quat/trans for reading a pose (per
                                 # kukdh1's PabSkeleton.h), so not decoded here --
                                 # kept verbatim so write_pab is byte-exact.
    extra: bytes = b""          # raw bytes of an optional trailing block
                                 # (none observed on the broom rig; kept for
                                 # round-trip safety on a skeleton that has one)


@dataclass
class Skeleton:
    version: int
    unk_u16: int          # header @0x10; NOT the bone count on this build (see below)
    first_id_a: int        # header @0x12, u32, role unknown
    first_id_b: int        # header @0x16, u32, role unknown
    bones: list


# The BDO-family decoders (kukdh1/PAZ-Unpacker's PabSkeleton.cpp) read a
# 22-byte header (0x16) and one 4-byte "bone id" ahead of every record.
# This build's header is 26 bytes (0x1A) -- 4 bytes longer -- and no such
# id gap was found between records: bone N's record runs straight into
# bone N+1's name-length byte, with only the flag-dependent optional block
# (if any) in between. Bone identity is therefore just its position in the
# file; nothing analogous to the BDO "uiBoneId" was found on this rig.
_PAB_HEADER_SIZE = 0x1A
_PAB_PAYLOAD_SIZE = 302  # parent(4) + 4 matrices(4*16*4=256) + scale(12) + quat(16) + trans(12) + flags(2) = 302
_OFF_PARENT = 0x000
_OFF_SCALE = 0x104
_OFF_QUAT = 0x110
_OFF_TRANS = 0x120
_OFF_FLAGS = 0x12C
# Gap (in bytes) between the end of a bone's 302-byte payload and the next
# record's name-length byte. 2 is "no optional block" (this build has no
# separate per-bone id, unlike kukdh1's BDO decoder, so the bare minimum gap
# is 2 rather than BDO's 4); the rest are kukdh1's known block sizes + 2.
_SEPARATORS = (2, 26, 38, 58, 62)


def read_pab(data: bytes) -> Skeleton:
    if data[:4] != MAGIC:
        raise ValueError("not a PAR file")
    if data[4] != TYPE_SKELETON:
        raise ValueError(f"not a skeleton (type={data[4]:#x})")
    version = data[5]
    if data[6:16] != CONST_BLOCK:
        raise ValueError("unexpected constant block at 0x06 -- different build?")

    unk_u16 = struct.unpack_from("<H", data, 0x10)[0]
    first_id_a = struct.unpack_from("<I", data, 0x12)[0]
    first_id_b = struct.unpack_from("<I", data, 0x16)[0]

    bones = []
    off = _PAB_HEADER_SIZE
    i = 0
    while True:
        name_len = data[off]
        name = data[off + 1: off + 1 + name_len].decode("cp949")
        payload = off + 1 + name_len
        parent = struct.unpack_from("<i", data, payload + _OFF_PARENT)[0]
        matrices = data[payload + 0x004: payload + _OFF_SCALE]
        scale = struct.unpack_from("<3f", data, payload + _OFF_SCALE)
        quat = struct.unpack_from("<4f", data, payload + _OFF_QUAT)
        trans = struct.unpack_from("<3f", data, payload + _OFF_TRANS)
        flags = data[payload + _OFF_FLAGS: payload + _OFF_FLAGS + 2]

        q2 = sum(c * c for c in quat)
        if not (0.9 <= q2 <= 1.1):
            raise ValueError(f"bone {i} ({name}) quaternion is not unit-norm ({q2}); offsets have drifted")
        if not (-1 <= parent < i):
            raise ValueError(f"bone {i} ({name}) parent {parent} is not a preceding bone")

        rec_end = payload + _PAB_PAYLOAD_SIZE

        if rec_end == len(data):
            bones.append(Bone(name, parent, scale, quat, trans, flags, matrices, b""))
            off = len(data)
            break

        chosen = None
        for sep in _SEPARATORS:
            cand = rec_end + sep
            if cand >= len(data):
                continue
            nlen = data[cand]
            if not (0 < nlen <= 64 and cand + 1 + nlen + 4 <= len(data)):
                continue
            parent_probe = struct.unpack_from("<i", data, cand + 1 + nlen)[0]
            if -1 <= parent_probe <= i + 1:
                chosen = sep
                break

        if chosen is None:
            # No further plausible record: this bone is last and whatever
            # remains (if anything) is its own trailing block.
            bones.append(Bone(name, parent, scale, quat, trans, flags, matrices, data[rec_end:]))
            off = len(data)
            break

        bones.append(Bone(name, parent, scale, quat, trans, flags, matrices, data[rec_end:rec_end + chosen]))
        off = rec_end + chosen
        i += 1

    return Skeleton(version, unk_u16, first_id_a, first_id_b, bones)


def write_pab(sk: Skeleton) -> bytes:
    out = bytearray()
    out += MAGIC
    out.append(TYPE_SKELETON)
    out.append(sk.version)
    out += CONST_BLOCK
    out += struct.pack("<H", sk.unk_u16)
    out += struct.pack("<I", sk.first_id_a)
    out += struct.pack("<I", sk.first_id_b)
    assert len(out) == _PAB_HEADER_SIZE

    for b in sk.bones:
        name_bytes = b.name.encode("cp949")
        out.append(len(name_bytes))
        out += name_bytes
        payload = bytearray(_PAB_PAYLOAD_SIZE)
        struct.pack_into("<i", payload, _OFF_PARENT, b.parent)
        payload[0x004:_OFF_SCALE] = b.matrices
        struct.pack_into("<3f", payload, _OFF_SCALE, *b.scale)
        struct.pack_into("<4f", payload, _OFF_QUAT, *b.quat)
        struct.pack_into("<3f", payload, _OFF_TRANS, *b.trans)
        payload[_OFF_FLAGS:_OFF_FLAGS + 2] = b.flags
        out += payload
        out += b.extra

    return bytes(out)


# --------------------------------------------------------------------------
# .paa animation clip
# --------------------------------------------------------------------------

@dataclass
class Animation:
    version: int
    count_u16: int     # header @0x10. Constant 15 across all 11 broom clips
                        # and equal to a field inside the sibling .paa_metabin,
                        # so it is schema/track-slot metadata, not a per-clip
                        # keyframe or bone count (the skeleton has 9 bones).
    unk_u16: int        # header @0x12. Constant 0xc000 across all 11 clips.
    tag: str            # header string, e.g. "남자;빗자루;"
                        # ("male;broom;"). NUL-terminated in the file.
    scale: tuple         # 3 float32 right after the tag; always (1,1,1) here
    track_data: bytes    # opaque: per-bone keyframe region, NOT decoded (see
                          # module docstring and animation.md)


def read_paa(data: bytes) -> Animation:
    if data[:4] != MAGIC:
        raise ValueError("not a PAR file")
    if data[4] != TYPE_ANIMATION:
        raise ValueError(f"not an animation (type={data[4]:#x})")
    version = data[5]
    if data[6:16] != CONST_BLOCK:
        raise ValueError("unexpected constant block at 0x06 -- different build?")

    count_u16 = struct.unpack_from("<H", data, 0x10)[0]
    unk_u16 = struct.unpack_from("<H", data, 0x12)[0]
    str_len = struct.unpack_from("<H", data, 0x14)[0]
    tag_bytes = data[0x16:0x16 + str_len]
    if tag_bytes[-1:] != b"\x00":
        raise ValueError("tag string is not NUL-terminated where expected")
    tag = tag_bytes[:-1].decode("utf-8")

    after_str = 0x16 + str_len
    scale = struct.unpack_from("<3f", data, after_str)
    track_start = after_str + 12

    return Animation(version, count_u16, unk_u16, tag, scale, data[track_start:])


def write_paa(anim: Animation) -> bytes:
    tag_bytes = anim.tag.encode("utf-8") + b"\x00"
    out = bytearray()
    out += MAGIC
    out.append(TYPE_ANIMATION)
    out.append(anim.version)
    out += CONST_BLOCK
    out += struct.pack("<H", anim.count_u16)
    out += struct.pack("<H", anim.unk_u16)
    out += struct.pack("<H", len(tag_bytes))
    out += tag_bytes
    out += struct.pack("<3f", *anim.scale)
    out += anim.track_data
    return bytes(out)


# --------------------------------------------------------------------------
# Keyframe-time scan (informational only -- does not feed write_paa)
# --------------------------------------------------------------------------

def scan_key_times(track_data: bytes):
    """Find the 10-byte-stride "0x3c marker + u16 time" pattern documented
    in animation.md. Returns a list of (byte_offset, time_value) pairs.

    This is diagnostic, not a full track parse: it does not know where one
    bone's tracks end and the next begin, and the marker byte's real role
    (constant 0x3c) is not understood, only that it reliably precedes a
    monotonically-increasing 0..100 "percent of clip" time value on a
    10-byte pitch. Do not build on this without re-reading animation.md's
    confidence notes.
    """
    hits = []
    i = 0
    n = len(track_data)
    while i < n - 2:
        if track_data[i] == 0x3C:
            t = struct.unpack_from("<H", track_data, i + 1)[0]
            if t <= 100:
                hits.append((i, t))
        i += 1
    return hits


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

def roundtrip_check(paths):
    """Read every path, write it back, and assert byte-for-byte equality.
    `paths` is an iterable of (kind, path) where kind is "pab" or "paa"."""
    results = []
    for kind, path in paths:
        data = open(path, "rb").read()
        if kind == "pab":
            obj = read_pab(data)
            back = write_pab(obj)
        elif kind == "paa":
            obj = read_paa(data)
            back = write_paa(obj)
        else:
            raise ValueError(kind)
        ok = (back == data)
        results.append((path, ok, len(data), len(back)))
    return results


if __name__ == "__main__":
    import sys
    kind, path = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    if kind == "pab":
        sk = read_pab(data)
        print(f"version={sk.version} unk_u16={sk.unk_u16} "
              f"first_id_a={sk.first_id_a:#x} first_id_b={sk.first_id_b:#x} "
              f"bones={len(sk.bones)}")
        for i, b in enumerate(sk.bones):
            print(f"  {i:2d} parent={b.parent:3d} {b.name:24s} "
                  f"scale={b.scale} quat={b.quat} trans={b.trans}")
        back = write_pab(sk)
        print("round-trip OK" if back == data else "ROUND-TRIP MISMATCH")
    elif kind == "paa":
        an = read_paa(data)
        print(f"version={an.version} count_u16={an.count_u16} unk_u16={an.unk_u16:#06x} "
              f"tag={an.tag!r} scale={an.scale} track_bytes={len(an.track_data)}")
        back = write_paa(an)
        print("round-trip OK" if back == data else "ROUND-TRIP MISMATCH")
