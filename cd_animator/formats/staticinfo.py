"""Read the game's data tables: its characters and items.

A table is two files in gamedata/binarystaticinfo__/bin/ (group 0008):
<table>.staticinfoheader is a u16 record count, then per record its u32 key
and u32 offset into <table>.staticinfobody. A record runs from its offset to
the next record's. Every record starts with its key again and its name, a
u32 length and that many bytes:

    01 00 00 00  05 00 00 00  4b 6c 69 66 66 00 ...      key 1, "Kliff"

The rest of a record is not decoded field by field; the add-on finds the
parts it needs by their shape and checks each against the game's files.

characterinfo (7,250 records). Each record names four files by
hashlittle(name, 0xC5EDE) side by side: the character description's base
name, the appearance's full path, an empty name, the skeleton's full path.
Kliff's are phm_description_player_kliff,
character/appearance/1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000.app_xml,
"" and character/model/1_pc/1_phm/phm_01.pab. Every record names an
appearance; several records may share one, as Kliff, Kliff_AI and
Kliff_Clone do. A record's gear is a u32 count and that many 64-byte
entries, each a u32 iteminfo key and numbers the add-on does not use:

    0a 00 00 00  42 bf 11 00 ...(60 bytes)  9b 46 0f 00 ...   10 items

A record holds several such lists, its loot among them; the gear is the
first whose items have a model of a character's own family (see packs.py).

iteminfo (6,816 records). An item's models are sets of prefabs, each a
scale (three floats, 1 1 1 so far) and a u32 count of prefab name hashes:

    00 00 80 3f  00 00 80 3f  00 00 80 3f  02 00 00 00  <sword> <scabbard>

The first set is the item as worn or held; later ones are the left-hand
version and the model dropped on the ground.
"""

import struct

EMPTY = 0xEAC5E173      # hashlittle(b"", 0xC5EDE)


def read_table(header, body):
    """[(key, record bytes)] in the header's order."""
    n = struct.unpack_from("<H", header, 0)[0]
    rows = [struct.unpack_from("<II", header, 2 + 8 * i) for i in range(n)]
    starts = sorted({o for _k, o in rows}) + [len(body)]
    end = {o: starts[i + 1] for i, o in enumerate(starts[:-1])}
    return [(k, body[o:end[o]]) for k, o in rows]


def record_name(rec):
    """The name a record starts with, such as Kliff."""
    if len(rec) < 8:
        return ""
    n = struct.unpack_from("<I", rec, 4)[0]
    return rec[8:8 + n].split(b"\0", 1)[0].decode("utf-8", "replace") if n < 256 else ""


def character_files(rec, is_appearance, is_skeleton):
    """(description hash, appearance hash, skeleton hash) of a character
    record, or None. `is_appearance(hash)` and `is_skeleton(hash)` tell the
    path hashes of appearances and skeletons, to check the place."""
    key = struct.pack("<I", EMPTY)
    at = rec.find(key, 8)
    while at >= 8:
        if at + 8 <= len(rec):
            description, app, _empty, skel = struct.unpack_from("<4I", rec, at - 8)
            if is_appearance(app) and is_skeleton(skel):
                return description, app, skel
        at = rec.find(key, at + 1)
    return None


def item_lists(rec, is_item):
    """[(offset, [item keys])]: every run in a character record that reads
    as a u32 count and that many 64-byte entries starting with an item key,
    in record order. `is_item(key)` tells an iteminfo key."""
    out = []
    for o in range(8, len(rec) - 8):
        n = struct.unpack_from("<I", rec, o)[0]
        if not 1 <= n <= 64 or o + 4 + 64 * n > len(rec):
            continue
        keys = [struct.unpack_from("<I", rec, o + 4 + 64 * i)[0] for i in range(n)]
        if all(is_item(k) for k in keys):
            out.append((o, keys))
    return out


def model_sets(rec, is_prefab):
    """[(scale, [prefab hashes])] of an item record, in record order; the
    first is the item as worn or held. `is_prefab(hash)` tells a prefab
    name hash."""
    out = []
    for o in range(8, len(rec) - 16):
        n = struct.unpack_from("<I", rec, o + 12)[0]
        if not 1 <= n <= 8 or o + 16 + 4 * n > len(rec):
            continue
        scale = struct.unpack_from("<3f", rec, o)
        if not all(0.01 < s < 100 for s in scale):
            continue
        hashes = struct.unpack_from(f"<{n}I", rec, o + 16)
        if all(is_prefab(h) for h in hashes):
            out.append((scale, list(hashes)))
    return out
