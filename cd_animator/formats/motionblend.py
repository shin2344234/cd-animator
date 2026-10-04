"""Crimson Desert blends (.motionblending): the blend spaces that mix
locomotion and aiming clips by speed, angle or distance.

From Broomy's research (its blend codec), which parses all 1,688 of the
game's blends and writes each back byte for byte. The clips a blend mixes
are root.values["_animationFileNames"], paths under character/motion/ with
.paa; each example names one by its index in that list.

Reader and writer for .motionblending (a reflection serialised ParameterizedMotionSpace).

Game path: character/binary/motionblending/<name>.motionblending, pack group 0009.
1688 entries in build 1.0.0.2976 (1644 distinct paths, 44 paths hold two different
versions). motionblend.md has the format, the evidence and the confidence per field.
This module parses all 1688 and writes each back byte for byte
(see check_corpus() at the bottom, or run this file with a folder name).

The file is self describing. It starts with a type schema, then one object tree.

    ff ff                       magic
    u32 ver                     3 or 4
    [8 bytes]                   only when ver >= 4, 0 in every file
    u32 sver                    14 or 15, the schema revision (not the file version)
    u16 ntypes
    ntypes x type:   u32 len + name, u16 nfields,
                     nfields x field: u32 len + name, u32 len + type name,
                                      u16 kind, u16 size, u16 flags, u16 extra
    object table (32 bytes):
        u32 0, u32 1, u32 total_file_size, u32 0, u64 -1, u32 body_offset, u32 body_size
    root object (type 0):
        u16 L, L mask bytes (bit i = field i of the type is stored), u32 0, fields
    fields, in schema order. A scalar, string or enum is stored only when its mask bit is set.
    A list is always stored (see below). Values:
        kind 0 scalar     `size` bytes
        kind 1 string     u32 length, bytes (not NUL terminated)
        kind 2 enum       as a string (the enum name)
        kind 3 list       u32 count, count x size bytes
        kind 10 strings   u32 count, count x (u32 length, bytes)
        kind 7 objects    u32 count, 13 byte list header, count x element
    A list in a file with sver 15 carries one extra byte in front: 0 then the list as above,
    or 1 for an empty list with nothing after it.
    element (object inside a list):
        u16 L, L mask bytes, u16 type index, u8 0, u64 id, u64 ptr, fields, u32 footer
        ptr = file offset of its own field + 4, footer = byte length of the fields + 4.
    list header (13 bytes): u8 0, u64 K, u32 0. K is the id of the last element, except in
    _triangles lists, where it is that id or a little more (unknown rule).
    A kind 7 list with count 0 and its mask bit clear still carries the 13 byte header.

The codec keeps every id and K as stored. It recomputes ptr, footer and the object table when it
writes, so lists can be edited as long as ids and K are supplied for new elements. Float values are kept as Python floats (exact for any float32 that is not a
signalling NaN); check_corpus proves the round trip.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field

U = struct.unpack_from

KIND_SCALAR, KIND_STRING, KIND_ENUM, KIND_LIST, KIND_OBJLIST, KIND_STRLIST = 0, 1, 2, 3, 7, 10


class FormatError(ValueError):
    pass


# ---------------------------------------------------------------------------
# schema

@dataclass
class FieldDef:
    name: str
    type_name: str
    kind: int
    size: int
    flags: int
    extra: int


@dataclass
class TypeDef:
    name: str
    fields: list

    def index(self, name):
        for i, f in enumerate(self.fields):
            if f.name == name:
                return i
        raise KeyError(name)


@dataclass
class Schema:
    ver: int
    sver: int
    ver_extra: bytes
    types: list

    def type_index(self, name):
        for i, t in enumerate(self.types):
            if t.name == name:
                return i
        raise KeyError(name)


def _read_schema(b):
    if b[:2] != b"\xff\xff":
        raise FormatError("bad magic")
    ver, = U("<I", b, 2)
    o = 6
    extra = b""
    if ver >= 4:
        extra = bytes(b[o:o + 8])
        o += 8
    sver, = U("<I", b, o)
    o += 4
    nt, = U("<H", b, o)
    o += 2
    types = []
    for _ in range(nt):
        n, = U("<I", b, o)
        o += 4
        name = bytes(b[o:o + n]).decode("ascii")
        o += n
        nf, = U("<H", b, o)
        o += 2
        fl = []
        for _ in range(nf):
            n, = U("<I", b, o)
            o += 4
            fn = bytes(b[o:o + n]).decode("ascii")
            o += n
            n, = U("<I", b, o)
            o += 4
            tn = bytes(b[o:o + n]).decode("ascii")
            o += n
            kind, size, flags, ext = U("<HHHH", b, o)
            o += 8
            fl.append(FieldDef(fn, tn, kind, size, flags, ext))
        types.append(TypeDef(name, fl))
    return Schema(ver, sver, extra, types), o


def _write_schema(s: Schema) -> bytes:
    out = bytearray(b"\xff\xff")
    out += struct.pack("<I", s.ver)
    if s.ver >= 4:
        out += s.ver_extra
    out += struct.pack("<IH", s.sver, len(s.types))
    for t in s.types:
        nb = t.name.encode("ascii")
        out += struct.pack("<I", len(nb)) + nb + struct.pack("<H", len(t.fields))
        for f in t.fields:
            a, c = f.name.encode("ascii"), f.type_name.encode("ascii")
            out += struct.pack("<I", len(a)) + a + struct.pack("<I", len(c)) + c
            out += struct.pack("<HHHH", f.kind, f.size, f.flags, f.extra)
    return bytes(out)


# ---------------------------------------------------------------------------
# objects

@dataclass
class ObjList:
    """A list of objects (kind 7). K is the 13 byte header's value, kept as stored. It equals the
    last element's id in every dimension, phase and example list and in 818 of the 818
    _delaunayTriangles lists; in _triangles lists it is the last id in 850 of 1192 and up to
    a few above it otherwise (rule not known). Set it yourself when you add elements."""
    items: list = field(default_factory=list)
    K: int = 0xFFFFFFFFFFFFFFFF
    empty_flag: bool = False      # sver 15 only: the prefix byte was 1 (empty, nothing follows)


@dataclass
class Obj:
    type_idx: int
    mask: bytes
    values: dict                 # field name -> decoded value, only stored fields
    id: int = 0                  # elements only
    z: int = 0                   # elements only, the byte after the type index (0 in every file)
    offsets: dict = field(default_factory=dict)   # field name -> absolute offset of its data, set by the parser
    # a list field the file stores but this dict may hold as ObjList / list


@dataclass
class MotionBlend:
    schema: Schema
    root: Obj
    table_zero1: int = 0
    table_one: int = 1
    table_zero2: int = 0
    table_ref: int = 0xFFFFFFFFFFFFFFFF

    def type(self, obj_or_idx):
        i = obj_or_idx if isinstance(obj_or_idx, int) else obj_or_idx.type_idx
        return self.schema.types[i]


_SCALAR_FMT = {("float", 4): "<f", ("uint32", 4): "<I", ("int32", 4): "<i", ("uint16", 2): "<H",
               ("int16", 2): "<h", ("bool", 1): "<B", ("uint8", 1): "<B", ("int8", 1): "<b",
               ("uint64", 8): "<Q", ("int64", 8): "<q"}


def _decode_list(fd: FieldDef, raw: bytes):
    """Decode `count x size` bytes of a kind 3 list into python values."""
    n = len(raw) // fd.size
    if fd.type_name == "float2":
        return [struct.unpack_from("<2f", raw, i * 8) for i in range(n)]
    fmt = _SCALAR_FMT.get((fd.type_name, fd.size))
    if fmt is None:
        return bytes(raw)
    return list(struct.unpack("<%d%s" % (n, fmt[1]), raw))


def _encode_list(fd: FieldDef, vals) -> bytes:
    if isinstance(vals, (bytes, bytearray)):
        return bytes(vals)
    if fd.type_name == "float2":
        return b"".join(struct.pack("<2f", *v) for v in vals)
    fmt = _SCALAR_FMT[(fd.type_name, fd.size)]
    return struct.pack("<%d%s" % (len(vals), fmt[1]), *vals)


def _decode_scalar(fd: FieldDef, raw: bytes):
    if fd.type_name == "float2":
        return struct.unpack("<2f", raw)
    fmt = _SCALAR_FMT.get((fd.type_name, fd.size))
    if fmt is None:
        return bytes(raw)
    v, = struct.unpack(fmt, raw)
    return bool(v) if fd.type_name == "bool" else v


def _encode_scalar(fd: FieldDef, v) -> bytes:
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if fd.type_name == "float2":
        return struct.pack("<2f", *v)
    fmt = _SCALAR_FMT[(fd.type_name, fd.size)]
    return struct.pack(fmt, int(v) if fd.type_name == "bool" else v)


# ---------------------------------------------------------------------------
# parse

def parse(data: bytes) -> MotionBlend:
    b = bytes(data)
    schema, o = _read_schema(b)
    z1, one, total, z2, ref, off, size = U("<IIIIQII", b, o)
    p = o + 32
    if (z1, one, z2, ref) != (0, 1, 0, 0xFFFFFFFFFFFFFFFF):
        raise FormatError("unexpected object table %r" % ((z1, one, z2, ref),))
    if total != len(b) or off != p or size != len(b) - off:
        raise FormatError("object table sizes do not match the file")
    types = schema.types

    def read_fields(ti, mask, p, obj):
        td = types[ti]
        for i, fd in enumerate(td.fields):
            pres = (mask[i // 8] >> (i % 8)) & 1 if i // 8 < len(mask) else 0
            islist = fd.kind in (KIND_LIST, KIND_OBJLIST, KIND_STRLIST)
            if not pres and not islist:
                continue
            empty_flag = False
            if islist and schema.sver >= 15:
                pf = b[p]
                p += 1
                if pf == 1:
                    empty_flag = True
                elif pf != 0:
                    raise FormatError("list prefix byte %d at 0x%x" % (pf, p - 1))
            if empty_flag:
                if fd.kind == KIND_OBJLIST:
                    obj.values[fd.name] = ObjList([], 0xFFFFFFFFFFFFFFFF, True)
                elif fd.kind == KIND_STRLIST:
                    obj.values[fd.name] = _EmptyStrList()
                else:
                    obj.values[fd.name] = _EmptyList()
                continue
            obj.offsets[fd.name] = p
            if fd.kind in (KIND_STRING, KIND_ENUM):
                n, = U("<I", b, p)
                obj.values[fd.name] = bytes(b[p + 4:p + 4 + n])
                p += 4 + n
            elif fd.kind == KIND_STRLIST:
                n, = U("<I", b, p)
                p += 4
                lst = []
                for _ in range(n):
                    k, = U("<I", b, p)
                    lst.append(bytes(b[p + 4:p + 4 + k]))
                    p += 4 + k
                obj.values[fd.name] = lst
            elif fd.kind == KIND_SCALAR:
                obj.values[fd.name] = _decode_scalar(fd, b[p:p + fd.size])
                p += fd.size
            elif fd.kind == KIND_LIST:
                n, = U("<I", b, p)
                p += 4
                obj.offsets[fd.name] = p            # offset of the first element
                obj.values[fd.name] = _decode_list(fd, b[p:p + n * fd.size])
                p += n * fd.size
            elif fd.kind == KIND_OBJLIST:
                n, = U("<I", b, p)
                p += 4
                if n or not pres:
                    hz, K, hy = U("<BQI", b, p)
                    if hz != 0 or hy != 0:
                        raise FormatError("list header %r at 0x%x" % ((hz, hy), p))
                    p += 13
                else:
                    K = 0xFFFFFFFFFFFFFFFF
                items = []
                for _ in range(n):
                    e, p = read_element(p)
                    items.append(e)
                obj.values[fd.name] = ObjList(items, K)
                obj.offsets[fd.name] = p
            else:
                raise FormatError("kind %d" % fd.kind)
        return p

    def read_element(p):
        st = p
        L, = U("<H", b, p)
        p += 2
        mask = bytes(b[p:p + L])
        p += L
        ti, z, eid, ptr = U("<HBQQ", b, p)
        if ti >= len(types):
            raise FormatError("element type index %d at 0x%x" % (ti, st))
        want = p + 3 + 8 + 4   # position of the ptr field + 4
        if ptr != want:
            raise FormatError("element ptr 0x%x, expected 0x%x" % (ptr, want))
        p += 19
        e = Obj(ti, mask, {}, eid, z)
        fstart = p
        p = read_fields(ti, mask, p, e)
        foot, = U("<I", b, p)
        if foot != p - fstart + 4:
            raise FormatError("footer %d for %d field bytes at 0x%x" % (foot, p - fstart, st))
        p += 4
        return e, p

    L, = U("<H", b, p)
    p += 2
    mask = bytes(b[p:p + L])
    p += L
    z, = U("<I", b, p)
    if z != 0:
        raise FormatError("root header word %d" % z)
    p += 4
    root = Obj(0, mask, {})
    p = read_fields(0, mask, p, root)
    if p != len(b):
        raise FormatError("%d bytes left after the root object" % (len(b) - p))
    return MotionBlend(schema, root, z1, one, z2, ref)


class _EmptyList(list):
    """A kind 3 list stored as the sver 15 empty prefix byte (1)."""


class _EmptyStrList(list):
    """A string list stored as the sver 15 empty prefix byte (1)."""


# ---------------------------------------------------------------------------
# write

def write(mb: MotionBlend) -> bytes:
    schema = mb.schema
    types = schema.types
    out = bytearray(_write_schema(schema))
    table_at = len(out)
    out += b"\0" * 32            # patched at the end
    body_at = len(out)

    def write_fields(ti, mask, obj, out):
        td = types[ti]
        for i, fd in enumerate(td.fields):
            pres = (mask[i // 8] >> (i % 8)) & 1 if i // 8 < len(mask) else 0
            islist = fd.kind in (KIND_LIST, KIND_OBJLIST, KIND_STRLIST)
            if not pres and not islist:
                continue
            v = obj.values.get(fd.name)
            if islist and schema.sver >= 15:
                is_empty = isinstance(v, (_EmptyList, _EmptyStrList)) or (isinstance(v, ObjList) and v.empty_flag)
                if is_empty:
                    out.append(1)
                    continue
                out.append(0)
            if fd.kind in (KIND_STRING, KIND_ENUM):
                out += struct.pack("<I", len(v)) + v
            elif fd.kind == KIND_STRLIST:
                out += struct.pack("<I", len(v))
                for s in v:
                    out += struct.pack("<I", len(s)) + s
            elif fd.kind == KIND_SCALAR:
                out += _encode_scalar(fd, v)
            elif fd.kind == KIND_LIST:
                raw = _encode_list(fd, v)
                out += struct.pack("<I", len(raw) // fd.size) + raw
            elif fd.kind == KIND_OBJLIST:
                items = v.items
                out += struct.pack("<I", len(items))
                if items or not pres:
                    out += struct.pack("<BQI", 0, v.K, 0)
                for e in items:
                    write_element(e, out)

    def write_element(e, out):
        td_mask = e.mask
        out += struct.pack("<H", len(td_mask)) + td_mask
        out += struct.pack("<HBQ", e.type_idx, e.z, e.id)
        ptr_at = len(out)
        out += struct.pack("<Q", ptr_at + 4)
        fstart = len(out)
        write_fields(e.type_idx, td_mask, e, out)
        out += struct.pack("<I", len(out) - fstart + 4)

    root = mb.root
    out += struct.pack("<H", len(root.mask)) + root.mask + struct.pack("<I", 0)
    write_fields(0, root.mask, root, out)
    total = len(out)
    out[table_at:table_at + 32] = struct.pack("<IIIIQII", mb.table_zero1, mb.table_one, total,
                                              mb.table_zero2, mb.table_ref, body_at, total - body_at)
    return bytes(out)


# ---------------------------------------------------------------------------
# rescaling a blend space

def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _n_dims(mb: MotionBlend) -> int:
    dims = mb.root.values.get("_dimensions")
    return len(dims.items) if dims is not None else 0


def touched_floats(data: bytes, ndims_required=2):
    """Every float that scale_parameters changes, as (absolute file offset, role, axis, value).

    axis is 0 (x), 1 (y) or 2 (z) and says which factor applies. Only files with exactly
    ndims_required dimensions are supported (the Delaunay vertex layout is only understood
    for two dimensions, see motionblend.md)."""
    mb = parse(data)
    nd = _n_dims(mb)
    if nd != ndims_required:
        raise ValueError("file has %d dimensions, expected %d" % (nd, ndims_required))
    root = mb.root
    out = []

    def floats(obj, name, role, axis_of, n=None, stride=1):
        if name not in obj.values or name not in obj.offsets:
            return                      # absent, or an empty list stored as the sver 15 prefix byte
        v = obj.values[name]
        base = obj.offsets[name]
        if isinstance(v, list) and v and not isinstance(v[0], tuple):
            for i, x in enumerate(v):
                ax = axis_of(i)
                if ax is not None:
                    out.append((base + 4 * i, "%s[%d]" % (role, i), ax, x))
        elif isinstance(v, list):               # float2 list
            for i, (x, y) in enumerate(v):
                out.append((base + 8 * i, "%s[%d].x" % (role, i), 0, x))
                out.append((base + 8 * i + 4, "%s[%d].y" % (role, i), 1, y))
        elif isinstance(v, tuple):              # float2 scalar
            out.append((base, role + ".x", 0, v[0]))
            out.append((base + 4, role + ".y", 1, v[1]))

    for k, e in enumerate(root.values["_motionExamples"].items):
        floats(e, "_parameters", "example[%d]._parameters" % k, lambda i: i if i < 3 else None)
    floats(root, "_parameterMinMax", "_parameterMinMax", lambda i: i // 2 if i < 6 else None)
    floats(root, "_thirdDimensionSplitInfo", "_thirdDimensionSplitInfo", lambda i: 2)
    for k, t in enumerate(root.values["_delaunayTriangles"].items):
        floats(t, "_min", "triangulation[%d]._min" % k, None)
        floats(t, "_max", "triangulation[%d]._max" % k, None)
        for j, tr in enumerate(t.values["_triangles"].items):
            floats(tr, "_vert", "triangulation[%d].triangle[%d]._vert" % (k, j), None)
            floats(tr, "_center", "triangulation[%d].triangle[%d]._center" % (k, j), None)
    return out


def scale_parameters(data: bytes, sx: float, sy: float, sz: float = 1.0, in_place=True) -> bytes:
    """Return the file with the parameter space scaled: x by sx, y by sy (and the third axis,
    where one exists, by sz).

    What changes: every example's _parameters, _parameterMinMax (min and max of each axis),
    _thirdDimensionSplitInfo (third axis units, only moves when sz != 1), and, for each
    Delaunay triangulation, _min, _max, every triangle's _vert and _center.
    What stays: the topology (_index lists, _delaunayPointIndexMap), ids, sizes, every other
    field. The file length does not change.

    Factors must be positive (a negative one would swap min and max and flip triangle winding).
    Only two dimension files are accepted. Floats are float32(old * factor), one rounding."""
    if not (sx > 0 and sy > 0 and sz > 0):
        raise ValueError("scale factors must be positive")
    f = (sx, sy, sz)
    mb = parse(data)
    if _n_dims(mb) != 2:
        raise ValueError("only two dimension blend spaces are supported (this one has %d)" % _n_dims(mb))
    b = bytearray(data)
    for off, role, axis, val in touched_floats(data):
        if axis is None:
            continue
        struct.pack_into("<f", b, off, _f32(val * f[axis]))
    return bytes(b)


def set_scalar(mb: MotionBlend, obj: Obj, name: str, value):
    """Store a scalar, string or enum field on obj and set its mask bit, so the writer emits it.
    The file grows by the size of the value when the field was not stored before."""
    td = mb.schema.types[obj.type_idx]
    i = td.index(name)
    fd = td.fields[i]
    if fd.kind not in (KIND_SCALAR, KIND_STRING, KIND_ENUM):
        raise ValueError("%s is not a scalar field" % name)
    m = bytearray(obj.mask)
    m[i // 8] |= 1 << (i % 8)
    obj.mask = bytes(m)
    obj.values[name] = value


def with_animation_scale(data: bytes, k: float) -> bytes:
    """Return the file with the root _animationScale set to k (default 1.0 when not stored).
    In the game's parameter evaluator (RVA 0x2EA98C0) every speed and distance type dimension
    is multiplied by _animationScale / characterScale before it is looked up in the blend
    space, so k > 1 acts like shrinking the example coordinates by 1 / k on those axes,
    equally on every such axis. Both broom dimensions are of that kind."""
    if not k > 0:
        raise ValueError("k must be positive")
    mb = parse(data)
    set_scalar(mb, mb.root, "_animationScale", float(k))
    return write(mb)


def check_invariants(data: bytes):
    """Structural facts that hold in the shipped two dimension files and must survive scaling.
    Returns a list of problems (empty is good)."""
    mb = parse(data)
    root = mb.root
    probs = []
    ex = root.values["_motionExamples"].items
    pts = [tuple((list(e.values.get("_parameters", [])) + [0.0, 0.0])[:2]) for e in ex]
    mm = root.values.get("_parameterMinMax", [])
    if len(mm) == 6 and pts:
        for ax in range(2):
            lo, hi = min(p[ax] for p in pts), max(p[ax] for p in pts)
            if abs(mm[2 * ax] - lo) > 1e-4 * max(1, abs(lo)) or abs(mm[2 * ax + 1] - hi) > 1e-4 * max(1, abs(hi)):
                probs.append("_parameterMinMax axis %d is not the example bounding box" % ax)
    for k, t in enumerate(root.values["_delaunayTriangles"].items):
        tv = t.values
        mn, mx = tv.get("_min", (0.0, 0.0)), tv.get("_max", (0.0, 0.0))
        for ax in range(2):
            lo, hi = min(p[ax] for p in pts), max(p[ax] for p in pts)
            if abs(mn[ax] - lo) > 1e-4 * max(1, abs(lo)) or abs(mx[ax] - hi) > 1e-4 * max(1, abs(hi)):
                probs.append("triangulation %d _min/_max axis %d is not the example bounding box" % (k, ax))
        for j, tr in enumerate(tv["_triangles"].items):
            idx, vert = tr.values["_index"], tr.values["_vert"]
            for i, v in zip(idx, vert):
                if not (i < len(pts) and abs(pts[i][0] - v[0]) <= 1e-4 * max(1, abs(v[0]))
                        and abs(pts[i][1] - v[1]) <= 1e-4 * max(1, abs(v[1]))):
                    probs.append("triangle %d vertex %d is not example %d" % (j, i, i))
                    break
            c = tr.values.get("_center")
            if c is not None:
                cx, cy = sum(v[0] for v in vert) / 3, sum(v[1] for v in vert) / 3
                if abs(cx - c[0]) > 1e-4 * max(1, abs(cx)) or abs(cy - c[1]) > 1e-4 * max(1, abs(cy)):
                    probs.append("triangle %d _center is not the centroid" % j)
    return probs


# ---------------------------------------------------------------------------
# helpers

def field_def(mb: MotionBlend, obj: Obj, name: str) -> FieldDef:
    td = mb.schema.types[obj.type_idx]
    return td.fields[td.index(name)]


def iter_objects(mb: MotionBlend):
    """Yield (path, obj) for the root and every element, depth first, in file order."""
    def walk(path, o):
        yield path, o
        for name, v in o.values.items():
            if isinstance(v, ObjList):
                for i, e in enumerate(v.items):
                    yield from walk(path + "/%s[%d]" % (name, i), e)
    yield from walk("", mb.root)


def type_name(mb: MotionBlend, obj: Obj) -> str:
    return mb.schema.types[obj.type_idx].name


def roundtrip_ok(data: bytes) -> bool:
    return write(parse(data)) == bytes(data)


def check_corpus(folder: str, verbose=False):
    """Parse and rewrite every .motionblending under folder. Returns (passed, total, failures)."""
    fails = []
    n = 0
    for dp, _, fns in os.walk(folder):
        for fn in sorted(fns):
            if not fn.lower().endswith(".motionblending"):
                continue
            n += 1
            path = os.path.join(dp, fn)
            data = open(path, "rb").read()
            try:
                ok = roundtrip_ok(data)
                if not ok:
                    fails.append((path, "bytes differ"))
            except Exception as ex:   # noqa: BLE001
                fails.append((path, "%s: %s" % (type(ex).__name__, ex)))
    return n - len(fails), n, fails


