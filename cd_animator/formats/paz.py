"""Read files straight out of Crimson Desert's packs.

The game keeps its files in numbered group folders (0000, 0001, ...), each
with an index, 0.pamt, and data files 0.paz, 1.paz and so on. Clips,
skeletons and blends are in group 0009; clip metadata and action charts in
0010.

The index holds, in order: a header with the number of .paz files, their
table, a tree of folder name fragments, a tree of file name fragments, a list
of folder records (folder, index of its first file, file count, hash) and the
file records (file name node, offset in the .paz, stored size, size, flags).
A file's full path is its folder's path, a slash and its name. The parser in
master looter's paz tools keeps only the top folder, which is not enough:
26,553 clip names in 0009 appear in more than one folder with different data.

The clips, skeletons, blends, metadata and charts the add-on reads are stored
plain or as LZ4 blocks (compression type 2). Meshes (.pac) are type 1: the
file keeps its PAR header and each section inside it is an LZ4 block. Only
XML-derived files are also encrypted, and the add-on reads none of those.
"""

import os
import struct
from dataclasses import dataclass

COMPRESSION_PAR = 1    # a PAR file whose sections are LZ4 blocks (meshes)
COMPRESSION_LZ4 = 2


@dataclass(frozen=True)
class Entry:
    path: str        # the game's path, as the game's own logs spell it
    paz: str         # the .paz file holding it
    offset: int
    stored: int      # size in the .paz
    size: int        # size once unpacked
    flags: int

    @property
    def compression(self):
        return (self.flags >> 16) & 0x0F

    @property
    def name(self):
        return self.path.rsplit("/", 1)[-1]


def _tree(data, off, size):
    """{offset: (parent offset, fragment)} for a fragment tree."""
    nodes = {}
    start = off
    while off < start + size:
        parent, n = struct.unpack_from("<IB", data, off)
        nodes[off - start] = (parent, data[off + 5:off + 5 + n].decode("utf-8", "replace"))
        off += 5 + n
    return nodes


def _joiner(nodes):
    cache = {}

    def path(ref):
        if ref in cache:
            return cache[ref]
        parts = []
        cur = ref
        while cur != 0xFFFFFFFF and cur in nodes and cur not in cache:
            parent, text = nodes[cur]
            parts.append(text)
            cur = parent
        head = cache.get(cur, "")
        result = head + "".join(reversed(parts))
        cache[ref] = result
        return result
    return path


def read_index(pamt_path, keep=None):
    """The entries of one group's index. `keep` is a set of lower-case
    extensions without the dot; other files are skipped."""
    with open(pamt_path, "rb") as f:
        data = f.read()
    folder_dir = os.path.dirname(pamt_path)
    stem = int(os.path.splitext(os.path.basename(pamt_path))[0])
    off = 4
    paz_count = struct.unpack_from("<I", data, off)[0]
    off += 4 + 8
    off += paz_count * 8 + max(paz_count - 1, 0) * 4

    size = struct.unpack_from("<I", data, off)[0]
    folders = _joiner(_tree(data, off + 4, size))
    off += 4 + size
    size = struct.unpack_from("<I", data, off)[0]
    names = _joiner(_tree(data, off + 4, size))
    off += 4 + size

    folder_count = struct.unpack_from("<I", data, off)[0]
    off += 8
    owner = []
    for i in range(folder_count):
        ref, first, count, _hash = struct.unpack_from("<IIII", data, off + 16 * i)
        owner.append((first, count, ref))
    off += 16 * folder_count

    file_count = (len(data) - off) // 20
    folder_of = [None] * file_count
    for first, count, ref in owner:
        prefix = folders(ref)
        for i in range(first, min(first + count, file_count)):
            folder_of[i] = prefix

    out = []
    paz_files = {}
    for i in range(file_count):
        node, offset, stored, size, flags = struct.unpack_from("<IIIII", data, off + 20 * i)
        name = names(node)
        if keep is not None:
            dot = name.rfind(".")
            if dot < 0 or name[dot + 1:].lower() not in keep:
                continue
        index = flags & 0xFF
        paz = paz_files.get(index)
        if paz is None:
            paz = paz_files[index] = os.path.join(folder_dir, f"{stem + index}.paz")
        prefix = folder_of[i]
        path = f"{prefix}/{name}" if prefix else name
        out.append(Entry(path, paz, offset, stored, size, flags))
    return out


def lz4_block(src, size):
    """Decompress one LZ4 block (no frame) to `size` bytes."""
    dst = bytearray()
    i, n = 0, len(src)
    while i < n:
        token = src[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]
        i += lit
        if i >= n:
            break
        back = src[i] | (src[i + 1] << 8)
        i += 2
        match = token & 15
        if match == 15:
            while True:
                b = src[i]
                i += 1
                match += b
                if b != 255:
                    break
        match += 4
        start = len(dst) - back
        if back <= 0 or start < 0:
            raise ValueError("LZ4 block points before its start")
        if back >= match:
            dst += dst[start:start + match]
        else:
            for k in range(match):
                dst.append(dst[start + k])
    if len(dst) != size:
        raise ValueError(f"LZ4 block gave {len(dst)} bytes, not {size}")
    return bytes(dst)


def par_unpack(raw):
    """A PAR file with its sections plain. Meshes (compression type 1 in the
    index) keep the PAR header and table and store each section as an LZ4
    block; the table holds (stored size, size) per section, a stored size of
    0 meaning plain. The result has every section plain and every stored
    size 0, the layout the game's offsets inside the file refer to."""
    if raw[:4] != b"PAR " or len(raw) < 0x50:
        raise ValueError("not a PAR file")
    head = bytearray(raw[:0x50])
    body = []
    off = 0x50
    for i in range(8):
        stored, size = struct.unpack_from("<II", raw, 0x10 + 8 * i)
        if not size:
            continue
        chunk = raw[off:off + (stored or size)]
        body.append(lz4_block(chunk, size) if stored else bytes(chunk))
        struct.pack_into("<I", head, 0x10 + 8 * i, 0)
        off += stored or size
    if off != len(raw):
        raise ValueError(f"PAR sections end at {off}, the file at {len(raw)}")
    return bytes(head) + b"".join(body)


def read(entry):
    """The file's bytes, unpacked."""
    with open(entry.paz, "rb") as f:
        f.seek(entry.offset)
        data = f.read(entry.stored if entry.stored != entry.size else entry.size)
    if entry.stored != entry.size:
        if entry.compression == COMPRESSION_PAR:
            return par_unpack(data)
        if entry.compression != COMPRESSION_LZ4:
            raise ValueError(f"{entry.path} uses compression type {entry.compression}, which the add-on does not read")
        data = lz4_block(data, entry.size)
    return data
