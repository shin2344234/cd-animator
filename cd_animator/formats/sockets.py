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
socket. No file names which description a character uses, so the add-on
merges them, the character's own family first; a part listed twice, as
Kliff's spear is, takes each attribute from its first listing.
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


def read_part_sockets(data, into=None):
    """{part name: {attribute: value}} from a character description,
    added to `into` without replacing what it already holds."""
    out = {} if into is None else into
    try:
        root = _root(data)
    except ET.ParseError:
        # A few descriptions are not well formed; take the elements anyway.
        text = data.decode("utf-8-sig", "replace")
        for attrs in re.findall(r"<PartInOutSocket ([^>]*?)/?>", text):
            pairs = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
            part = pairs.pop("PartName", None)
            if part:
                held = out.setdefault(part, {})
                for k, v in pairs.items():
                    held.setdefault(k, v)
        return out
    for e in root.iter("PartInOutSocket"):
        part = e.get("PartName")
        if part:
            held = out.setdefault(part, {})
            for k, v in e.attrib.items():
                if k != "PartName":
                    held.setdefault(k, v)
    return out


def placement(part_rule, drawn):
    """(character socket, weapon child socket) for a part rule, drawn or
    put away; either may be None."""
    if not part_rule:
        return None, None
    side = "Out" if drawn else "In"
    return part_rule.get(f"{side}SocketBone"), part_rule.get(f"{side}ChildSocketBone")
