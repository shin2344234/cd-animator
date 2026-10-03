"""Check characters built from their appearance files.

    blender -b --factory-startup --python tests/check_character.py -- [game folder]

Needs the game installed. It requires:

  * 300 appearance files, picked evenly through the packs, to resolve to a
    skeleton and meshes that are all in the packs;
  * Kliff (cd_phm_macduff_00000) to build with his skeleton and exactly the
    19 meshes of his default look, each one read, textured and parented;
  * Kliff's own proportions: the armature's bones at his skeleton
    variation's world bind positions, his body at rest where the game's
    skinning puts it, and with a clip playing close to the game's skinning,
    worked out separately in game space. The reference poses the bones
    without scale, a key turning a bone in its unscaled bind frame, and
    applies each bone's own variation scale to its vertices only, as the
    variation's records imply: every child carries the inverse of its
    parent's scale.
  * Damian to build on the female skeleton with every mesh read.

Exit code 0 means every check passed.
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
from cd_animator.formats import paa, paa_codec, pac, paz  # noqa: E402

PHM = "1_pc/1_phm/"
KLIFF = {
    "CD_Nude": "nude/cd_phm_00_nude_00_0001",
    "CD_Underwear": "armor/38_underwear/cd_phm_00_uw_00_0001",
    "CD_Head": "head/head/cd_phm_00_head_00_0001_macduff",
    "CD_EyeLeft": "head/head_sub/cd_phm_00_eyeleft_00_0001",
    "CD_EyeRight": "head/head_sub/cd_phm_00_eyeright_00_0001",
    "CD_Eyebrows": "head/head_sub/cd_phm_00_eyebrow_00_0002",
    "CD_Eyelashes": "head/head_sub/cd_phm_00_head_00_0001_macduff_eyelash_0001",
    "CD_Tooth": "head/head_sub/cd_phm_00_tooth_00_0001",
    "CD_Nude_Hair": "head/beard/cd_phm_00_fuzz_00_0001",
    "CD_Hair": "head/hair/cd_phm_00_hair_00_0022_player",
    "CD_Beard": "head/beard/cd_phm_00_beard_00_0005_06_player",
    "CD_Upperbody": "armor/9_upperbody/cd_phm_00_ub_00_0054",
    "CD_Lowerbody": "armor/10_lowerbody/cd_phm_00_lb_00_0054",
    "CD_Lowerbody_Acc": "armor/10_lowerbody/cd_phm_00_lb_belt_00_0001",
    "CD_Shoulder_Under": "armor/14_sho/cd_phm_00_sho_under_00_0054",
    "CD_Cloak": "armor/19_cloak/cd_phm_00_cloak_00_0054",
    "CD_Cloak_Shoulder": "armor/14_sho/cd_phm_00_sho_00_0054",
    "CD_Hand": "armor/11_hand/cd_phm_00_hand_0054",
    "CD_Foot": "armor/12_foot/cd_phm_00_foot_0054",
}


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def check_survey(idx):
    t = time.time()
    names = idx.appearances[::max(1, len(idx.appearances) // 300)][:300]
    meshes, bad = 0, []
    for name in names:
        try:
            ch = packs.character(idx, name)
            skel, parts, missing = ch.skeleton, ch.parts, ch.missing
        except (packs.PackError, ValueError, SyntaxError) as exc:
            bad.append(f"{name}: {exc}")
            continue
        absent = [m for _c, m in parts if m + ".pac" not in idx.by_path]
        if missing or absent or skel + ".pab" not in idx.by_path:
            bad.append(f"{name}: {missing or absent or skel}")
        meshes += len(parts)
    # One appearance file in the game is not well-formed XML.
    return report(len(bad) <= 1, f"{len(names)} of {len(idx.appearances)} appearances resolve, {meshes} meshes, "
                                 f"all in the packs ({time.time() - t:.1f} s){'; ' + bad[0] if bad else ''}")


def build(name):
    t = time.time()
    # The appearance alone; tests/check_gear.py checks the gear.
    res = bpy.ops.cd_animator.game_character(character=name, gear="NONE")
    arm = bpy.context.view_layer.objects.active
    return res, arm, time.time() - t


def check_kliff():
    res, arm, took = build("cd_phm_macduff_00000")
    got = {o["cd_component"]: o for o in arm.children}
    want = {c: "character/model/" + PHM + p for c, p in KLIFF.items()}
    wrong = [c for c in want if c not in got or got[c].name.split(".")[0] != want[c].rsplit("/", 1)[-1]]
    extra = [c for c in got if c not in want]
    untextured = [o.name for o in got.values()
                  if not any(m.get("cd_shader") for m in o.data.materials)]
    fails = report(res == {"FINISHED"} and arm.get("cd_game_path") == "character/model/" + PHM + "phm_01",
                   f"Kliff builds on phm_01 ({took:.1f} s)")
    fails += report(not wrong and not extra, f"{len(got)} meshes, his 19 default parts"
                                             f"{'; wrong ' + str(wrong) if wrong else ''}{'; extra ' + str(extra) if extra else ''}")
    fails += report(not untextured, f"every part has the game's materials{'; not ' + str(untextured) if untextured else ''}")
    return fails


CLIP = "1_pc/1_phm/00_riding/cd_phm_rd_broom_basic_00_00_nor_std_dismount_l_00"


def _trs(t, q, s):
    m = Quaternion((q[3], q[0], q[1], q[2])).normalized().to_matrix().to_4x4()
    return Matrix.Translation(t) @ m @ Matrix.Diagonal((s[0], s[1], s[2], 1.0))


def _sample(keys, f, n):
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


def _game_world(sk, binds, tracks, frame):
    """Each bone's world matrix in game space, from local binds and keys."""
    out = []
    for i, b in enumerate(sk.bones):
        local = binds[i]
        bt = tracks.get(paa_codec.bone_hash(b.name))
        if bt:
            f = frame / paa_codec.frame_step(bt.kind)
            local = local @ _trs(_sample(bt.pos_keys, f, 3) or (0, 0, 0), _sample(bt.rot_keys, f, 4) or (0, 0, 0, 1),
                                 _sample(bt.scale_keys, f, 3) or (1, 1, 1))
        out.append(local if b.parent < 0 else out[b.parent] @ local)
    return out


def _evaluated(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = [v.co.copy() for v in me.vertices]
    ev.to_mesh_clear()
    return co


def check_proportions(idx):
    """Kliff's skeleton variation against the game's skinning, in game space."""
    fails = 0
    res, arm, _took = build("cd_phm_macduff_00000")
    ch = packs.character(idx, "1_pc/1_phm/cd_phm_macduff/cd_phm_macduff_00000")
    var = packs.variation(idx, ch.variations)
    sk = paa.read_pab(paz.read(idx.by_path[ch.skeleton + ".pab"]))
    shared = [_trs(b.trans, b.quat, b.scale) for b in sk.bones]
    shared_world = _game_world(sk, shared, {}, 0)
    varied_world = []
    for i, b in enumerate(sk.bones):
        m = var.get(paa_codec.bone_hash(b.name))
        if m is not None:
            varied_world.append(Matrix((m[0:4], m[4:8], m[8:12], m[12:16])))
        else:
            varied_world.append(shared[i] if b.parent < 0 else varied_world[b.parent] @ shared[i])
    # Unscaled bind worlds and each bone's own scale on top of them.
    plain = []
    for w in varied_world:
        loc, rot, _size = w.decompose()
        plain.append(Matrix.Translation(loc) @ rot.to_matrix().to_4x4())
    own = [plain[i].inverted() @ varied_world[i] for i in range(len(sk.bones))]
    binds = [plain[i] if b.parent < 0 else plain[b.parent].inverted() @ plain[i]
             for i, b in enumerate(sk.bones)]

    worst = max((arm.data.bones[b.name].head_local - convert.vec_in(varied_world[i].translation)).length
                for i, b in enumerate(sk.bones) if paa_codec.bone_hash(b.name) in var)
    fails += report(res == {"FINISHED"} and len(ch.variations) == 2 and worst < 1e-5,
                    f"{len(var)} bones from {', '.join(p.rsplit('/', 1)[-1] for p in ch.variations)} "
                    f"sit at the variation's bind, worst {worst * 1000:.4f} mm; scale {arm.scale[0]:g}")

    body = next(o for o in arm.children if o.get("cd_component") == "CD_Nude")
    path = "character/model/1_pc/1_phm/nude/cd_phm_00_nude_00_0001.pac"
    m = pac.read_pac(paz.read(idx.by_path[path]), 0, {paa_codec.bone_hash(b.name) for b in sk.bones})
    bone_index = {paa_codec.bone_hash(b.name): i for i, b in enumerate(sk.bones)}
    verts = [p for sb in m.submeshes for p in sb.positions]
    skins = [s for sb in m.submeshes for s in sb.skin]
    inv = [w.inverted() for w in shared_world]

    def game_skin(pose):
        mats = {i: pose[i] @ inv[i] for i in set(bone_index[h] for h in m.palette)}
        out = []
        for p, skin in zip(verts, skins):
            acc, total = Vector((0, 0, 0)), 0.0
            for slot, w in skin:
                acc += (mats[bone_index[m.palette[slot]]] @ Vector(p)) * w
                total += w
            out.append(convert.vec_in(acc / total))
        return out

    arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    got, want = _evaluated(body), game_skin(varied_world)
    worst = max((a - b).length for a, b in zip(got, want))
    moved = max((convert.vec_in(Vector(p)) - b).length for p, b in zip(verts, want))
    fails += report(worst < 1e-4, f"body at rest where the game's skinning puts it, worst {worst * 1000:.3f} mm "
                                  f"(the variation moves vertices up to {moved * 1000:.1f} mm)")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=CLIP)
    _h, td = paa_codec.decode_file(open(arm.animation_data.action["cd_source"], "rb").read())
    tracks = {b.name_hash: b for b in td.bones}
    for f in (0, 25, 50):
        bpy.context.scene.frame_set(f)
        posed = _game_world(sk, binds, tracks, f)
        got, want = _evaluated(body), game_skin([posed[i] @ own[i] for i in range(len(posed))])
        d = sorted((a - b).length for a, b in zip(got, want))
        fails += report(d[-1] < 0.01, f"frame {f} of a dismount: within {d[-1] * 1000:.2f} mm of the game's skinning, "
                                      f"99% within {d[int(len(d) * 0.99)] * 1000:.2f} mm")
    return fails


def check_damian():
    res, arm, took = build("1_pc/2_phw/cd_phw_damian/cd_phw_damian_00000")
    return report(res == {"FINISHED"} and arm["cd_game_path"].endswith("/phw_01") and len(arm.children) == 16,
                  f"Damian builds on phw_01 with {len(arm.children)} meshes ({took:.1f} s)")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_survey(idx)
    fails += check_kliff()
    fails += check_proportions(idx)
    fails += check_damian()
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
