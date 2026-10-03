"""Read a skeleton variation (.pabc): a character's own proportions.

Characters share a few skeletons (phm_01 for every man) and differ by a
skeleton variation, named by the body and head prefabs' data files, such as
character/binary/skeletonvariation/1_pc/1_phm/nude/cd_phm_00_nude_01_0002.pabc
for Kliff's body and .../head/head/cd_phm_macduff_head_0001.pabc for his head.

Layout, read on 3 October 2026 and checked on the 97 male variations:

    0x00  "PAR " and 12 bytes the same in every file
    0x10  u32 record count
    0x14  records of 196 bytes:
            u32       bone name hash, as clips use (paa_codec.bone_hash)
            16 f32    A, the bone's world bind matrix, column major, with scale
            16 f32    B, the same bone's local matrix without scale
            16 f32    C, packed: 3 x 1.0, rotation quaternion (x, y, z, w),
                      position, scale, and the inverse of the parent's scale
    then 4 bytes

C chains as world = parent world @ diag(inverse parent scale) @ T(rotation,
position, scale): children cancel their parent's scale, as Maya's segment
scale compensation does. That reproduces A to 0.01 mm for most bones, but
some records are relative to a different parent than the skeleton's (Kliff's
clavicles to the neck rather than Spine2, the tongue to the lower teeth), so
the add-on takes A, the world matrix, as the variation and works out each
bone's local from it against the skeleton's own parent.

A body variation covers about 420 of phm_01's 447 bones and a head variation
about 207, the face. Kliff's body variation moves no main joint; it scales
bones across their length (thighs 1.12 thicker, spine 0.91, the shoulder
muscle helpers up to 1.66) and moves and turns helper bones by up to 31 mm.
"""

import struct

RECORD = 196


def read_variation(data):
    """{bone hash: world bind matrix as 16 floats, row major, game space}."""
    if data[:4] != b"PAR " or len(data) < 0x14:
        raise ValueError("not a skeleton variation (.pabc)")
    count = struct.unpack_from("<I", data, 0x10)[0]
    if 0x14 + count * RECORD > len(data):
        raise ValueError(f"skeleton variation says {count} bones but holds {(len(data) - 0x14) // RECORD}")
    out = {}
    for r in range(count):
        off = 0x14 + r * RECORD
        bone = struct.unpack_from("<I", data, off)[0]
        m = struct.unpack_from("<16f", data, off + 4)
        # Column major on disk: m[4 * column + row].
        out[bone] = tuple(m[4 * c + r] for r in range(4) for c in range(4))
    return out
