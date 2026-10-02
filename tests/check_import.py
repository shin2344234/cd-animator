"""Check the importers against forward kinematics done in game space.

Run with Blender in the background:
    blender -b --factory-startup --python tests/check_import.py -- <samples folder>

For each skeleton and clip it imports through the add-on, steps through
frames, and compares every bone's posed transform with the game-space result
of local = bind @ key (rotation nlerp, position lerp between keys). The
reference math below does not use the add-on's conversion code.
Exit code 0 means every check passed.
"""

import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import anim, skeleton  # noqa: E402
from cd_animator.formats import paa, paa_codec  # noqa: E402


# ---- game-space reference, plain tuples ------------------------------------

def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def qrot(q, v):
    x, y, z, w = q
    r = qmul(qmul(q, (v[0], v[1], v[2], 0.0)), (-x, -y, -z, w))
    return r[:3]


def sample(keys, frame, quat):
    comps = ("x", "y", "z", "w") if quat else ("x", "y", "z")
    get = lambda k: [getattr(k, c) for c in comps]  # noqa: E731
    if frame <= keys[0].frame:
        v = get(keys[0])
    elif frame >= keys[-1].frame:
        v = get(keys[-1])
    else:
        for a, b in zip(keys, keys[1:]):
            if a.frame <= frame <= b.frame:
                t = (frame - a.frame) / (b.frame - a.frame)
                va, vb = get(a), get(b)
                if quat and sum(x * y for x, y in zip(va, vb)) < 0:
                    vb = [-y for y in vb]   # short way round
                v = [x * (1 - t) + y * t for x, y in zip(va, vb)]
                break
    if quat:
        # Stored keys are not exactly unit length (half floats, 8-bit LOD
        # keys), so they are normalised like any interpolated key.
        n = math.sqrt(sum(c * c for c in v)) or 1.0
        v = [c / n for c in v]
    return v


def game_fk(sk, tracks, frame, lod):
    out = []
    for b in sk.bones:
        bt = tracks.get(b.name)
        # LOD section 1 counts 1/5 s ticks, everything else 30 fps frames
        step = 6 if bt and lod and bt.section == 1 else 1
        kq, kt = (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)
        if bt and bt.rot_keys:
            kq = tuple(sample(bt.rot_keys, frame / step, True))
        if bt and bt.pos_keys:
            kt = tuple(sample(bt.pos_keys, frame / step, False))
        lq = qmul(b.quat, kq)
        lt = tuple(t + d for t, d in zip(b.trans, qrot(b.quat, kt)))
        if b.parent < 0:
            out.append((lq, lt))
        else:
            pq, pt = out[b.parent]
            out.append((qmul(pq, lq), tuple(p + d for p, d in zip(pt, qrot(pq, lt)))))
    return out


# ---- checks ------------------------------------------------------------------

def blender_game_frame(obj, bone_name):
    """A bone's posed head and its game local X and Y axis tips, in game space."""
    from cd_animator import convert
    pb = obj.pose.bones[bone_name]
    c = convert.AXIS_CORRECTION[obj.data.bones[bone_name]["cd_axis"]]
    m = pb.matrix @ c.conjugated().to_matrix().to_4x4()   # game bone frame, Blender space
    head = m.translation
    tips = [m @ convert.vec_in(v) for v in ((1, 0, 0), (0, 1, 0))]
    return [convert.vec_out(p) for p in [head] + tips]


def check_clip(context, obj, sk, clip_path, frames_to_check):
    data = open(clip_path, "rb").read()
    _c, td = paa_codec.decode_file(data)
    names = {paa_codec.bone_hash(b.name): b.name for b in sk.bones}
    tracks = {names[bt.name_hash]: bt for bt in td.bones if bt.name_hash in names}
    anim.import_clip(context, obj, clip_path)
    worst = 0.0
    worst_at = None
    for fr in frames_to_check:
        context.scene.frame_set(int(fr), subframe=fr - int(fr))
        ref = game_fk(sk, tracks, fr, td.lod)
        for i, b in enumerate(sk.bones):
            q, t = ref[i]
            want = [t] + [tuple(a + d for a, d in zip(t, qrot(q, v))) for v in ((1, 0, 0), (0, 1, 0))]
            got = blender_game_frame(obj, b.name)
            err = max(math.dist(w, g) for w, g in zip(want, got))
            if err > worst:
                worst, worst_at = err, (fr, b.name)
    return worst, worst_at


def check_quat_formula():
    from mathutils import Quaternion
    from cd_animator import convert
    worst = 0.0
    for q in [(0.1, 0.7, -0.2, 0.68), (0.5, 0.5, 0.5, 0.5), (-0.3, 0.1, 0.9, 0.3)]:
        n = math.sqrt(sum(c * c for c in q))
        q = tuple(c / n for c in q)
        r = Quaternion((q[3], q[0], q[1], q[2])).to_matrix()
        want = convert.SWAP.to_3x3() @ r @ convert.SWAP.to_3x3()
        got = convert.quat_in(q).to_matrix()
        worst = max(worst, max(abs(want[i][j] - got[i][j]) for i in range(3) for j in range(3)))
        back = convert.quat_out(convert.quat_in(q))
        worst = max(worst, max(abs(a - b) for a, b in zip(back, q)))
    return worst


def check_seating(context, folder):
    """Seated by record A, the left and right mount clips should start with
    Kliff standing on the ground and end where the idle seats him."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.import_pab(filepath=os.path.join(folder, "cd_r0032_00_broom.pab"))
    broom = context.object
    bpy.ops.cd_animator.import_pab(filepath=os.path.join(folder, "phm_01.pab"))
    kliff = context.object
    anim.seat_rider(kliff, broom)

    def show(suffix, frame):
        anim.import_clip(context, broom, os.path.join(folder, f"cd_rd_broom_basic_00_00_{suffix}.paa"))
        anim.import_clip(context, kliff, os.path.join(folder, f"cd_phm_rd_broom_basic_00_00_{suffix}.paa"))
        context.scene.frame_set(frame)
        w = kliff.matrix_world
        feet = min((w @ kliff.pose.bones[n].head).z for n in ("Bip01 L Toe0", "Bip01 R Toe0"))
        return feet, w @ kliff.pose.bones["Bip01 Pelvis"].head

    _f, seat = show("nor_std_idle_01", 0)
    failures = 0
    for side in ("l", "r"):
        feet, _p = show(f"nor_std_mount_{side}_00", 0)
        _f, end = show(f"nor_std_mount_{side}_00", 75)
        ok = -0.05 < feet < 0.15 and (end - seat).length < 0.05
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} seated mount_{side}: toes start {feet:.3f} m above ground, "
              f"ends {(end - seat).length:.3f} m from the idle seat")
    return failures


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    folder = argv[0] if argv else os.path.join(os.path.dirname(HERE), "samples", "character")
    cd_animator.register()
    context = bpy.context
    failures = 0

    e = check_quat_formula()
    print(f"quaternion swap formula: max error {e:.2e}")
    failures += e > 1e-6

    rigs = [
        ("cd_r0032_00_broom.pab", "cd_rd_broom_basic_00_00_"),
        ("phm_01.pab", "cd_phm_rd_broom_basic_00_00_"),
    ]
    for pab_name, prefix in rigs:
        pab_path = os.path.join(folder, pab_name)
        sk = paa.read_pab(open(pab_path, "rb").read())
        bpy.ops.cd_animator.import_pab(filepath=pab_path)
        obj = context.object
        if len(obj.data.bones) != len(sk.bones):
            print(f"FAIL {pab_name}: {len(obj.data.bones)} Blender bones for {len(sk.bones)} in the file")
            failures += 1
            continue
        # bind pose: no action
        anim.reset_pose(obj)
        context.view_layer.update()
        ref = game_fk(sk, {}, 0, False)
        bind_err = max(math.dist(ref[i][1], blender_game_frame(obj, b.name)[0]) for i, b in enumerate(sk.bones))
        print(f"{pab_name}: {len(sk.bones)} bones, bind pose max error {bind_err:.2e} m")
        failures += bind_err > 1e-4

        clips = sorted(f for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(".paa"))
        for clip in clips:
            path = os.path.join(folder, clip)
            _c, td = paa_codec.decode_file(open(path, "rb").read())
            last = round(td.lead.duration * anim.FPS)
            frames = {0, 1, last // 3, last // 2, (2 * last) // 3 + 1, last, 0.5, last / 2 + 0.25}
            # half frames around every sign flip, where interpolation matters
            for bt in td.bones:
                step = 6 if td.lod and bt.section == 1 else 1
                for a, b in zip(bt.rot_keys, bt.rot_keys[1:]):
                    if a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w < 0:
                        frames.add((a.frame + b.frame) * step / 2)
            frames = sorted(frames)
            worst, at = check_clip(context, obj, sk, path, frames)
            ok = worst < 1e-3
            failures += not ok
            print(f"  {'ok  ' if ok else 'FAIL'} {clip}: max error {worst:.2e} m at {at}")

    failures += check_seating(context, folder)
    print("PASS" if not failures else f"{failures} FAILURES")
    sys.stdout.flush()
    os._exit(0 if not failures else 1)


main()
