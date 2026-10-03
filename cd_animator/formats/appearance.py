"""Read a character's appearance: which meshes make up its look.

An appearance file (character/appearance/.../X.app_xml, encrypted in the
packs) lists prefabs by name in sections:

    <Appearance>
      <Nude><Prefab Name="cd_phm_00_nude_01_0002_macduff" CharacterScale="1.02571"/></Nude>
      <Head><Prefab Name="cd_phm_00_head_00_0001_macduff" HeadScale="0.92"/></Head>
      <Hair> ... </Hair>
      <Armor><Prefab Name="cd_phm_00_ub_inner_0054"/> ... </Armor>

Kliff's own appearance is cd_phm_macduff_00000; the macduff files carry his
voice (vce_pc_kliff) and use meshparam_example_kliff.xml.

A prefab (character/bin__/prefab/.../NAME.prefab) is a binary scene object
with one component per part. Each component has a name, such as
CD_Upperbody, and the game path of its mesh. The file is a reflection
dump whose field layout this module does not parse; it takes each
component's name and mesh path, which are stored as plain strings, the
name ending in the bytes 01 01 00 01 03, the path after a u32 length. Every appearance in the game
resolves this way: 5,667 files, 43,369 meshes, all present in the packs.

Parts go on in file order, and a later component with the same name
replaces an earlier one, which is how the appearance's outfit (marked
Preview) covers the plain inner layers listed before it.

The body prefab's data file (character/prefab/.../NAME.prefabdata_xml)
names the skeleton, such as 1_pc/1_phm/phm_01.pab, and a skeleton
variation (.pabc) with the character's own proportions, which the add-on
does not read.
"""

import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

# Components that show only in some states: the flight cloak, the line to a
# hyperspace plug, bags for docking.
HIDDEN = ("flight", "for_dock", "hyperspaceplug")

_COMPONENT = re.compile(rb"([A-Za-z][\w]{1,60})\x01\x01\x00\x01\x03")
_MESH = re.compile(rb"character/model/")
_SOCKET_FILE = re.compile(rb"character/descriptors/socketbonedata/")


@dataclass
class Appearance:
    prefabs: list = field(default_factory=list)   # (section, prefab name, attributes)

    @property
    def nude(self):
        return next((p[1] for p in self.prefabs if p[0] == "Nude"), None)


def read_appearance(data):
    text = data.decode("utf-8-sig", "replace")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    root = ET.fromstring("<root>" + text + "</root>")
    app = Appearance()
    top = root.find("Appearance")
    if top is None:
        return app
    for section in top:
        for p in section.iter("Prefab"):
            name = p.get("Name")
            if name:
                app.prefabs.append((section.tag, name, dict(p.attrib)))
    return app


def prefab_parts(data):
    """[(component name, mesh game path)] of a prefab, in file order."""
    names = [(m.end(), m.group(1).decode()) for m in _COMPONENT.finditer(data)]
    out = []
    for m in _MESH.finditer(data):
        start = m.start()
        if start < 4:
            continue
        size = struct.unpack_from("<I", data, start - 4)[0]
        path = data[start:start + size]
        if not path.endswith(b".pac"):
            continue
        owner = [n for end, n in names if end <= start]
        out.append((owner[-1] if owner else "", path.decode("utf-8", "replace")))
    return out


def prefab_sockets(data):
    """{component name: socket file game path} of a prefab: the socket
    file a weapon's component names after its mesh (formats/sockets.py)."""
    names = [(m.end(), m.group(1).decode()) for m in _COMPONENT.finditer(data)]
    out = {}
    for m in _SOCKET_FILE.finditer(data):
        start = m.start()
        if start < 4:
            continue
        size = struct.unpack_from("<I", data, start - 4)[0]
        path = data[start:start + size]
        if not path.endswith(b".sockets.xml"):
            continue
        owner = [n for end, n in names if end <= start]
        if owner:
            out.setdefault(owner[-1], path.decode("utf-8", "replace").lower())
    return out


def skeleton_of(prefabdata):
    """The skeleton path a prefab's data file names, such as
    1_pc/1_phm/phm_01.pab, or None."""
    m = re.search(r'<SkeletonName FileName="([^"]+)"', prefabdata.decode("utf-8-sig", "replace"))
    return m.group(1) if m else None


def variation_of(prefabdata):
    """The skeleton variation path a prefab's data file names, such as
    1_pc/1_phm/nude/cd_phm_00_nude_01_0002.pabc, or None."""
    m = re.search(r'<SkeletonVariationName FileName="([^"]+)"', prefabdata.decode("utf-8-sig", "replace"))
    return m.group(1) if m else None


def character_scale(app):
    """The body prefab's CharacterScale, 1.0 when it has none."""
    for section, _name, attributes in app.prefabs:
        if section == "Nude":
            try:
                return float(attributes.get("CharacterScale", 1.0))
            except ValueError:
                return 1.0
    return 1.0


def hidden(component):
    c = component.lower()
    return any(h in c for h in HIDDEN)


def assemble(app, parts_of):
    """The meshes of appearance `app`: [(component, mesh path)], later
    components replacing earlier ones of the same name. `parts_of(name)`
    gives a prefab's parts, or None when the prefab is missing. Returns
    (meshes, hidden components skipped, missing prefab names)."""
    slots = {}
    skipped, missing = [], []
    for _section, name, _attributes in app.prefabs:
        parts = parts_of(name)
        if parts is None:
            missing.append(name)
            continue
        for comp, mesh in parts:
            if hidden(comp):
                skipped.append(comp)
                continue
            slots.pop(comp, None)
            slots[comp] = mesh
    return list(slots.items()), skipped, missing
