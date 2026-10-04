"""The game's sounds, by the names a move plays them by.

The game's sound is Wwise. Its bank info, sound/bin__/windows/
soundbanksinfo_<language>.pasound and the same under soundcommon/, names
its Wwise objects, each as a u8 length, the name, hashlittle of the name in
lower case and the object's Wwise ID, FNV-1 of the name. A chart's sound
event names a sound by the hashlittle key. Only the banks' HIRC sections
say which objects are events, so names() reads every bank once per game
version, about 7 s, and keeps the list in the add-on's cache.
"""

import json
import os
import struct

from . import packs
from .formats import paz
from .formats.hashlittle import hashlittle

INFO = ("sound/bin__/windows/soundbanksinfo_", "soundcommon/bin__/windows/soundbanksinfo_")
LANGUAGE = "english(us)"
EVENT = 4                              # a Wwise event's HIRC object type


class SoundError(Exception):
    pass


def _records(data):
    """[(name, Wwise ID)] of a bank info file."""
    out = []
    i = 0
    while i < len(data) - 9:
        n = data[i]
        name = data[i + 1:i + 1 + n]
        if n >= 3 and i + 9 + n <= len(data) and all(32 < c < 127 for c in name) \
                and struct.unpack_from("<I", data, i + 1 + n)[0] == hashlittle(name.lower(), 0xC5EDE):
            out.append((name.decode().lower(), struct.unpack_from("<I", data, i + 5 + n)[0]))
            i += 9 + n
        else:
            i += 1
    return out


def _entries(idx, ext):
    for group in sorted(os.listdir(idx.folder)):
        pamt = os.path.join(idx.folder, group, "0.pamt")
        if os.path.isfile(pamt):
            yield from paz.read_index(pamt, {ext})


def _events(idx):
    """The Wwise IDs of every bank's events."""
    out = set()
    for e in _entries(idx, "bnk"):
        d = paz.read(e)
        p = 0
        while p + 8 <= len(d):
            tag, size = d[p:p + 4], struct.unpack_from("<I", d, p + 4)[0]
            if tag == b"HIRC":
                q = p + 12
                for _ in range(struct.unpack_from("<I", d, p + 8)[0]):
                    kind, n, oid = struct.unpack_from("<BII", d, q)
                    if kind == EVENT:
                        out.add(oid)
                    q += 5 + n
                break
            p += 8 + size
    return out


def _read(idx):
    infos = {}
    for e in _entries(idx, "pasound"):
        p = e.path.lower()
        for prefix in INFO:
            if p.startswith(prefix):
                infos.setdefault(prefix, []).append(e)
    if not infos:
        raise SoundError("the game has no sound bank info")
    events = _events(idx)
    out = set()
    for entries in infos.values():
        e = next((e for e in entries if LANGUAGE in e.path.lower()), entries[0])
        out |= {name for name, wid in _records(paz.read(e)) if wid in events}
    return sorted(out)


def names(idx):
    """Every sound a move can play, sorted, read once per game version."""
    if getattr(idx, "_sounds", None) is None:
        stamp = "_".join(str(int(t)) for t in idx.stamp)
        path = os.path.join(packs.cache_root(), f"sounds_{stamp}.json")
        try:
            with open(path, encoding="utf-8") as f:
                idx._sounds = json.load(f)
        except (OSError, ValueError):
            idx._sounds = _read(idx)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(idx._sounds, f)
            except OSError:
                pass
    return idx._sounds


def find(idx, text):
    """The sound `text` names: a name from the list, or words only one
    name holds."""
    t = text.strip().lower()
    every = names(idx)
    if t in set(every):
        return t
    hits = packs.search(every, t)
    if len(hits) == 1:
        return hits[0]
    raise SoundError(f'{len(hits) or "None"} of the game\'s sounds match "{text.strip()}"; pick one from the list')
