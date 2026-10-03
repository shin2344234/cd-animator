"""ChaCha20 for the game's encrypted pack files, in plain Python.

The packs encrypt the XML-derived files, such as a mesh's material file
(.pac_xml), with ChaCha20 (encryption type 3 in the index, flag bits 20 to
23). The key and nonce come from the file's lower-case name, as CrimsonForge
(github.com/hzeemr/crimsonforge, MIT) found: s = hashlittle(name, 0xC5EDE);
the 16-byte nonce is s four times, which ChaCha20 reads as a 32-bit block
counter s and a 96-bit nonce; the key is eight words s ^ 0x60616263 ^ d for
d in XOR_DELTAS. Encryption and decryption are the same operation.
"""

import struct

from .hashlittle import hashlittle

SEED = 0xC5EDE
KEY_XOR = 0x60616263
XOR_DELTAS = (0x00000000, 0x0A0A0A0A, 0x0C0C0C0C, 0x06060606,
              0x0E0E0E0E, 0x0A0A0A0A, 0x06060606, 0x02020202)
_M = 0xFFFFFFFF


def _block(state):
    x = list(state)

    def qr(a, b, c, d):
        x[a] = (x[a] + x[b]) & _M; x[d] ^= x[a]; x[d] = ((x[d] << 16) | (x[d] >> 16)) & _M
        x[c] = (x[c] + x[d]) & _M; x[b] ^= x[c]; x[b] = ((x[b] << 12) | (x[b] >> 20)) & _M
        x[a] = (x[a] + x[b]) & _M; x[d] ^= x[a]; x[d] = ((x[d] << 8) | (x[d] >> 24)) & _M
        x[c] = (x[c] + x[d]) & _M; x[b] ^= x[c]; x[b] = ((x[b] << 7) | (x[b] >> 25)) & _M

    for _ in range(10):
        qr(0, 4, 8, 12); qr(1, 5, 9, 13); qr(2, 6, 10, 14); qr(3, 7, 11, 15)
        qr(0, 5, 10, 15); qr(1, 6, 11, 12); qr(2, 7, 8, 13); qr(3, 4, 9, 14)
    return struct.pack("<16I", *((x[i] + state[i]) & _M for i in range(16)))


def chacha20(data, key, nonce16):
    """XOR `data` with the ChaCha20 stream for a 32-byte key and a 16-byte
    nonce whose first word is the starting block counter."""
    k = struct.unpack("<8I", key)
    counter, n0, n1, n2 = struct.unpack("<4I", nonce16)
    const = (0x61707865, 0x3320646E, 0x79622D32, 0x6B206574)
    out = bytearray(len(data))
    for i in range(0, len(data), 64):
        ks = _block(const + k + ((counter + i // 64) & _M, n0, n1, n2))
        chunk = data[i:i + 64]
        out[i:i + len(chunk)] = bytes(a ^ b for a, b in zip(chunk, ks))
    return bytes(out)


def key_nonce(name):
    s = hashlittle(name.lower().encode("utf-8"), SEED)
    base = s ^ KEY_XOR
    return struct.pack("<8I", *(base ^ d for d in XOR_DELTAS)), struct.pack("<I", s) * 4


def decrypt(data, name):
    """The plain bytes of a file the packs encrypt, keyed by its file name."""
    key, nonce = key_nonce(name.rsplit("/", 1)[-1])
    return chacha20(data, key, nonce)
