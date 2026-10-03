"""Read Crimson Desert's skinned meshes (.pac), for display on an armature.

Worked out on 3 October 2026 against all 12,963 meshes of pack group 0009.
The vertex record's layout follows the notes in CrimsonForge
(github.com/hzeemr/crimsonforge, MIT), which its author read from the game's
skinning shader; the rest was read from the files and checked on every mesh.

A .pac is a PAR file: "PAR ", version bytes, then at 0x10 eight (stored
size, size) pairs, one per section, and the sections from 0x50 on. In the
packs each section is an LZ4 block (formats/paz.py, par_unpack); offsets
inside the file refer to the plain layout.

Section 0 describes the mesh. Sections 1 to 4 hold geometry, one per level of
detail, the most detailed last.

Section 0, all integers little-endian:

    u32  flags (see below)
    u8   n, the number of detail levels with geometry (2 to 4)
    n x  u32 file offset of the level's vertices, most detailed first
    n x  u32 file offset of the level's indices
    u16  submesh count, then per submesh:
         u8 length and the submesh name, u8 length and the material name
         3 bytes, 8 x f32: two numbers not used here, then the bounding
         box's minimum xyz and extent xyz
         u8 k, the detail levels this submesh has
         4 bytes: which of its k levels each of the game's 4 levels uses
         k x u16 vertex count, k x u32 index count
    blocks that some flags add (below)
    u16  palette size, then that many u32 bone name hashes (the same hash
         the clips use, hashlittle(name, 0xC5EDE))
    6 x  f32 the whole mesh's bounding box
    then data the add-on does not read: a Havok tag file on most meshes

Level j of the file holds, in submesh order, the vertices of every submesh
with more than j levels, then their indices. The counts add up exactly: the
vertices end where the level's index offset points, and the indices end
where the section ends.

A vertex record is 40 bytes:

    +0   3 x u16 position, min + value / 32767 * extent per axis
    +6   2 bytes not used here
    +8   2 x f16 texture coordinates, +12 a second pair
    +16  u32 normal: bits 10-19 x, 20-29 y, as value / 511.5 - 1; z is
         sqrt(1 - x^2 - y^2), negative when bit 30 is set
    +20  2 x u32, three 10-bit palette slots in each
    +28  8 x u8 weights, the first six used
    +36  3 bytes, +39 a byte whose low 6 bits are 63 when all six slots
         count and anything else when only the first four do

Weights add up to 255 on 96% of vertices outside cloth meshes and 92% in
all; the rest add up to less, and the reader scales each vertex's weights to
a sum of 1, as Blender's armature deform does anyway.

Indices are u16 triangles, counted from the submesh's first vertex.

Flags in the first u32 of section 0 that put a block before the palette:

    0x2000   a bounding box, u16 n and n x 16-byte tree nodes, u16 m and
             m x 24-byte boxes
    0x1      the mesh's own bone list (below)
    0x4, 0x100, 0x200, 0x1000, 0x8000
             cloth simulation data of varying layout

Flags 0x2, 0x80, 0x20000, 0x1000000 and 0x2000000 add nothing there. With
only those and 0x2000 the palette's place follows from the layout (5,893
meshes); with any other flag the reader finds the palette by its hashes, a
u16 n followed by n words that are all known bone hashes (6,677 meshes). On
all 5,778 meshes where both work they find the same palette; on the other
115 one palette bone is in no skeleton file, so the search cannot match it.

Flag 0x1 (2,023 meshes: weapons, props, some armour) gives the mesh a bone
list of its own:

    u32  n, then per bone:
         u32 name hash, u8 length and name, i32 parent index (-1 for root)
         4 x 16 f32, column major: world bind, its inverse, local bind and
         one more; then 3 f32 scale, 4 f32 rotation (x, y, z, w), 3 f32
         position, which chained from the root give the world bind

Its palette names these bones. The list comes right after the parts on
1,494 of those meshes and after cloth data of varying layout on the rest,
and flags such as 0x40 and 0x4000 put a few more bytes between it and the
palette. The reader finds the list by its shape, a count and bones whose
names hash to their stored hashes, and then the palette among the known and
the mesh's own hashes: that works on 2,022 of the 2,023. Armour lists
repeat skeleton bones (Bip01, Bip01 Spine and on) with physics bones under
them; a weapon's root, such as B_Weapon_0001, is in no character skeleton,
and the weapon is attached at a socket instead (formats/sockets.py).
"""

import struct
from dataclasses import dataclass, field

from .paz import par_unpack

STRIDE = 40
FLAG_BONES = 0x1
FLAG_TREE = 0x2000
NO_BLOCK = 0x2 | 0x80 | 0x20000 | 0x1000000 | 0x2000000

_VERTEX = struct.Struct("<3H2x2e4xIII8B3xB")


@dataclass
class Submesh:
    name: str
    material: str
    bbox_min: tuple
    bbox_extent: tuple
    lod_map: tuple
    vertex_counts: tuple
    index_counts: tuple
    positions: list = field(default_factory=list)   # game space, metres
    uvs: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    skin: list = field(default_factory=list)        # per vertex [(palette slot, weight 0..1)]
    triangles: list = field(default_factory=list)


@dataclass
class Bone:
    hash: int
    name: str
    parent: int             # index in the mesh's bone list, -1 for the root
    world: tuple            # world bind, 16 floats, row major, game space


@dataclass
class Mesh:
    flags: int
    levels: int
    submeshes: list
    palette: tuple          # bone name hashes; a vertex's slots index this
    bbox: tuple
    palette_found_by: str   # "layout" or "hashes"
    bones: list = field(default_factory=list)   # the mesh's own bones (flag 0x1)


def _name(s, off):
    n = s[off]
    return s[off + 1:off + 1 + n].decode("ascii", "replace"), off + 1 + n


def _sections(data):
    out, off = [], 0x50
    for i in range(8):
        stored, size = struct.unpack_from("<II", data, 0x10 + 8 * i)
        if size:
            if stored:
                raise ValueError("compressed section; unpack the file first")
            out.append((off, size))
            off += size
    if off != len(data):
        raise ValueError(f"sections end at {off}, the file at {len(data)}")
    return out


def _find_palette(s, start, known):
    for o in range(start, len(s) - 6):
        n = struct.unpack_from("<H", s, o)[0]
        if 0 < n < 1024 and o + 2 + 4 * n <= len(s) and struct.unpack_from("<I", s, o + 2)[0] in known \
                and all(w in known for w in struct.unpack_from(f"<{n}I", s, o + 2)):
            return o
    return None


def _bones_at(s, o):
    """(end offset, [Bone]) for a bone list starting at `o`, or None."""
    from .hashlittle import hashlittle
    if o + 4 > len(s):
        return None
    n = struct.unpack_from("<I", s, o)[0]
    if not 0 < n < 300:
        return None
    o += 4
    bones = []
    for i in range(n):
        if o + 5 > len(s):
            return None
        h, size = struct.unpack_from("<IB", s, o)
        raw = s[o + 5:o + 5 + size]
        if not 0 < size < 64 or not all(32 <= c < 127 for c in raw) or hashlittle(raw, 0xC5EDE) != h:
            return None
        if o + 9 + size + 296 > len(s):
            return None
        parent = struct.unpack_from("<i", s, o + 5 + size)[0]
        if not -1 <= parent < i:
            return None
        m = struct.unpack_from("<16f", s, o + 9 + size)
        bones.append(Bone(h, raw.decode("ascii"), parent, tuple(m[4 * c + r] for r in range(4) for c in range(4))))
        o += 9 + size + 296
    return o, bones


def _find_bones(s, start):
    for o in range(start, len(s) - 9):
        if s[o + 1] == 0 and s[o + 2] == 0 and s[o + 3] == 0:
            found = _bones_at(s, o)
            if found:
                return found
    return None


def read_pac(data, level=0, known_hashes=None):
    """The mesh at detail level `level` (0 is the most detailed).
    `known_hashes`, a set of bone name hashes, finds the palette on meshes
    whose flags put blocks the reader does not parse before it."""
    if data[:4] != b"PAR ":
        raise ValueError("not a PAR file")
    if any(struct.unpack_from("<I", data, 0x10 + 8 * i)[0] for i in range(8)):
        data = par_unpack(data)
    secs = _sections(data)
    s0, size0 = secs[0]
    s = data[s0:s0 + size0]
    flags = struct.unpack_from("<I", s, 0)[0]
    levels = s[4]
    off = 5
    vstart = struct.unpack_from(f"<{levels}I", s, off)
    istart = struct.unpack_from(f"<{levels}I", s, off + 4 * levels)
    off += 8 * levels
    count = struct.unpack_from("<H", s, off)[0]
    off += 2
    subs = []
    for _ in range(count):
        name, off = _name(s, off)
        material, off = _name(s, off)
        f = struct.unpack_from("<8f", s, off + 3)
        off += 35
        k = s[off]
        lod_map = tuple(s[off + 1:off + 5])
        off += 5
        vc = struct.unpack_from(f"<{k}H", s, off)
        ic = struct.unpack_from(f"<{k}I", s, off + 2 * k)
        off += 6 * k
        subs.append(Submesh(name, material, f[2:5], f[5:8], lod_map, vc, ic))

    found_by = "layout"
    bones = []
    if flags & FLAG_BONES:
        found = _find_bones(s, off)
        if found is None:
            raise ValueError(f"this mesh's flags ({flags:#x}) give it a bone list of its own, which was not found")
        after, bones = found
        own = set(known_hashes or ()) | {b.hash for b in bones}
        at = _find_palette(s, after, own)
        if at is None:
            raise ValueError("no palette of known bone hashes follows this mesh's own bone list")
        off, found_by = at, "hashes"
    elif not flags & ~(NO_BLOCK | FLAG_TREE):
        if flags & FLAG_TREE:
            n = struct.unpack_from("<H", s, off + 24)[0]
            off += 26 + 16 * n
            m = struct.unpack_from("<H", s, off)[0]
            off += 2 + 24 * m
    else:
        at = _find_palette(s, off, known_hashes) if known_hashes else None
        if at is None:
            raise ValueError(f"this mesh's flags ({flags:#x}) put data the add-on does not read before its bone "
                             "palette, and no run of known bone hashes was found after it")
        off, found_by = at, "hashes"
    n = struct.unpack_from("<H", s, off)[0]
    palette = struct.unpack_from(f"<{n}I", s, off + 2)
    off += 2 + 4 * n
    bbox = struct.unpack_from("<6f", s, off)

    if not 0 <= level < levels:
        raise ValueError(f"the mesh has {levels} detail levels, not {level + 1}")
    vbase, ibase = vstart[level], istart[level]
    total_v = sum(sb.vertex_counts[level] for sb in subs if level < len(sb.vertex_counts))
    total_i = sum(sb.index_counts[level] for sb in subs if level < len(sb.index_counts))
    end = next(o + sz for o, sz in secs if o <= vbase < o + sz)
    if vbase + total_v * STRIDE != ibase or ibase + 2 * total_i != end:
        raise ValueError(f"level {level}: {total_v} vertices and {total_i} indices do not fill their section")

    for sb in subs:
        if level >= len(sb.vertex_counts):
            continue
        nv, ni = sb.vertex_counts[level], sb.index_counts[level]
        mn, ext = sb.bbox_min, sb.bbox_extent
        for rec in _VERTEX.iter_unpack(data[vbase:vbase + nv * STRIDE]):
            qx, qy, qz, u, v, nrm, lo, hi = rec[:8]
            w = rec[8:16]
            sb.positions.append((mn[0] + qx / 32767.0 * ext[0], mn[1] + qy / 32767.0 * ext[1],
                                 mn[2] + qz / 32767.0 * ext[2]))
            sb.uvs.append((u, v))
            nx = ((nrm >> 10) & 0x3FF) / 511.5 - 1.0
            ny = ((nrm >> 20) & 0x3FF) / 511.5 - 1.0
            nz = max(0.0, 1.0 - nx * nx - ny * ny) ** 0.5
            sb.normals.append((nx, ny, -nz if nrm & 0x40000000 else nz))
            slots = (lo & 0x3FF, (lo >> 10) & 0x3FF, (lo >> 20) & 0x3FF, hi & 0x3FF, (hi >> 10) & 0x3FF, (hi >> 20) & 0x3FF)
            used = 6 if rec[16] & 0x3F == 63 else 4
            total = sum(w[:used]) or 1
            sb.skin.append([(slots[j], w[j] / total) for j in range(used) if w[j]])
        idx = struct.unpack_from(f"<{ni}H", data, ibase)
        sb.triangles = [idx[i:i + 3] for i in range(0, ni - 2, 3)]
        vbase += nv * STRIDE
        ibase += 2 * ni
    return Mesh(flags, levels, [sb for sb in subs if level < len(sb.vertex_counts)], palette, bbox, found_by, bones)
