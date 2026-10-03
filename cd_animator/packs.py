"""The game's own files, read from its packs instead of from unpacked copies.

The game folder comes from the add-on's preferences, or from Steam's library
list when that is empty. The index of groups 0008 (the data tables of
characters and items), 0009 (clips, skeletons, meshes, their materials and
textures, characters' appearances and prefabs, blends) and 0010 (clip
metadata, action charts) is read once per session, about 3 seconds. Files taken from the packs are written to a cache in Blender's
user folder: a clip, its LOD and its metadata side by side, so the importer
and exporter find them as they would unpacked copies, and the cached clip
stays the template its action is written against.
"""

import os
import re
from dataclasses import dataclass

import bpy

from .formats import paz

GROUPS = {"0008": {"staticinfoheader", "staticinfobody"},
          "0009": {"paa", "pab", "pabc", "pac", "pac_xml", "dds", "app_xml", "prefab", "prefabdata_xml",
                   "motionblending", "xml"},
          "0010": {"paa_metabin", "paac"}}
MOTION = "character/motion/"
MOTION_LOD = "character/motion/motion_lod__/"
ANIMMETA = "actionchart/bin__/animmeta/"
MODEL = "character/model/"
MODEL_PROPERTY = "character/modelproperty/"
APPEARANCE = "character/appearance/"
PREFAB = "character/bin__/prefab/"
VARIATION = "character/binary/skeletonvariation/"
SOCKETS = "character/descriptors/socketbonedata/"
DESCRIPTIONS = "character/descriptors/characterdescription/"
TABLES = "gamedata/binarystaticinfo__/bin/"
GAME = "Crimson Desert"


class PackError(Exception):
    pass


def _steam_libraries():
    roots = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            roots.append(winreg.QueryValueEx(k, "SteamPath")[0])
    except (ImportError, OSError):
        pass
    roots += [r"C:\Program Files (x86)\Steam", os.path.expanduser("~/.steam/steam")]
    found = []
    for root in roots:
        found.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, encoding="utf-8", errors="replace") as f:
                found += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
        except OSError:
            pass
    return found


def find_game():
    """The game folder from Steam's libraries, or None."""
    for lib in _steam_libraries():
        folder = os.path.join(lib, "steamapps", "common", GAME)
        if os.path.isfile(os.path.join(folder, "0009", "0.pamt")):
            return folder
    return None


def game_folder(context=None):
    prefs = None
    try:
        prefs = (context or bpy.context).preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        pass
    folder = getattr(prefs, "game_folder", "") if prefs else ""
    folder = bpy.path.abspath(folder) if folder else find_game()
    if not folder or not os.path.isfile(os.path.join(folder, "0009", "0.pamt")):
        raise PackError("Crimson Desert's folder was not found; set it in the add-on's preferences")
    return folder


class Index:
    def __init__(self, folder):
        self.folder = folder
        self.by_path = {}
        for group, keep in GROUPS.items():
            for e in paz.read_index(os.path.join(folder, group, "0.pamt"), keep):
                self.by_path[e.path.lower()] = e
        # Clips by their path under character/motion/, without .paa; LODs left out.
        self.clips = sorted(p[len(MOTION):-4] for p in self.by_path
                            if p.startswith(MOTION) and not p.startswith(MOTION_LOD) and p.endswith(".paa"))
        self.skeletons = sorted(p[:-4] for p in self.by_path if p.endswith(".pab"))
        self.meshes = sorted(p[:-4] for p in self.by_path if p.endswith(".pac"))
        # Characters by their path under character/appearance/, without .app_xml.
        self.appearances = sorted(p[len(APPEARANCE):-8] for p in self.by_path
                                  if p.startswith(APPEARANCE) and p.endswith(".app_xml"))
        # Prefabs and their data files by name; a few names repeat, and the first is kept.
        self.prefabs, self.prefab_data = {}, {}
        for p in sorted(self.by_path):
            if p.startswith(PREFAB) and p.endswith(".prefab"):
                self.prefabs.setdefault(p.rsplit("/", 1)[-1][:-7], p)
            elif p.endswith(".prefabdata_xml"):
                self.prefab_data.setdefault(p.rsplit("/", 1)[-1][:-15], p)
        self._bone_hashes = None
        self._clips_by_folder = {}
        self._sockets = {}
        self._part_rules = {}
        self._tables = {}
        self._gear = {}
        self.stamp = _stamp(folder)

    def table(self, name):
        """{key: record bytes} of data table `name`, such as iteminfo, in
        the header's order (formats/staticinfo.py)."""
        if name not in self._tables:
            from .formats import staticinfo
            head = self.by_path.get(TABLES + name + ".staticinfoheader")
            body = self.by_path.get(TABLES + name + ".staticinfobody")
            if head is None or body is None:
                raise PackError(f"no {name} table in the game")
            self._tables[name] = dict(staticinfo.read_table(paz.read(head), paz.read(body)))
        return self._tables[name]

    def bone_hashes(self):
        """Every bone name hash of every skeleton in the game, read once."""
        if self._bone_hashes is None:
            from .formats import paa, paa_codec
            out = set()
            for name in self.skeletons:
                for b in paa.read_pab(paz.read(self.by_path[name + ".pab"])).bones:
                    out.add(paa_codec.bone_hash(b.name))
            self._bone_hashes = out
        return self._bone_hashes


def _stamp(folder):
    return tuple(os.path.getmtime(os.path.join(folder, g, "0.pamt")) for g in GROUPS)


_index = None


def index(context=None):
    """The index for the current game folder, read on first use and again
    after a game update changes it."""
    global _index
    folder = game_folder(context)
    if _index is None or _index.folder != folder or _index.stamp != _stamp(folder):
        _index = Index(folder)
    return _index


def loaded():
    return _index is not None


def clips_for(idx, skeleton):
    """The clips in skeleton `skeleton`'s own folder (its game path without
    .pab), such as 1_pc/1_phm/ for Kliff's phm_01, or every clip when that
    folder has none: 124 of the game's 273 skeletons have no clips of their
    own folder, and some none at all."""
    folder = skeleton[len(MODEL):].rsplit("/", 1)[0] + "/" if skeleton and skeleton.startswith(MODEL) else ""
    if folder not in idx._clips_by_folder:
        found = [c for c in idx.clips if c.startswith(folder)] if folder else []
        idx._clips_by_folder[folder] = found or idx.clips
    return idx._clips_by_folder[folder]


def search(names, text, limit=300):
    """Names holding every word of `text`, at most `limit`."""
    words = text.lower().replace("\\", "/").split()
    out = []
    for n in names:
        if all(w in n for w in words):
            out.append(n)
            if len(out) >= limit:
                break
    return out


def resolve(names, text, kind, prefix="", ext=""):
    """One name from `names` for what the user typed: the name itself, its
    game path (`prefix` + name + `ext`, as the loader's log prints it), or a
    unique ending such as the file name alone."""
    t = text.strip().lower().replace("\\", "/")
    if prefix and t.startswith(prefix):
        t = t[len(prefix):]
    if ext and t.endswith(ext):
        t = t[:-len(ext)]
    if not t:
        raise PackError(f"no {kind} named")
    lookup = set(names)
    if t in lookup:
        return t
    hits = [n for n in names if n == t or n.endswith("/" + t)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise PackError(f"no {kind} in the game is called {text.strip()}")
    raise PackError(f"{len(hits)} {kind}s end in {text.strip()}; pick one with its folder, such as {hits[0]}")


def cache_root():
    try:
        return bpy.utils.extension_path_user(__package__, path="game", create=True)
    except (ValueError, AttributeError, KeyError):
        return bpy.utils.user_resource("DATAFILES", path=os.path.join("cd_animator", "game"), create=True)


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return path
    except OSError:
        pass
    with open(path, "wb") as f:
        f.write(data)
    return path


def fetch_clip(idx, name):
    """Unpack clip `name` (a path under character/motion/, no extension) with
    its LOD and metadata into the cache; the clip's local path."""
    e = idx.by_path.get(MOTION + name + ".paa")
    if e is None:
        raise PackError(f"no clip {name} in the game")
    folder = os.path.join(cache_root(), "clips", *os.path.dirname(name).split("/"))
    stem = os.path.join(folder, os.path.basename(name))
    path = _write(stem + ".paa", paz.read(e))
    lod = idx.by_path.get(MOTION_LOD + name + "_lod.paa")
    if lod is not None:
        _write(stem + "_lod.paa", paz.read(lod))
    mb = idx.by_path.get(ANIMMETA + name + ".paa_metabin")
    if mb is not None:
        _write(stem + ".paa_metabin", paz.read(mb))
    return path


def fetch_mesh(idx, name):
    """Unpack mesh `name` (its game path without .pac) into the cache; its
    local path."""
    e = idx.by_path.get(name + ".pac")
    if e is None:
        raise PackError(f"no mesh {name} in the game")
    return _write(os.path.join(cache_root(), "meshes", *name.split("/")) + ".pac", paz.read(e))


def find_mesh(idx, file_name):
    """The game path of the mesh whose file is called `file_name`, or None
    when no mesh or more than one has that name."""
    stem = os.path.splitext(os.path.basename(file_name))[0].lower()
    hits = [n for n in idx.meshes if n.rsplit("/", 1)[-1] == stem]
    return hits[0] if len(hits) == 1 else None


def material_file(idx, name):
    """The bytes of mesh `name`'s material file (.pac_xml), or None."""
    if not name.startswith(MODEL):
        return None
    e = idx.by_path.get(MODEL_PROPERTY + name[len(MODEL):] + ".pac_xml")
    return paz.read(e) if e is not None else None


def fetch_texture(idx, path):
    """Unpack texture `path` (its game path, with .dds) into the cache; its
    local path, or None when the packs do not have it."""
    e = idx.by_path.get(path.lower())
    if e is None:
        return None
    local = os.path.join(cache_root(), "textures", *path.lower().split("/"))
    if os.path.isfile(local) and os.path.getsize(local) == e.size:
        return local
    return _write(local, paz.read(e))


@dataclass
class Character:
    skeleton: str        # game path without .pab
    parts: list          # [(component, mesh game path without .pac)]
    skipped: list        # components shown only in some states
    missing: list        # prefabs the packs lack
    variations: list     # skeleton variation game paths, body first
    scale: float         # the body's CharacterScale
    socket_files: dict   # component: its prefab's socket file, for weapons


def character(idx, name):
    """Character appearance `name` (its path under character/appearance/,
    without .app_xml) resolved to its skeleton, meshes and skeleton
    variations."""
    from .formats import appearance
    e = idx.by_path.get(APPEARANCE + name + ".app_xml")
    if e is None:
        raise PackError(f"no character {name} in the game")
    app = appearance.read_appearance(paz.read(e))

    def parts_of(prefab):
        path = idx.prefabs.get(prefab.lower())
        return appearance.prefab_parts(paz.read(idx.by_path[path])) if path else None

    meshes, skipped, missing = appearance.assemble(app, parts_of)
    skel = None
    data = idx.prefab_data.get((app.nude or "").lower())
    if data:
        skel = appearance.skeleton_of(paz.read(idx.by_path[data]))
    if not skel:
        raise PackError(f"{name} names no skeleton for its body")
    skel = (MODEL + skel.lower()).rsplit(".", 1)[0]
    if skel + ".pab" not in idx.by_path:
        raise PackError(f"{name}'s skeleton {skel} is not in the game")

    # Each prefab's data file may name a skeleton variation: the body's for
    # the body, the head's for the face. Later ones win where they overlap.
    variations = []
    socket_files = {}
    for _section, prefab, _attributes in app.prefabs:
        path = idx.prefabs.get(prefab.lower())
        if path:
            socket_files.update(appearance.prefab_sockets(paz.read(idx.by_path[path])))
        data = idx.prefab_data.get(prefab.lower())
        found = appearance.variation_of(paz.read(idx.by_path[data])) if data else None
        path = VARIATION + found.lower() if found else None
        if path and path in idx.by_path and path not in variations:
            variations.append(path)
    return Character(skel, [(c, m.lower()[:-4]) for c, m in meshes], skipped, missing,
                     variations, appearance.character_scale(app), socket_files)


def prefab(idx, name):
    """A prefab's parts: [(component, mesh game path without .pac, socket
    file game path or None)]."""
    from .formats import appearance
    path = idx.prefabs.get(name.lower())
    if path is None:
        raise PackError(f"no prefab {name} in the game")
    data = paz.read(idx.by_path[path])
    files = appearance.prefab_sockets(data)
    return [(c, m.lower()[:-4], files.get(c)) for c, m in appearance.prefab_parts(data)]


@dataclass
class Gear:
    record: str          # the character record's name, such as Kliff
    description: str     # the character description it names, or None
    items: list          # [(item name, [prefab name])], in the record's order


def _name_hash(name):
    from .formats.hashlittle import hashlittle
    return hashlittle(name.lower().encode("utf-8"), 0xC5EDE)


def gear(idx, name):
    """The gear of character appearance `name` (as for character()): the
    first character record in the table that names the appearance, and the
    prefabs of its items as worn or held. None when no record names it or
    the record has no gear."""
    if name in idx._gear:
        return idx._gear[name]
    from .formats import staticinfo
    chars, items = idx.table("characterinfo"), idx.table("iteminfo")
    if "prefab" not in idx._tables:
        idx._tables["prefab"] = {_name_hash(n): n for n in idx.prefabs}
        idx._tables["description"] = {_name_hash(p.rsplit("/", 1)[-1][:-4]): p.rsplit("/", 1)[-1][:-4]
                                      for p in idx.by_path if p.startswith(DESCRIPTIONS) and p.endswith(".xml")}
        apps = {_name_hash(APPEARANCE + a + ".app_xml") for a in idx.appearances}
        idx._tables["skeleton_of"] = {_name_hash(n + ".pab"): n for n in idx.skeletons}
        skels = idx._tables["skeleton_of"]
        # The first record naming an appearance is its character: Kliff
        # before Kliff_AI and Kliff_Clone.
        first = {}
        for rec in chars.values():
            files = staticinfo.character_files(rec, apps.__contains__, skels.__contains__)
            if files:
                first.setdefault(files[1], (rec, files[0], files[2]))
        idx._tables["record"] = first
    prefab_of = idx._tables["prefab"]
    found = idx._tables["record"].get(_name_hash(APPEARANCE + name + ".app_xml"))
    out = None
    if found:
        rec, description, skeleton_hash = found

        def worn(key):
            sets = staticinfo.model_sets(items[key], prefab_of.__contains__)
            return [prefab_of[h] for h in sets[0][1]] if sets else []

        # A record lists its loot the same way; the gear is the first list
        # with a model made for the character's family, cd_phm_... for a
        # man, and not only props (cd_t...) or another creature's things.
        skeleton = idx._tables["skeleton_of"][skeleton_hash]
        family = "cd_" + skeleton.rsplit("/", 1)[-1].split("_", 1)[0] + "_"
        for _offset, keys in staticinfo.item_lists(rec, items.__contains__):
            models = [(staticinfo.record_name(items[k]), worn(k)) for k in keys]
            if any(p.startswith(family) for _n, ps in models for p in ps):
                out = Gear(staticinfo.record_name(rec), idx._tables["description"].get(description), models)
                break
    idx._gear[name] = out
    return out


def sockets(idx, path):
    """{name: formats.sockets.Socket} of a socket file (its game path), or
    of skeleton `path` (game path without .pab); empty when there is none."""
    from .formats import sockets as sockets_format
    if not path.endswith(".sockets.xml"):
        path = SOCKETS + path[len(MODEL):] + ".pab.sockets.xml" if path.startswith(MODEL) else ""
    if path not in idx._sockets:
        e = idx.by_path.get(path)
        idx._sockets[path] = sockets_format.read_sockets(paz.read(e)) if e is not None else {}
    return idx._sockets[path]


def stacks(idx, skeleton):
    """[formats.sockets.Stack] of skeleton `skeleton` (game path without
    .pab); empty when it has no socket file."""
    from .formats import sockets as sockets_format
    e = idx.by_path.get(SOCKETS + skeleton[len(MODEL):] + ".pab.sockets.xml") if skeleton.startswith(MODEL) else None
    return sockets_format.read_stacks(paz.read(e)) if e is not None else []


def part_rules(idx, skeleton, playable=False, description=None):
    """{part name: its socket rule}, merged from every character
    description: `description` first when the character's record names one
    (gear()), then those of the skeleton's family (phm for phm_01), and
    within them the player files first for a playable character and last
    for anyone else."""
    from .formats import sockets as sockets_format
    family = skeleton.rsplit("/", 1)[-1].split("_", 1)[0]
    key = (family, playable, (description or "").lower())
    if key not in idx._part_rules:
        files = sorted(p for p in idx.by_path if p.startswith(DESCRIPTIONS) and p.endswith(".xml"))

        def order(p):
            base = p.rsplit("/", 1)[-1]
            own = base.startswith(family + "_")
            player = "player" in base
            return (base[:-4] != key[2], not own, player != playable, base)

        rules = {}
        for p in sorted(files, key=order):
            sockets_format.read_part_sockets(paz.read(idx.by_path[p]), rules)
        idx._part_rules[key] = rules
    return idx._part_rules[key]


def variation(idx, paths):
    """The merged skeleton variation of game paths `paths`, later ones
    winning: {bone hash: world bind matrix, 16 floats, game space}."""
    from .formats import pabc
    out = {}
    for path in paths:
        out.update(pabc.read_variation(paz.read(idx.by_path[path])))
    return out


def fetch_skeleton(idx, name):
    """Unpack skeleton `name` (its game path without .pab) into the cache."""
    e = idx.by_path.get(name + ".pab")
    if e is None:
        raise PackError(f"no skeleton {name} in the game")
    return _write(os.path.join(cache_root(), "skeletons", os.path.basename(name) + ".pab"), paz.read(e))
