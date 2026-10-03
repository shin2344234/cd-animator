"""Check meshes from the game's packs, skinned to their armatures.

    blender -b --factory-startup --python tests/check_mesh.py -- [game folder] [--all]

Needs the game installed. For Kliff's body and the Wyvern it imports the
skeleton and the mesh from the packs and requires:

  * every palette bone to be in the skeleton, every vertex weighted to
    something, and the triangles to face the way the stored normals do;
  * the mesh not to move at the rest pose;
  * with a clip playing, every vertex Blender deforms to sit where linear
    blend skinning puts it, done separately in game space: the weighted sum
    of each bone's posed world matrix times its inverse bind matrix, applied
    to the vertex as the file stores it.

With --all it also reads every mesh in the game and requires the reader to
accept all but two (a sack flail object whose palette is not found, and one
spare). That takes hours in
Blender, whose LZ4 decoder is plain Python. Exit code 0 means every check
passed.
"""

import os
import sys
import time

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import convert, packs  # noqa: E402
from cd_animator.formats import pac, paa, paa_codec, paz  # noqa: E402

SW = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
CASES = [
    ("character/model/1_pc/1_phm/phm_01", "character/model/1_pc/1_phm/nude/cd_phm_00_nude_00_0001",
     "1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_dismount_l_00", (0, 25, 50)),
    ("character/model/2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/cd_m0004_00_wyvern",
     "character/model/2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/cd_m0004_00_wyvern_00_0001",
     "2_mon/cd_m0004_00_dragon/cd_m0004_00_wyvern/00_mon/cd_rd_wyvern_basic_00_00_air_std_idle_00", (0, 30, 60)),
]


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def samp(keys, f, n):
    if not keys:
        return None
    if f <= keys[0].frame:
        return [getattr(keys[0], c) for c in "xyzw"[:n]]
    if f >= keys[-1].frame:
        return [getattr(keys[-1], c) for c in "xyzw"[:n]]
    for a, b in zip(keys, keys[1:]):
        if a.frame <= f <= b.frame:
            t = (f - a.frame) / (b.frame - a.frame)
            va = [getattr(a, c) for c in "xyzw"[:n]]
            vb = [getattr(b, c) for c in "xyzw"[:n]]
            if n == 4 and sum(x * y for x, y in zip(va, vb)) < 0:
                vb = [-x for x in vb]
            return [x * (1 - t) + y * t for x, y in zip(va, vb)]


def trs(t, q, s):
    m = Quaternion((q[3], q[0], q[1], q[2])).normalized().to_matrix().to_4x4()
    return Matrix.Translation(t) @ m @ Matrix.Diagonal((s[0], s[1], s[2], 1.0))


def game_world(sk, tracks, frame):
    """Each bone's world matrix in game space; bind pose when tracks is empty."""
    out = []
    for b in sk.bones:
        local = trs(b.trans, b.quat, b.scale)
        bt = tracks.get(paa_codec.bone_hash(b.name))
        if bt:
            f = frame / paa_codec.frame_step(bt.kind)
            local = local @ trs(samp(bt.pos_keys, f, 3) or (0, 0, 0), samp(bt.rot_keys, f, 4) or (0, 0, 0, 1),
                                samp(bt.scale_keys, f, 3) or (1, 1, 1))
        out.append(local if b.parent < 0 else out[b.parent] @ local)
    return out


def evaluated(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    co = [v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return co


def check_case(idx, skel, mesh_path, clip, frames):
    fails = 0
    print(os.path.basename(mesh_path))
    bpy.ops.cd_animator.game_skeleton(skeleton=skel)
    rig = bpy.context.object
    t = time.time()
    # The mesh as the file has it; cloth would split off its free parts (cloth.py).
    res = bpy.ops.cd_animator.game_mesh(mesh=mesh_path, cloth=False)
    obj = next(o for o in rig.children if o.type == "MESH")
    data = paz.read(idx.by_path[mesh_path + ".pac"])
    sk = paa.read_pab(paz.read(idx.by_path[skel + ".pab"]))
    names = {paa_codec.bone_hash(b.name) for b in sk.bones}
    m = pac.read_pac(data, 0, names)
    nv = sum(len(sb.positions) for sb in m.submeshes)
    fails += report(res == {"FINISHED"} and len(obj.data.vertices) == nv and all(h in names for h in m.palette),
                    f"{nv} vertices in {len(m.submeshes)} parts, all {len(m.palette)} palette bones in the skeleton "
                    f"({time.time() - t:.1f} s)")
    unweighted = sum(1 for v in obj.data.vertices if not v.groups)
    fails += report(unweighted == 0, f"every vertex is weighted, {unweighted} are not")

    # The triangles face the way the stored normals do.
    me = obj.data
    me.calc_loop_triangles()
    stored = [convert.vec_in(n) for sb in m.submeshes for n in sb.normals]
    agree = sum(1 for p in me.polygons if p.normal.dot(sum((stored[v] for v in p.vertices), stored[0] * 0)) > 0)
    fails += report(agree >= 0.98 * len(me.polygons), f"{agree / len(me.polygons):.1%} of triangles face like their normals")

    rig.animation_data_clear()
    rest = evaluated(obj)
    raw = [convert.vec_in(p) for sb in m.submeshes for p in sb.positions]
    worst = max((a - b).length for a, b in zip(rest, raw))
    fails += report(worst < 1e-5, f"rest pose leaves the mesh where the file puts it, worst {worst * 1000:.4f} mm")

    bpy.ops.cd_animator.game_clip(clip=clip)
    _h, td = paa_codec.decode_file(open(rig.animation_data.action["cd_source"], "rb").read())
    tracks = {b.name_hash: b for b in td.bones}
    bind = game_world(sk, {}, 0)
    inv = [mtx.inverted() for mtx in bind]
    bone_index = {paa_codec.bone_hash(b.name): i for i, b in enumerate(sk.bones)}
    verts = [p for sb in m.submeshes for p in sb.positions]
    skins = [s for sb in m.submeshes for s in sb.skin]
    for f in frames:
        bpy.context.scene.frame_set(f)
        got = evaluated(obj)
        pose = game_world(sk, tracks, f)
        skinmats = {i: pose[i] @ inv[i] for i in set(bone_index[h] for h in m.palette)}
        worst, at = 0.0, None
        for vi, (p, skin) in enumerate(zip(verts, skins)):
            acc = None
            total = 0.0
            for slot, w in skin:
                mtx = skinmats[bone_index[m.palette[slot]]]
                q = mtx @ Vector(p)
                acc = q * w if acc is None else acc + q * w
                total += w
            want = convert.vec_in(acc / total)
            d = (got[vi] - want).length
            if d > worst:
                worst, at = d, vi
        fails += report(worst < 1e-3, f"frame {f}: skinned as the game skins it, worst {worst * 1000:.3f} mm (vertex {at})")
    return fails


def check_all(idx):
    t = time.time()
    hashes = idx.bone_hashes()
    bad = []
    for name in idx.meshes:
        try:
            pac.read_pac(paz.read(idx.by_path[name + ".pac"]), 0, hashes)
        except ValueError as exc:
            bad.append((name, str(exc)))
    for name, why in bad[:5]:
        print("    ", name, why)
    return report(len(bad) <= 2, f"{len(idx.meshes)} meshes: {len(idx.meshes) - len(bad)} read, "
                                 f"{len(bad)} failures ({time.time() - t:.0f} s)")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    folder = next((a for a in argv if not a.startswith("--")), None)
    cd_animator.register()
    for h in list(bpy.app.handlers.frame_change_pre):
        bpy.app.handlers.frame_change_pre.remove(h)
    if folder:
        packs.game_folder = lambda context=None: folder
    idx = packs.index()
    fails = 0
    for case in CASES:
        fails += check_case(idx, *case)
    if "--all" in argv:
        fails += check_all(idx)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
