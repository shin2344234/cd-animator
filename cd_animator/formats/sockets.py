"""Read sockets: the named points where weapons and props attach.

A skeleton's sockets are in
character/descriptors/socketbonedata/<skeleton path>.pab.sockets.xml, such
as .../1_pc/1_phm/phm_01.pab.sockets.xml with 52 for every man:

    <Socket Name="RHand_Socket" Parent="Bip_Weapon_R"
            Rotation="0 0 0 1" Translation="0 0 0"/>

A socket is a parent bone and a transform in that bone's frame, rotation as
x y z w, game space. A weapon has a socket file of its own, named in its
prefab, whose sockets hang from the weapon's own bones (formats/pac.py); a
parent of "" is the weapon's origin. These "child sockets" are the points
of the weapon that meet the character's socket: Basic_ChildSocket is the
grip of a sword, Pelvis_L_ChildSocket where it sits in the scabbard.

Which socket a part goes to is in the character descriptions,
character/descriptors/characterdescription/*.xml, named by creature type
(phm_description_player_kliff.xml, animal_wolf.xml, mon_wyvern.xml):

    <PartInOutSocket PartName="CD_MainWeapon_Sword_R"
        InSocketBone="Pelvis_L_Socket" OutSocketBone="RHand_Socket"
        InChildSocketBone="Pelvis_L_ChildSocket"
        OutChildSocketBone="Basic_ChildSocket"/>

PartName is a prefab component's name. "Out" is drawn, in use; "In" is put
away. The weapon goes where its child socket lands on the character's
socket. A character's record in the data tables names its description
(formats/staticinfo.py); the add-on reads that one first and the rest
after it, the character's own family first, so that a part the record's
file leaves out still finds a rule. The first file to define a part gives
its whole rule; a part listed twice in one file, as Kliff's spear is,
takes each attribute from its first listing.

After the SocketList a skeleton's socket file groups some sockets for
stacking over clothes:

    <StackEquipInfo Count="5" EquipTypeName="Back"
        InnerPartNames="CD_Cloak CD_Upperbody"
        OriginBoneName="Bip_Weapon_Attach_In_02" Axis="z" ...>
        <Socket Name="Spine2_B_Shield_Socket"/> ...

Equipment at those sockets moves out along the origin bone's axis, in the
bone's own game frame, by as much as the inner parts stand out there.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class Socket:
    name: str
    parent: str          # bone name, "" for the origin
    rotation: tuple      # x, y, z, w
    translation: tuple


def _floats(text, n, default):
    try:
        v = tuple(float(x) for x in (text or "").split())
    except ValueError:
        return default
    return v if len(v) == n else default


def _root(data):
    text = data.decode("utf-8-sig", "replace")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    # Description files close some elements with a bare "</>".
    text = text.replace("</>", "")
    return ET.fromstring("<root>" + text + "</root>")


def read_sockets(data):
    """{socket name: Socket} from a .sockets.xml file."""
    # Read element by element: 12 of the 505 socket files in the game are
    # not well-formed XML as a whole.
    # Only the SocketList defines sockets; StackEquipInfo after it names
    # some again, with no transform, for equipment stacked on the back.
    out = {}
    text = data.decode("utf-8-sig", "replace")
    lists = re.findall(r"<SocketList\b.*?</SocketList>", text, re.S)
    for attrs in re.findall(r"<Socket\s([^>]*?)/?>", "".join(lists) if lists else text):
        e = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
        name = e.get("Name")
        if name and name not in out:
            out[name] = Socket(name, e.get("Parent") or "",
                               _floats(e.get("Rotation"), 4, (0.0, 0.0, 0.0, 1.0)),
                               _floats(e.get("Translation"), 3, (0.0, 0.0, 0.0)))
    return out


@dataclass
class Stack:
    name: str            # EquipTypeName, such as Back
    inner: tuple         # component names of the clothes under it
    origin: str          # bone the sockets move out from
    axis: tuple          # unit vector in the origin bone's game frame
    sockets: tuple       # socket names


_AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def read_stacks(data):
    """[Stack] from a skeleton's .sockets.xml file."""
    out = []
    text = data.decode("utf-8-sig", "replace")
    for head, body in re.findall(r"<StackEquipInfo\s([^>]*)>(.*?)</StackEquipInfo>", text, re.S):
        e = dict(re.findall(r'(\w+)="([^"]*)"', head))
        axis = e.get("Axis", "").strip().lower()
        sign = -1.0 if axis.startswith("-") else 1.0
        unit = _AXES.get(axis.lstrip("+-"))
        names = tuple(re.findall(r'<Socket\s[^>]*?Name="([^"]+)"', body))
        if unit and e.get("OriginBoneName") and names:
            out.append(Stack(e.get("EquipTypeName", ""), tuple(e.get("InnerPartNames", "").split()),
                             e["OriginBoneName"], tuple(sign * x for x in unit), names))
    return out


def read_part_sockets(data, into=None):
    """{part name: {attribute: value}} from a character description, added
    to `into`. A part `into` already holds is left as it is: the first file
    to define a part decides all of its rule, so that a player file's
    Visible="Out" does not reach an NPC's shield. Within one file a part
    listed twice takes each attribute from its first listing."""
    out = {} if into is None else into
    found = {}
    try:
        elements = [dict(e.attrib) for e in _root(data).iter("PartInOutSocket")]
    except ET.ParseError:
        # A few descriptions are not well formed; take the elements anyway.
        text = data.decode("utf-8-sig", "replace")
        elements = [dict(re.findall(r'(\w+)="([^"]*)"', attrs))
                    for attrs in re.findall(r"<PartInOutSocket ([^>]*?)/?>", text)]
    for pairs in elements:
        part = pairs.pop("PartName", None)
        if part:
            held = found.setdefault(part, {})
            for k, v in pairs.items():
                held.setdefault(k, v)
    for part, rule in found.items():
        out.setdefault(part, rule)
    return out


def placement(part_rule, drawn):
    """(character socket, weapon child socket) for a part rule, drawn or
    put away; either may be None."""
    if not part_rule:
        return None, None
    side = "Out" if drawn else "In"
    return part_rule.get(f"{side}SocketBone"), part_rule.get(f"{side}ChildSocketBone")
