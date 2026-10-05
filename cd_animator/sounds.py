"""The game's sounds, by the names a move plays them by.

The game's sound is Wwise. Its bank info, sound/bin__/windows/
soundbanksinfo_<language>.pasound and the same under soundcommon/, names
its Wwise objects, each as a u8 length, the name, hashlittle of the name in
lower case and the object's Wwise ID, FNV-1 of the name. A chart's sound
event names a sound by the hashlittle key. Only the banks' HIRC sections
say which objects are events, so events() reads every bank once per game
version, about 7 s, and keeps each event's bank in the add-on's cache.

To play a sound in Blender, media() follows the event in its bank, bank
version 150: its first Play action, that action's target, and the first
child of each container on the way down to a sound. A child names its
parent near the start of its own record, so the children are found that
way. The sound's media is in the bank's DATA or a file named by its ID
under sound/windows/media/, its language's folder there for voices, or
soundcommon/windows/media/.
96% of the events end in Wwise Vorbis, which fetch() turns into Ogg.
"""

import json
import os
import struct

from . import packs
from .formats import paz, wwise
from .formats.hashlittle import hashlittle

INFO = ("sound/bin__/windows/soundbanksinfo_", "soundcommon/bin__/windows/soundbanksinfo_")
LANGUAGE = "english(us)"
EVENT = 4                              # a Wwise event's HIRC object type
SOUND = 2                              # a sound's, and 5, 6 and 7 are containers
PLAY = 0x0403                          # an action that plays its target
VORBIS = 0x00040001                    # the codec plug-in of Wwise Vorbis
MEDIA = ("sound/windows/media/", f"sound/windows/media/{LANGUAGE}/", "soundcommon/windows/media/")


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


def _entries(idx, *exts):
    for group in sorted(os.listdir(idx.folder)):
        pamt = os.path.join(idx.folder, group, "0.pamt")
        if os.path.isfile(pamt):
            yield from paz.read_index(pamt, set(exts))


def _events(idx):
    """{Wwise ID: bank path} of every bank's events. A voice's event is in
    one bank per language, each naming that language's media, so the
    add-on's language wins."""
    out = {}
    for e in _entries(idx, "bnk"):
        path = e.path.lower()
        d = paz.read(e)
        p = 0
        while p + 8 <= len(d):
            tag, size = d[p:p + 4], struct.unpack_from("<I", d, p + 4)[0]
            if tag == b"HIRC":
                q = p + 12
                for _ in range(struct.unpack_from("<I", d, p + 8)[0]):
                    kind, n, oid = struct.unpack_from("<BII", d, q)
                    if kind == EVENT and (oid not in out or f"/{LANGUAGE}/" in path):
                        out[oid] = path
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
    banks = _events(idx)
    out = {}
    for entries in infos.values():
        e = next((e for e in entries if LANGUAGE in e.path.lower()), entries[0])
        out.update({name: [banks[wid], wid] for name, wid in _records(paz.read(e)) if wid in banks})
    return out


def names(idx):
    """Every sound a move can play, sorted."""
    if getattr(idx, "_sound_names", None) is None:
        idx._sound_names = sorted(events(idx))
    return idx._sound_names


def events(idx):
    """{name: [bank path, Wwise ID]} of every sound a move can play, read
    once per game version."""
    if getattr(idx, "_sounds", None) is None:
        stamp = "_".join(str(int(t)) for t in idx.stamp)
        path = os.path.join(packs.cache_root(), f"sound_events_{stamp}.json")
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


def _files(idx):
    """{path: pack entry} of the game's sound banks and media files, read
    once a session, about 6 s."""
    if getattr(idx, "_sound_files", None) is None:
        idx._sound_files = {e.path.lower(): e for e in _entries(idx, "bnk", "wem")}
    return idx._sound_files


def _bank(data):
    """({ID: (type, record)} of a bank's HIRC objects, {media ID: bytes} of
    the media in its DATA)."""
    objs, media, index = {}, {}, []
    p = 0
    while p + 8 <= len(data):
        tag, size = data[p:p + 4], struct.unpack_from("<I", data, p + 4)[0]
        body = p + 8
        if tag == b"DIDX":
            index = [struct.unpack_from("<III", data, body + 12 * i) for i in range(size // 12)]
        elif tag == b"DATA":
            media = {mid: data[body + off:body + off + n] for mid, off, n in index}
        elif tag == b"HIRC":
            q = body + 4
            for _ in range(struct.unpack_from("<I", data, body)[0]):
                kind, n, oid = struct.unpack_from("<BII", data, q)
                objs[oid] = (kind, data[q + 9:q + 5 + n])
                q += 5 + n
        p += 8 + size
    return objs, media


def _parent(kind, rec):
    """The parent's ID in a sound or container record, or None for the few
    laid out otherwise. A sound's starts with 14 bytes of source, more for
    a source plug-in. Then come the effects, the metadata, the bus and the
    parent."""
    try:
        off = 0
        if kind == SOUND:
            off = 14 + (4 + struct.unpack_from("<I", rec, 14)[0] if rec[0] & 0xF == 2 else 0)
        fx = rec[off + 1]
        off += 2 + (1 + 7 * fx if fx else 0)
        off += 2 + 6 * rec[off + 1]
        return struct.unpack_from("<I", rec, off + 4)[0]
    except (struct.error, IndexError):
        return None


def media(idx, name):
    """The .wem bytes of the first sound that sound `name` plays: its
    event's first Play action's target, or that container's first child
    by ID, and so on down. The game picks among a container's children as
    it plays. Raises SoundError when that sound is not Wwise Vorbis."""
    bank, wid = events(idx)[name]
    files = _files(idx)
    objs, embedded = _bank(paz.read(files[bank]))
    rec = objs[wid][1]
    count, i = 0, 0
    while True:
        b = rec[i]
        i += 1
        count = count << 7 | b & 0x7F
        if b < 0x80:
            break
    actions = [objs.get(struct.unpack_from("<I", rec, i + 4 * k)[0]) for k in range(count)]
    play = next((r for _k, r in filter(None, actions) if struct.unpack_from("<H", r, 0)[0] == PLAY), None)
    if play is None:
        raise SoundError(f"{name} plays no sound of its own, so Blender has none to play")
    node = struct.unpack_from("<I", play, 2)[0]
    while node in objs and objs[node][0] != SOUND:
        node = min((oid for oid, (k, r) in objs.items() if k in (SOUND, 5, 6, 7) and _parent(k, r) == node),
                   default=None)
    if node not in objs:
        raise SoundError(f"{name} plays music or a sound outside its bank, which Blender cannot follow")
    plugin, stream, source = struct.unpack_from("<IBI", objs[node][1], 0)
    if plugin != VORBIS:
        raise SoundError(f"{name} is not stored as Wwise Vorbis but by plug-in {plugin:08X}, so Blender cannot play it")
    # A prefetched sound, stream type 1, keeps only its start in the bank.
    if stream == 0 and source in embedded:
        return embedded[source]
    e = next((files[p] for p in (m + f"{source}.wem" for m in MEDIA) if p in files), None)
    if e is None:
        raise SoundError(f"{name}'s media, {source}.wem, is not in the game's files")
    return paz.read(e)


def fetch(idx, name):
    """The cached .ogg of sound `name`, converted on first use."""
    path = os.path.join(packs.cache_root(), "sounds", name + ".ogg")
    if not os.path.isfile(path):
        data = wwise.convert(media(idx, name))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    return path


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
