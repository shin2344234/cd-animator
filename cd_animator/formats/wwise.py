"""Wwise Vorbis (.wem) to Ogg Vorbis, which Blender plays.

A port of the part of ww2ogg (github.com/hcs64/ww2ogg) that the game's
voice files need. ww2ogg is Copyright (c) 2002, Xiph.org Foundation and
Copyright (c) 2009-2016, Adam Gashlin, under this licence:

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions
    are met:

    - Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

    - Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

    - Neither the name of the Xiph.org Foundation nor the names of its
    contributors may be used to endorse or promote products derived from
    this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
    ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
    A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION
    OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
    SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
    LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
    DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
    THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
    OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

packed_codebooks_aoTuV_603.bin, next to this file, is ww2ogg's table of
the Vorbis codebooks Wwise leaves out of its files, under the same licence.

A .wem is a RIFF file with codec 0xFFFF. Its fmt chunk (0x42 bytes, or a
vorb chunk) gives the sample count, where the setup packet and the first
audio packet start in the data chunk, and the two block sizes. Wwise drops
the identification and comment headers, which convert() writes from the
fmt chunk, and shortens the setup header: each codebook is a 10-bit index
into the table, and the floors, residues, mappings and modes leave out
fields that are always the same. Audio packets carry a 2-byte size; with
"mod packets", which every voice file in the game has, the packet type
bit and the window flags of long blocks are left out too, and convert()
puts them back.
"""

import os
import struct

CODEBOOKS = os.path.join(os.path.dirname(__file__), "packed_codebooks_aoTuV_603.bin")
VENDOR = b"converted from Audiokinetic Wwise by CD Animator (after ww2ogg)"


class WemError(ValueError):
    pass


def _ilog(v):
    return v.bit_length()


def _quantvals(entries, dimensions):
    vals = entries >> ((_ilog(entries) - 1) * (dimensions - 1) // dimensions)
    while True:
        acc, acc1 = vals ** dimensions, (vals + 1) ** dimensions
        if acc <= entries < acc1:
            return vals
        vals += -1 if acc > entries else 1


class _Reader:
    """Bits of `data` from the lowest bit of the first byte up, as Vorbis packs them."""

    def __init__(self, data):
        self.value = int.from_bytes(data, "little")
        self.size = len(data) * 8
        self.pos = 0

    def __call__(self, n):
        if self.pos + n > self.size:
            raise WemError("ran out of bits")
        v = (self.value >> self.pos) & ((1 << n) - 1)
        self.pos += n
        return v


class _Writer:
    def __init__(self):
        self.value = 0
        self.pos = 0

    def __call__(self, v, n):
        self.value |= (v & ((1 << n) - 1)) << self.pos
        self.pos += n

    def bytes(self):
        return self.value.to_bytes((self.pos + 7) // 8, "little")


_codebooks = None


def _library():
    global _codebooks
    if _codebooks is None:
        with open(CODEBOOKS, "rb") as f:
            data = f.read()
        table, = struct.unpack_from("<I", data, len(data) - 4)
        count = (len(data) - table) // 4
        offsets = struct.unpack_from(f"<{count}I", data, table)
        _codebooks = (data, offsets)
    return _codebooks


def _rebuild_codebook(i, w):
    """Write codebook `i` of the table in full Vorbis form."""
    data, offsets = _library()
    if not 0 <= i < len(offsets) - 1:
        raise WemError(f"codebook {i} is not in the table")
    r = _Reader(data[offsets[i]:offsets[i + 1]])
    dimensions, entries = r(4), r(14)
    w(0x564342, 24)
    w(dimensions, 16)
    w(entries, 24)
    ordered = r(1)
    w(ordered, 1)
    if ordered:
        w(r(5), 5)
        current = 0
        while current < entries:
            n = _ilog(entries - current)
            number = r(n)
            w(number, n)
            current += number
        if current > entries:
            raise WemError("codebook entries out of range")
    else:
        length_bits, sparse = r(3), r(1)
        if not 0 < length_bits <= 5:
            raise WemError("codebook length bits out of range")
        w(sparse, 1)
        for _ in range(entries):
            present = 1
            if sparse:
                present = r(1)
                w(present, 1)
            if present:
                w(r(length_bits), 5)
    lookup = r(1)
    w(lookup, 4)
    if lookup == 1:
        w(r(32), 32)
        w(r(32), 32)
        value_bits = r(4)
        w(value_bits, 4)
        w(r(1), 1)
        for _ in range(_quantvals(entries, dimensions)):
            w(r(value_bits + 1), value_bits + 1)


def _setup(packet, channels, w):
    """Rebuild the setup header from Wwise's short form. Returns each
    mode's block flag."""
    r = _Reader(packet)
    w(5, 8)
    for c in b"vorbis":
        w(c, 8)
    count = r(8) + 1
    w(count - 1, 8)
    for _ in range(count):
        _rebuild_codebook(r(10), w)
    w(0, 6)   # time count - 1
    w(0, 16)  # the one, dummy, time value

    floors = r(6) + 1
    w(floors - 1, 6)
    for _ in range(floors):
        w(1, 16)  # floor type 1
        partitions = r(5)
        w(partitions, 5)
        classes = []
        for _ in range(partitions):
            c = r(4)
            w(c, 4)
            classes.append(c)
        dims = []
        for _ in range(max(classes, default=-1) + 1):
            d = r(3)
            w(d, 3)
            dims.append(d + 1)
            sub = r(2)
            w(sub, 2)
            if sub:
                w(r(8), 8)
            for _ in range(1 << sub):
                w(r(8), 8)
        w(r(2), 2)
        rangebits = r(4)
        w(rangebits, 4)
        for c in classes:
            for _ in range(dims[c]):
                w(r(rangebits), rangebits)

    residues = r(6) + 1
    w(residues - 1, 6)
    for _ in range(residues):
        kind = r(2)
        if kind > 2:
            raise WemError("bad residue type")
        w(kind, 16)
        w(r(24), 24)
        w(r(24), 24)
        w(r(24), 24)
        classifications = r(6) + 1
        w(classifications - 1, 6)
        w(r(8), 8)
        cascade = []
        for _ in range(classifications):
            low = r(3)
            w(low, 3)
            flag = r(1)
            w(flag, 1)
            high = 0
            if flag:
                high = r(5)
                w(high, 5)
            cascade.append(high * 8 + low)
        for c in cascade:
            for k in range(8):
                if c & (1 << k):
                    w(r(8), 8)

    mappings = r(6) + 1
    w(mappings - 1, 6)
    for _ in range(mappings):
        w(0, 16)
        submaps = 1
        flag = r(1)
        w(flag, 1)
        if flag:
            submaps = r(4) + 1
            w(submaps - 1, 4)
        polar = r(1)
        w(polar, 1)
        if polar:
            steps = r(8) + 1
            w(steps - 1, 8)
            bits = _ilog(channels - 1)
            for _ in range(steps):
                w(r(bits), bits)
                w(r(bits), bits)
        reserved = r(2)
        if reserved:
            raise WemError("mapping reserved field set")
        w(0, 2)
        if submaps > 1:
            for _ in range(channels):
                w(r(4), 4)
        for _ in range(submaps):
            w(r(8), 8)
            w(r(8), 8)
            w(r(8), 8)

    modes = r(6) + 1
    w(modes - 1, 6)
    flags = []
    for _ in range(modes):
        flag = r(1)
        w(flag, 1)
        flags.append(bool(flag))
        w(0, 16)
        w(0, 16)
        w(r(8), 8)
    w(1, 1)  # framing
    if (r.pos + 7) // 8 != len(packet):
        raise WemError("the setup packet was not read exactly")
    return flags


_CRC = []
for _i in range(256):
    _c = _i << 24
    for _ in range(8):
        _c = ((_c << 1) ^ 0x04C11DB7) if _c & 0x80000000 else (_c << 1)
    _CRC.append(_c & 0xFFFFFFFF)


def _crc(data):
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFFFFFF) ^ _CRC[(c >> 24) ^ b]
    return c


class _Ogg:
    def __init__(self):
        self.out = bytearray()
        self.seq = 0

    def page(self, packet, granule, first=False, last=False):
        """Write `packet` on pages of its own."""
        lacing = [255] * (len(packet) // 255) + [len(packet) % 255]
        done = 0
        continued = False
        while True:
            segs = lacing[:255]
            lacing = lacing[255:]
            body = packet[done:done + sum(segs)]
            done += len(body)
            end = not lacing
            flags = (1 if continued else 0) | (2 if first else 0) | (4 if last and end else 0)
            head = struct.pack("<4sBBqIIIB", b"OggS", 0, flags, granule if end else -1, 1, self.seq, 0, len(segs))
            page = bytearray(head + bytes(segs) + body)
            struct.pack_into("<I", page, 22, _crc(page))
            self.out += page
            self.seq += 1
            first, continued = False, True
            if end:
                return


def _chunks(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WemError("not a RIFF WAVE file")
    out, i = {}, 12
    while i + 8 <= len(data):
        cid, size = data[i:i + 4], struct.unpack_from("<I", data, i + 4)[0]
        out[cid] = (i + 8, size)
        i += 8 + size + (size & 1)
    return out


def info(data):
    """(channels, sample rate, sample count) of a .wem."""
    chunks = _chunks(data)
    fo, _fs = chunks[b"fmt "]
    channels, rate = struct.unpack_from("<HI", data, fo + 2)
    vo = chunks[b"vorb"][0] if b"vorb" in chunks else fo + 0x18
    return channels, rate, struct.unpack_from("<I", data, vo)[0]


def convert(data):
    """The Ogg Vorbis file for the Wwise Vorbis file `data`."""
    chunks = _chunks(data)
    if b"fmt " not in chunks or b"data" not in chunks:
        raise WemError("no fmt or data chunk")
    fo, fs = chunks[b"fmt "]
    codec, channels, rate, avg = struct.unpack_from("<HHII", data, fo)
    if codec != 0xFFFF:
        raise WemError(f"codec 0x{codec:04X} is not Wwise Vorbis")
    if b"vorb" in chunks:
        vo, vs = chunks[b"vorb"]
    elif fs == 0x42:
        vo, vs = fo + 0x18, 0x2A
    else:
        raise WemError("no Vorbis header")
    if vs not in (0x2A, 0x32, 0x34):
        raise WemError(f"vorb header of 0x{vs:X} bytes is an older layout this reader does not take")
    samples, = struct.unpack_from("<I", data, vo)
    mod_packets = True
    if vs == 0x2A:
        signal, = struct.unpack_from("<I", data, vo + 4)
        mod_packets = signal not in (0x4A, 0x4B, 0x69, 0x70)
        setup_at, audio_at = struct.unpack_from("<II", data, vo + 0x10)
        b0, b1 = data[vo + 0x28], data[vo + 0x29]
        size_bytes = 2
    else:
        raise WemError("vorb header with granules is not supported")
    do, ds = chunks[b"data"]
    end = do + ds

    ogg = _Ogg()
    w = _Writer()
    w(1, 8)
    for c in b"vorbis":
        w(c, 8)
    w(0, 32)
    w(channels, 8)
    w(rate, 32)
    w(0, 32)
    w(avg * 8, 32)
    w(0, 32)
    w(b0, 4)
    w(b1, 4)
    w(1, 1)
    ogg.page(w.bytes(), 0, first=True)

    w = _Writer()
    w(3, 8)
    for c in b"vorbis":
        w(c, 8)
    w(len(VENDOR), 32)
    for c in VENDOR:
        w(c, 8)
    w(0, 32)
    w(1, 1)
    ogg.page(w.bytes(), 0)

    at = do + setup_at
    size, = struct.unpack_from("<H", data, at)
    w = _Writer()
    flags = _setup(data[at + size_bytes:at + size_bytes + size], channels, w)
    ogg.page(w.bytes(), 0)
    if at + size_bytes + size != do + audio_at:
        raise WemError("the first audio packet does not follow the setup packet")

    mode_bits = _ilog(len(flags) - 1)
    mask = (1 << mode_bits) - 1
    blocks = (1 << b0, 1 << b1)
    packets = []
    at = do + audio_at
    while at + size_bytes <= end:
        size, = struct.unpack_from("<H", data, at)
        body = data[at + size_bytes:at + size_bytes + size]
        if len(body) < size:
            raise WemError("audio packet cut short")
        packets.append(body)
        at += size_bytes + size
    if not packets:
        raise WemError("no audio packets")

    def mode(body):
        if not body:
            return None
        return body[0] & mask if mod_packets else (body[0] >> 1) & mask

    granule, prev = 0, None
    for i, body in enumerate(packets):
        m = mode(body)
        long_block = m is not None and flags[m]
        if mod_packets and body:
            head = _Writer()
            head(0, 1)
            head(m, mode_bits)
            if long_block:
                nxt = mode(packets[i + 1]) if i + 1 < len(packets) else None
                head(1 if prev else 0, 1)
                head(1 if nxt is not None and flags[nxt] else 0, 1)
            head(body[0] >> mode_bits, 8 - mode_bits)
            rest = int.from_bytes(body[1:], "little")
            value = head.value | (rest << head.pos)
            out = value.to_bytes((head.pos + 8 * (len(body) - 1) + 7) // 8, "little")
        else:
            out = bytes(body)
        if m is not None:
            size_now = blocks[1 if long_block else 0]
            if prev is not None:
                granule += blocks[1 if prev else 0] // 4 + size_now // 4
            prev = long_block
        last = i == len(packets) - 1
        ogg.page(out, min(granule, samples) if not last else samples, last=last)
    return bytes(ogg.out)
