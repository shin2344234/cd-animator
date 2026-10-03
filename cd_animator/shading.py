"""Blender materials from the game's material files (formats.material).

Two kinds of shader cover nearly every mesh.

The classic shaders (SkinnedMeshStandard, Cloth, Skin, Hair, Eye and others)
name a base colour texture, a normal map and a material map (_sp). The
material map's channels, read from the textures themselves: G is roughness
(it drops on polished metal); B is metallic on most shaders (it is 1 exactly
on the gold wire of a sword handle and 0 on the leather), but on skin it
lights the ears and other thin parts, so there it drives subsurface; R is
near 1 on hard surfaces and holds pore detail on skin, and is used as the
specular level. Hair, beard and fur textures are near white; the game
colours them with _hairDyeingColor, which multiplies the base colour here.
Eyes keep the iris and pupil in textures of their own, laid over the
eyeball by their alpha.

The layered shaders (names ending in _Ver2, and StaticStandard) have no
base colour texture. A mask (_colorBlendingMaskTexture) splits the part
into up to three layers by its R, G and B channels. Each layer has a tint
colour (_tintColorR, G, B) and a small tiling texture set from a shared
library (cd_texturelayer_*: colour, material map, normal), repeated
255 / b times across the UV square, where b is the first byte of
_dyeingTransformProperty0, 1 and 3 for layers R, G and B. The game's
shader is not known; here a layer's colour is its tint times its tiling
colour texture, and its roughness and metal come from the tiling material
map. Grime, scratches, dye and the detail normals are left out.

Normal maps are DirectX style, green pointing down the texture, so green is
inverted for Blender. Textures load from the add-on's cache through
`load(path, color)`, which returns a bpy image or None.
"""

SKIN = {"SkinnedMeshSkin", "SkinnedMeshSkinWrinkle"}
EYE = {"SkinnedMeshEye"}
EYE_COVER = {"SkinnedMeshEyeCover"}
LAYERS = (("R", 0), ("G", 1), ("B", 3))
GREY = (0.5, 0.5, 0.5, 1.0)


def _linear(c):
    out = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c[:3]]
    return (*out, 1.0)


def layered(m):
    return "_colorBlendingMaskTexture" in m.textures and "_baseColorTexture" not in m.textures


class _Builder:
    def __init__(self, mat, load):
        mat.use_nodes = True
        self.tree = mat.node_tree
        self.nodes = self.tree.nodes
        self.nodes.clear()
        self.load = load
        self.out = self.node("ShaderNodeOutputMaterial", 900, 0)
        self.bsdf = self.node("ShaderNodeBsdfPrincipled", 600, 0)
        self.link(self.bsdf.outputs["BSDF"], self.out.inputs["Surface"])
        self.uv = None

    def node(self, kind, x, y, label=None):
        n = self.nodes.new(kind)
        n.location = (x, y)
        if label:
            n.label = label
        return n

    def link(self, a, b):
        self.tree.links.new(a, b)

    def image(self, path, color, x, y, tiles=None):
        img = self.load(path, color) if path else None
        if img is None:
            return None
        n = self.node("ShaderNodeTexImage", x, y)
        n.image = img
        n.label = path.rsplit("/", 1)[-1]
        if tiles and tiles != 1.0:
            if self.uv is None:
                self.uv = self.node("ShaderNodeTexCoord", x - 600, y)
            mp = self.node("ShaderNodeMapping", x - 250, y, f"repeat {tiles:g}")
            mp.inputs["Scale"].default_value = (tiles, tiles, 1.0)
            self.link(self.uv.outputs["UV"], mp.inputs["Vector"])
            self.link(mp.outputs["Vector"], n.inputs["Vector"])
        return n

    def separate(self, img, x, y):
        n = self.node("ShaderNodeSeparateColor", x, y)
        self.link(img.outputs["Color"], n.inputs["Color"])
        return n

    def mix(self, a, b, fac, x, y, blend="MIX"):
        """Colour `a` and `b` (sockets or RGBA values) mixed by `fac`."""
        n = self.node("ShaderNodeMix", x, y)
        n.data_type = "RGBA"
        n.blend_type = blend
        for i, v in ((6, a), (7, b)):
            if isinstance(v, tuple):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        if isinstance(fac, float):
            n.inputs["Factor"].default_value = fac
        else:
            self.link(fac, n.inputs["Factor"])
        return n.outputs[2]

    def mix_float(self, a, b, fac, x, y):
        n = self.node("ShaderNodeMix", x, y)
        n.data_type = "FLOAT"
        for i, v in ((2, a), (3, b)):
            if isinstance(v, float):
                n.inputs[i].default_value = v
            else:
                self.link(v, n.inputs[i])
        self.link(fac, n.inputs["Factor"])
        return n.outputs[0]

    def normal(self, path, x, y):
        img = self.image(path, False, x, y)
        if img is None:
            return
        sep = self.separate(img, x + 300, y)
        inv = self.node("ShaderNodeMath", x + 480, y - 60, "DirectX to OpenGL green")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        self.link(sep.outputs["Green"], inv.inputs[1])
        comb = self.node("ShaderNodeCombineColor", x + 660, y)
        self.link(sep.outputs["Red"], comb.inputs["Red"])
        self.link(inv.outputs["Value"], comb.inputs["Green"])
        self.link(sep.outputs["Blue"], comb.inputs["Blue"])
        nm = self.node("ShaderNodeNormalMap", x + 840, y)
        self.link(comb.outputs["Color"], nm.inputs["Color"])
        self.link(nm.outputs["Normal"], self.bsdf.inputs["Normal"])


def _eye(b, m, color):
    """The eyeball's colour with the iris and pupil laid over it. Both
    textures share the eyeball's UV square; the iris texture's alpha is the
    iris disc and the pupil texture's alpha the pupil disc."""
    iris = b.image(m.textures.get("_irisDiffuseTexture"), True, -1300, 700)
    if iris is not None:
        color = b.mix(color, iris.outputs["Color"], iris.outputs["Alpha"], -400, 600)
    pupil = b.image(m.textures.get("_pupilTexture"), False, -1300, 1000)
    if pupil is not None:
        dark = _linear(m.colors.get("_pupilColor", (0.0, 0.0, 0.0, 1.0)))
        color = b.mix(color, dark, pupil.outputs["Alpha"], -200, 600)
    return color


def _classic(b, m):
    base = b.image(m.textures.get("_baseColorTexture"), True, -900, 400)
    if base is not None:
        color = base.outputs["Color"]
        dye = m.colors.get("_hairDyeingColor")
        if dye is not None:
            color = b.mix(color, _linear(dye), 1.0, -600, 400, "MULTIPLY")
        if m.shader in EYE:
            color = _eye(b, m, color)
        b.link(color, b.bsdf.inputs["Base Color"])
    alpha_tex = b.image(m.textures.get("_alphaTexture"), False, -900, 700)
    if alpha_tex is not None:
        b.link(alpha_tex.outputs["Color"], b.bsdf.inputs["Alpha"])
    elif base is not None and m.switches.get("AlphaTest"):
        b.link(base.outputs["Alpha"], b.bsdf.inputs["Alpha"])
    elif m.shader in EYE_COVER:
        # The clear film over the eyes; Kliff's names only a normal map.
        b.bsdf.inputs["Alpha"].default_value = 0.0
    sp = b.image(m.textures.get("_materialTexture"), False, -900, 50)
    if sp is not None:
        sep = b.separate(sp, -600, 50)
        b.link(sep.outputs["Green"], b.bsdf.inputs["Roughness"])
        spec = b.node("ShaderNodeMath", -400, -50, "specular level")
        spec.operation = "MULTIPLY"
        spec.inputs[1].default_value = 0.5
        b.link(sep.outputs["Red"], spec.inputs[0])
        b.link(spec.outputs["Value"], b.bsdf.inputs["Specular IOR Level"])
        if m.shader in SKIN:
            b.link(sep.outputs["Blue"], b.bsdf.inputs["Subsurface Weight"])
            b.bsdf.inputs["Subsurface Scale"].default_value = 0.01
        elif m.shader not in EYE:
            b.link(sep.outputs["Blue"], b.bsdf.inputs["Metallic"])


def _layered(b, m):
    mask_img = b.image(m.textures.get("_colorBlendingMaskTexture"), False, -1500, 900)
    if mask_img is None:
        return
    mask = b.separate(mask_img, -1200, 900)
    color, rough, metal = GREY, 0.5, 0.0
    y = 500
    for ch, prop in LAYERS:
        tint = m.colors.get("_tintColor" + ch)
        repeat = m.bytes4.get(f"_dyeingTransformProperty{prop}", (255,))[0]
        tiles = round(255 / repeat, 3) if repeat else 1.0
        diff = b.image(m.textures.get("_detailDiffuseMask" + ch), True, -1500, y, tiles)
        spm = b.image(m.textures.get("_detailMaterialMask" + ch), False, -1500, y - 300, tiles)
        if tint is None and diff is None:
            y -= 700
            continue
        layer = _linear(tint) if tint else (1.0, 1.0, 1.0, 1.0)
        if diff is not None:
            layer = b.mix(diff.outputs["Color"], layer, 1.0, -1000, y, "MULTIPLY")
        fac = mask.outputs["Red" if ch == "R" else "Green" if ch == "G" else "Blue"]
        color = b.mix(color, layer, fac, -700, y)
        if spm is not None:
            sep = b.separate(spm, -1000, y - 300)
            rough = b.mix_float(rough, sep.outputs["Green"], fac, -700, y - 250)
            metal = b.mix_float(metal, sep.outputs["Blue"], fac, -700, y - 400)
        y -= 700
    if isinstance(color, tuple):
        b.bsdf.inputs["Base Color"].default_value = color
    else:
        b.link(color, b.bsdf.inputs["Base Color"])
    if not isinstance(rough, float):
        b.link(rough, b.bsdf.inputs["Roughness"])
        b.link(metal, b.bsdf.inputs["Metallic"])


def setup(mat, m, load):
    """Fill Blender material `mat` from game material `m`."""
    b = _Builder(mat, load)
    if layered(m):
        _layered(b, m)
    else:
        _classic(b, m)
    b.normal(m.textures.get("_normalTexture"), -900, -400)
    mat["cd_shader"] = m.shader
