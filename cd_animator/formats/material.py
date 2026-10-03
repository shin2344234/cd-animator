"""Read a mesh's material file (.pac_xml).

Each mesh character/model/X.pac has a material file at
character/modelproperty/X.pac_xml, encrypted in the packs (formats.paz reads
it plain). It is XML with two top-level elements and no single root:

    <SkinnedMeshPropertyCommon .../>
    <ModelPropertyList>
      <ModelProperty Index="0"> ... one per colour variant of the mesh
        <SkinnedMeshMaterialWrapper _subMeshName="cd_phm_00_head_0001_01">
          <Material Name="_resourceMaterial" _materialName="SkinnedMeshSkin">
            <Vector Name="_permutations"> switches, such as AlphaTest
            <Vector Name="_parameters">
              <MaterialParameterTexture _name="_baseColorTexture">
                <ResourceReferencePath_ITexture _path="character/texture/....dds"/>
              <MaterialParameterFloat _name="..." _value="0.05"/>
              <MaterialParameterColor _name="..." _value="#rrggbbaa"/>
              <MaterialParameterByte4 _name="..." _value="u32 of four bytes"/>

A submesh name matches a part's name in the .pac. A parameter left at the
shader's default is not written, so a missing one means "default", which
the files do not say. Texture paths ending in nonetexture0xffffffff.dds mean
no texture.
"""

import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

NONE_TEXTURE = "nonetexture"


@dataclass
class Material:
    shader: str                                     # such as SkinnedMeshStandard
    textures: dict = field(default_factory=dict)    # parameter name: game path
    floats: dict = field(default_factory=dict)
    colors: dict = field(default_factory=dict)      # name: (r, g, b, a), 0..1, as written (sRGB)
    bytes4: dict = field(default_factory=dict)      # name: four bytes, low first
    switches: dict = field(default_factory=dict)    # permutations, such as AlphaTest: 1


def _number(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _material(elem):
    m = Material(elem.get("_materialName", ""))
    for vec in elem.findall("Vector"):
        target = vec.get("Name")
        for p in vec:
            name = p.get("_name")
            if not name:
                continue
            kind = p.tag
            value = p.get("_value")
            if target == "_permutations":
                m.switches[name] = _number(value)
            elif kind == "MaterialParameterTexture":
                ref = p.find("ResourceReferencePath_ITexture")
                path = (ref.get("_path") or "").lower() if ref is not None else ""
                if path and NONE_TEXTURE not in path:
                    m.textures[name] = path
            elif kind == "MaterialParameterFloat":
                try:
                    m.floats[name] = float(value)
                except (TypeError, ValueError):
                    pass
            elif kind == "MaterialParameterColor" and value and re.fullmatch(r"#[0-9a-fA-F]{8}", value):
                m.colors[name] = tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5, 7))
            elif kind == "MaterialParameterByte4":
                m.bytes4[name] = tuple(struct.pack("<I", _number(value) & 0xFFFFFFFF))
            else:
                m.switches.setdefault(name, _number(value))
    return m


def read_materials(data, variant=0):
    """{submesh name (lower case): Material} for colour variant `variant`,
    and the number of variants."""
    text = data.decode("utf-8-sig", "replace")
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    root = ET.fromstring("<root>" + text + "</root>")
    variants = root.findall("./ModelPropertyList/ModelProperty")
    if not variants:
        return {}, 0
    chosen = variants[min(max(variant, 0), len(variants) - 1)]
    out = {}
    for wrapper in chosen.iter("SkinnedMeshMaterialWrapper"):
        sub = (wrapper.get("_subMeshName") or "").lower()
        mat = next((m for m in wrapper.iter("Material") if m.get("Name") == "_resourceMaterial"), None)
        if sub and mat is not None:
            out[sub] = _material(mat)
    return out, len(variants)
