"""Check the game's materials and textures on imported meshes.

    blender -b --factory-startup --python tests/check_textures.py -- [game folder]

Needs the game installed. It requires:

  * ChaCha20 to give RFC 8439's test vector (section 2.4.2);
  * 200 material files, picked evenly through the packs, to decrypt and
    parse, and 200 compressed textures to unpack to their stated size;
  * Kliff's body, head, hair and an armour piece and the Wyvern to import
    with every part given a material from its material file, every texture
    that file names loaded with pixels, and the right inputs connected: a
    base colour on classic shaders, a layer mask on layered ones, a normal
    map wherever the file names one.

Exit code 0 means every check passed.
"""

import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import packs, shading  # noqa: E402
from cd_animator.formats import chacha, material, paz  # noqa: E402

PHM = "character/model/1_pc/1_phm/"
WYVERN = "character/model/2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/"
CASES = [
    (PHM + "phm_01", [PHM + "nude/cd_phm_00_nude_00_0001", PHM + "head/head/cd_phm_00_head_00_0001",
                      PHM + "head/hair/cd_phm_00_hair_00_0003_player", PHM + "armor/9_upperbody/cd_phm_00_ub_00_0187"]),
    (WYVERN + "cd_m0004_00_wyvern", [WYVERN + "cd_m0004_00_wyvern_00_0001"]),
]


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_chacha():
    key = bytes(range(32))
    nonce = bytes.fromhex("01000000" "000000000000004a00000000")
    text = (b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, "
            b"sunscreen would be it.")
    got = chacha.chacha20(text, key, nonce)
    want = bytes.fromhex("6e2e359a2568f98041ba0728dd0d6981e97e7aec1d4360c20a27afccfd9fae0b"
                         "f91b65c5524733ab8f593dabcd62b3571639d624e65152ab8f530c359f0861d8"
                         "07ca0dbf500d6a6156a38e088a22b65e52bc514d16ccf806818ce91ab7793736"
                         "5af90bbf74a35be6b40b8eedf2785e42874d")
    return report(got == want, "ChaCha20 gives RFC 8439's test vector")


def check_files(idx):
    fails = 0
    t = time.time()
    xmls = sorted(p for p in idx.by_path if p.endswith(".pac_xml"))
    bad = []
    parts = 0
    for p in xmls[::max(1, len(xmls) // 200)][:200]:
        try:
            mats, _n = material.read_materials(paz.read(idx.by_path[p]))
            parts += len(mats)
        except (ValueError, SyntaxError) as exc:
            bad.append((p, exc))
    fails += report(not bad and parts > 200, f"200 of {len(xmls)} material files decrypt and parse, {parts} parts "
                                             f"({time.time() - t:.1f} s){'; first failure ' + str(bad[0]) if bad else ''}")
    t = time.time()
    packed = sorted(p for p, e in idx.by_path.items() if p.endswith(".dds") and e.stored != e.size)
    bad = []
    for p in packed[::max(1, len(packed) // 200)][:200]:
        try:
            paz.read(idx.by_path[p])
        except ValueError as exc:
            bad.append((p, exc))
    # Three placeholder textures (skinnedmesh_box*) are uncompressed RGBA, which the packs store oddly.
    fails += report(len(bad) <= 3, f"200 of {len(packed)} compressed textures unpack to their stated size "
                                   f"({time.time() - t:.1f} s){'; ' + str(bad[0]) if bad else ''}")
    return fails


def linked(mat, name):
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    return bsdf.inputs[name].is_linked


def check_mesh(idx, rig, path):
    fails = 0
    bpy.context.view_layer.objects.active = rig
    before = set(rig.children)
    res = bpy.ops.cd_animator.game_mesh(mesh=path)
    obj = next(o for o in rig.children if o not in before)
    mats, _n = material.read_materials(packs.material_file(idx, path))
    name = path.rsplit("/", 1)[-1]
    problems = []
    images = 0
    for mat in obj.data.materials:
        game = mats.get(mat.name.split(".")[0].lower())
        if game is None or mat.get("cd_shader") != game.shader:
            problems.append(f"{mat.name} has no material from the file")
            continue
        nodes = [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"]
        for n in nodes:
            images += 1
            if not n.image or n.image.size[0] == 0:
                problems.append(f"{n.label} has no pixels")
        if shading.layered(game):
            mask = game.textures["_colorBlendingMaskTexture"].rsplit("/", 1)[-1]
            if not any(n.label == mask for n in nodes):
                problems.append(f"{mat.name}: no layer mask")
        elif "_baseColorTexture" in game.textures and not linked(mat, "Base Color"):
            problems.append(f"{mat.name}: base colour not connected")
        if "_normalTexture" in game.textures and not linked(mat, "Normal"):
            problems.append(f"{mat.name}: normal map not connected")
    fails += report(res == {"FINISHED"} and not problems,
                    f"{name}: {len(obj.data.materials)} parts, {images} texture nodes"
                    f"{'; ' + '; '.join(problems[:3]) if problems else ''}")
    return fails


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    fails = check_chacha()
    idx = packs.index()
    fails += check_files(idx)
    for skel, meshes in CASES:
        bpy.ops.cd_animator.game_skeleton(skeleton=skel)
        rig = bpy.context.object
        for path in meshes:
            fails += check_mesh(idx, rig, path)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
