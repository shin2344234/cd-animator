"""Python port of Bob Jenkins' public-domain lookup3.c hashlittle(), with the
seed constant this binary's compiled instance uses baked in (recovered from
the disassembly at RVA 0x12D6800: a=b=c = strlen(key) + 0xDEBA1DCD, i.e.
initval = 0xDEBA1DCD - 0xDEADBEEF).

This computes the OFFLINE PREDICTED value of each eErrNo* global; it has not
been checked against a live process (the rules for this task forbid running
the game), so treat these as strong, evidence-based predictions, not
verified facts.
"""
import struct

MASK = 0xFFFFFFFF


def rol(x, k):
    x &= MASK
    return ((x << k) | (x >> (32 - k))) & MASK


def mix(a, b, c):
    a = (a - c) & MASK; a ^= rol(c, 4);  c = (c + b) & MASK
    b = (b - a) & MASK; b ^= rol(a, 6);  a = (a + c) & MASK
    c = (c - b) & MASK; c ^= rol(b, 8);  b = (b + a) & MASK
    a = (a - c) & MASK; a ^= rol(c, 16); c = (c + b) & MASK
    b = (b - a) & MASK; b ^= rol(a, 19); a = (a + c) & MASK
    c = (c - b) & MASK; c ^= rol(b, 4);  b = (b + a) & MASK
    return a, b, c


def final(a, b, c):
    c ^= b; c = (c - rol(b, 14)) & MASK
    a ^= c; a = (a - rol(c, 11)) & MASK
    b ^= a; b = (b - rol(a, 25)) & MASK
    c ^= b; c = (c - rol(b, 16)) & MASK
    a ^= c; a = (a - rol(c, 4)) & MASK
    b ^= a; b = (b - rol(a, 14)) & MASK
    c ^= b; c = (c - rol(b, 24)) & MASK
    return a, b, c


SEED_CONST = (0xDEBA1DCD - 0xDEADBEEF) & MASK  # the recovered "initval"


def hashlittle(key: bytes, initval=SEED_CONST):
    length = len(key)
    a = b = c = (0xDEADBEEF + length + initval) & MASK
    k = key
    off = 0
    remaining = length
    while remaining > 12:
        a = (a + k[off] + (k[off+1] << 8) + (k[off+2] << 16) + (k[off+3] << 24)) & MASK
        b = (b + k[off+4] + (k[off+5] << 8) + (k[off+6] << 16) + (k[off+7] << 24)) & MASK
        c = (c + k[off+8] + (k[off+9] << 8) + (k[off+10] << 16) + (k[off+11] << 24)) & MASK
        a, b, c = mix(a, b, c)
        off += 12
        remaining -= 12

    tail = k[off:off+remaining] + b"\x00" * (12 - remaining)
    if remaining >= 12: c = (c + (tail[11] << 24)) & MASK
    if remaining >= 11: c = (c + (tail[10] << 16)) & MASK
    if remaining >= 10: c = (c + (tail[9] << 8)) & MASK
    if remaining >= 9:  c = (c + tail[8]) & MASK
    if remaining >= 8:  b = (b + (tail[7] << 24)) & MASK
    if remaining >= 7:  b = (b + (tail[6] << 16)) & MASK
    if remaining >= 6:  b = (b + (tail[5] << 8)) & MASK
    if remaining >= 5:  b = (b + tail[4]) & MASK
    if remaining >= 4:  a = (a + (tail[3] << 24)) & MASK
    if remaining >= 3:  a = (a + (tail[2] << 16)) & MASK
    if remaining >= 2:  a = (a + (tail[1] << 8)) & MASK
    if remaining >= 1:  a = (a + tail[0]) & MASK
    if remaining == 0:
        return c
    a, b, c = final(a, b, c)
    return c


if __name__ == "__main__":
    print("SEED_CONST (initval) = 0x%08X" % SEED_CONST)
    tests = [b"", b"a", b"hello", b"hello, world", b"The quick brown fox"]
    for t in tests:
        print("%-24r hashlittle=0x%08X" % (t, hashlittle(t)))
