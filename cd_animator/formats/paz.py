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
plain or as LZ4 blocks (compression type 2). Type 1 keeps the file's own
header and compresses the parts after it: a mesh (.pac) stores each section
of its PAR file as an LZ4 block, a texture (.dds) its four largest mip levels.
XML-derived files, such as a mesh's material file (.pac_xml), are encrypted
with ChaCha20 (encryption type 3) and then LZ4 compressed; they are
decrypted first.
"""

import os
import struct
from dataclasses import dataclass

from . import chacha

COMPRESSION_PAR = 1    # a PAR file whose sections are LZ4 blocks (meshes)
COMPRESSION_LZ4 = 2
ENCRYPTION_CHACHA = 3


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
    def encryption(self):
        return (self.flags >> 20) & 0x0F

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


# Bytes per 4x4 block of the block-compressed formats, by DDS four-character
# code or DXGI format number; others are 16.
_BLOCK8 = {b"DXT1", b"ATI1", b"BC4U", b"BC4S"}
_DXGI_BLOCK8 = {70, 71, 72, 79, 80, 81}


def _mip_sizes(head):
    """(header size, size of each mip level) of a DDS file."""
    height, width, _pitch, _depth, mips = struct.unpack_from("<5I", head, 12)
    four = head[0x54:0x58]
    pf_flags, bits = struct.unpack_from("<I", head, 0x50)[0], struct.unpack_from("<I", head, 0x58)[0]
    size = 128
    if four == b"DX10":
        size = 148
        block = 8 if struct.unpack_from("<I", head, 128)[0] in _DXGI_BLOCK8 else 16
    elif pf_flags & 0x4:
        block = 8 if four in _BLOCK8 else 16
    else:
        block = None    # uncompressed pixels, `bits` each
    out = []
    for _ in range(max(1, mips)):
        if block is None:
            out.append(width * height * bits // 8)
        else:
            out.append(max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block)
        width, height = max(1, width // 2), max(1, height // 2)
    return size, out


def dds_unpack(raw, size):
    """A DDS texture with its mip levels plain. The packs store the header
    as it is and the mip levels in order, largest first; the header's first
    four reserved words hold the stored size of the four largest levels, and
    a level whose stored size is below its real size is an LZ4 block."""
    if raw[:4] != b"DDS ":
        raise ValueError("not a DDS file")
    head, sizes = _mip_sizes(raw)
    stored = struct.unpack_from("<4I", raw, 0x20)
    out = [raw[:head]]
    off = head
    for i, n in enumerate(sizes):
        c = stored[i] if i < 4 and stored[i] else n
        chunk = raw[off:off + c]
        out.append(lz4_block(chunk, n) if c < n else bytes(chunk))
        off += c
    data = b"".join(out)
    if off != len(raw) or len(data) != size:
        raise ValueError(f"DDS levels end at {off} of {len(raw)} bytes and unpack to {len(data)}, not {size}")
    return data


def read(entry):
    """The file's bytes, decrypted and unpacked."""
    with open(entry.paz, "rb") as f:
        f.seek(entry.offset)
        data = f.read(entry.stored if entry.stored != entry.size else entry.size)
    if entry.encryption == ENCRYPTION_CHACHA:
        data = chacha.decrypt(data, entry.name)
    elif entry.encryption:
        raise ValueError(f"{entry.path} uses encryption type {entry.encryption}, which the add-on does not read")
    if entry.stored != entry.size:
        if entry.compression == COMPRESSION_PAR:
            return dds_unpack(data, entry.size) if data[:4] == b"DDS " else par_unpack(data)
        if entry.compression != COMPRESSION_LZ4:
            raise ValueError(f"{entry.path} uses compression type {entry.compression}, which the add-on does not read")
        data = lz4_block(data, entry.size)
    return data
