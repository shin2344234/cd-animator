"""Make Broomy's takeoff with Kliff pushing off the ground.

    blender -b --factory-startup --python examples/push_off.py -- [out folder]

Seated on the broom idle, Kliff's hips are 1.45 m up and his toes hang 0.65
to 0.78 m above the ground, out of reach of his legs. So the takeoff dips
the broom under him first. Two clips are made together so their timing
matches:

The broom's takeoff starts from the level takeoff (examples/level_takeoff.py:
every bone on the idle's frame 0, the climb's rise and drift on Bip01).
Bip01's rise and B_MoveControl_01, which move the broom in game, now wait
RISE_DELAY frames,
and B_Body_00, which shows and carries Kliff, sinks DIP m by frame 6, sits
there to frame 9 and springs back as the rise begins.

Kliff's push-off is a new clip holding his broom idle's first frame for 36
frames, with IK legs. The ground's place in his space is worked out from
the broom's clip frame by frame (B_Rider_01, his seat, carries the dip, the
rise and the forward drift), so the balls of his feet land at frame 6, stay
planted while the broom sits low, and leave the ground at frame 10 as it
springs up. His legs are close to straight by then, which is what limits
the contact to four frames. The
script corrects the IK targets until the feet sit CLEARANCE m above the
ground on the contact frames and prints each foot's clearance per frame.

Writes cd_rd_broom_basic_00_00_nor_std_takeoff_00 (the broom; Broomy plays
it for the Wyvern's takeoff) and, for Kliff, the clip of FDA30B13, the spare
action of his that the Broomy test build plays at takeoff. Each with its
_lod.paa and .paa_metabin, into out/push_off.
"""

import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cd_animator  # noqa: E402
from cd_animator import anim, clip, export  # noqa: E402

S = os.path.join(ROOT, "samples", "character")
BROOM_IDLE = "cd_rd_broom_basic_00_00_nor_std_idle_01"
CLIMB = "cd_rd_broom_basic_00_00_nor_move_walkfast_f_75u_ing_00"
BROOM_NAME = "cd_rd_broom_basic_00_00_nor_std_takeoff_00"
KLIFF_IDLE = "cd_phm_rd_broom_basic_00_00_nor_std_idle_01"
KLIFF_NAME = "cd_phm_rd_wyvern_basic_00_00_air_move_fall_walk_end_00"
KEEP = ("B_TL_Position_01", "B_TL_Position_02")

KICK_FRAMES = 36
RISE_DELAY = 9          # Bip01 holds still this long, then rises as the climb does
DIP = 0.42              # how far B_Body_00 sinks, metres
# B_Body_00's drop by frame: ease down, sit, spring back as the rise starts.
BODY = [(0, 0.0), (3, 0.14), (5, 0.38), (6, DIP), (9, DIP), (11, 0.24), (13, 0.0)]
CONTACT = range(6, 10)  # frames the feet are on the ground; the broom springs up from 9
CLEARANCE = 0.03        # ball of the foot above the ground (the shoe sole)
BACK = 0.10             # feet land this far behind where they hang
# Foot pitch (toes down) and spine lean (forward) in degrees, by frame.
FOOT = [(0, 0), (3, -8), (6, 25), (9, 35), (11, 50), (16, 35), (26, 0), (KICK_FRAMES, 0)]
LEAN = [(0, 0), (3, 3), (6, 10), (10, 6), (16, -3), (26, 0), (KICK_FRAMES, 0)]
SIDES = ("L", "R")
UP = Vector((0.0, 0.0, 1.0))
LATERAL = Vector((1.0, 0.0, 0.0))


def at(table, frame):
    """Linear lookup in a (frame, value) table."""
    for (f0, v0), (f1, v1) in zip(table, table[1:]):
        if f0 <= frame <= f1:
            return v0 + (v1 - v0) * (frame - f0) / (f1 - f0)
    return table[-1][1]


def update(frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


def build_broom(broom):
    idle = anim.import_clip(bpy.context, broom, os.path.join(S, BROOM_IDLE + ".paa"))[0]
    climb = anim.import_clip(bpy.context, broom, os.path.join(S, CLIMB + ".paa"))[0]
    last = round(climb["cd_duration"] * anim.FPS)
    broom.animation_data.action = idle
    update(0)
    rest = {pb.name: pb.matrix_basis.copy() for pb in broom.pose.bones}
    broom.animation_data.action = climb
    rise, move = [], []
    for f in range(last + 1):
        update(f)
        rise.append(broom.pose.bones["Bip01"].matrix_basis.translation.copy())
        move.append(broom.pose.bones["B_MoveControl_01"].matrix_basis.copy())

    bag = export._channelbag(broom, climb)
    body = broom.pose.bones["B_Body_00"]
    for pb in broom.pose.bones:
        prefix = f'pose.bones["{pb.name}"]'
        if pb.name == "B_MoveControl_01":
            # The game moves the broom by this bone as well as by Bip01, so
            # it waits the same RISE_DELAY frames. Left on the climb's own
            # timing it ran up to 0.8 m ahead of Bip01, and the broom popped
            # up to it as flight began.
            for fc in [c for c in bag.fcurves if c.data_path.startswith(prefix)]:
                bag.fcurves.remove(fc)
            for f in range(last + 1):
                loc, rot, _s = move[max(0, f - RISE_DELAY)].decompose()
                pb.location, pb.rotation_quaternion = loc, rot
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)
            continue
        if pb.name in KEEP:
            continue
        for fc in [c for c in bag.fcurves if c.data_path.startswith(prefix)]:
            bag.fcurves.remove(fc)
        loc0, rot0, _s = rest[pb.name].decompose()
        if pb.name == "Bip01":
            keys = range(last + 1)
        elif pb.name == "B_Body_00":
            keys = sorted({f for f, _d in BODY} | {last})
        else:
            keys = (0, last)
        for f in keys:
            pb.rotation_quaternion = rot0
            if pb.name == "Bip01":
                pb.location = loc0 + (rise[max(0, f - RISE_DELAY)] - rise[0])
            else:
                pb.location = loc0
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_quaternion", frame=f)

    # B_Body_00 sinks straight down in the broom's space; Bip01 does not
    # turn in this clip, so one conversion to the bone's local axes holds.
    update(0)
    down_local = body.matrix.to_3x3() @ body.matrix_basis.to_3x3().inverted()
    down_local = down_local.inverted() @ -UP
    loc0 = rest["B_Body_00"].to_translation()
    fcs = [fc for fc in bag.fcurves if fc.data_path == 'pose.bones["B_Body_00"].location']
    for fc in fcs:
        for p in fc.keyframe_points:
            p.co[1] = loc0[fc.array_index] + down_local[fc.array_index] * at(BODY, p.co[0])
        fc.update()
    for fc in bag.fcurves:
        # B_Body_00 eases; every other bone's keys are straight lines
        if not fc.data_path.startswith('pose.bones["B_Body_00"]'):
            for p in fc.keyframe_points:
                p.interpolation = "LINEAR"
    climb.name = BROOM_NAME
    return climb


def seat_track(broom, action, frames):
    """Where Kliff's seat, B_Rider_01, has moved to at each frame."""
    broom.animation_data.action = action
    out = {}
    seat = broom.pose.bones["B_Rider_01"]
    for f in frames:
        update(f)
        out[f] = (broom.matrix_world @ seat.matrix).translation.copy()
    return {f: p - out[0] for f, p in out.items()}


def local_axis(pb, world_axis):
    m = pb.matrix.to_3x3() @ pb.matrix_basis.to_3x3().inverted()
    return (m.inverted() @ world_axis).normalized()


def sign_for(pb, base, axis, probe, want):
    """+1 or -1: the turn about `axis` that moves `probe(pb)` along `want`."""
    before = probe(pb)
    pb.rotation_quaternion = Quaternion(axis, math.radians(10)) @ base
    bpy.context.view_layer.update()
    after = probe(pb)
    pb.rotation_quaternion = base
    bpy.context.view_layer.update()
    return 1 if (after - before).dot(want) > 0 else -1


def ball(kliff, side):
    """The ball of the foot: the lower end of the toe bone, in world space."""
    t = kliff.pose.bones[f"Bip01 {side} Toe0"]
    w = kliff.matrix_world
    return min(w @ t.head, w @ t.tail, key=lambda v: v.z)


def build_kliff(kliff, seat):
    action = clip.new_clip(bpy.context, kliff, os.path.join(S, KLIFF_IDLE + ".paa"), KLIFF_NAME, KICK_FRAMES, hold=True)
    update(0)
    pose = kliff.pose.bones
    w = kliff.matrix_world
    feet = {s: pose[f"Bip01 {s} Foot"] for s in SIDES}
    spine = pose["Bip01 Spine"]
    head = pose["Bip01 Head"]
    turn = {}
    for pb in list(feet.values()) + [spine]:
        turn[pb.name] = (local_axis(pb, LATERAL), pb.rotation_quaternion.copy())
    toe_tip = lambda pb: w @ (pb.matrix @ Vector((0.0, pb.length, 0.0)))  # noqa: E731
    sgn = {pb.name: sign_for(pb, turn[pb.name][1], turn[pb.name][0], toe_tip, Vector((0, 1, 0)))
           for pb in feet.values()}
    sgn[spine.name] = sign_for(spine, turn[spine.name][1], turn[spine.name][0],
                               lambda _pb: w @ head.head, Vector((0, -1, 0)))

    for f in sorted({f for f, _v in FOOT} | {f for f, _v in LEAN}):
        for pb in list(feet.values()) + [spine]:
            axis, base = turn[pb.name]
            deg = at(LEAN if pb is spine else FOOT, f)
            pb.rotation_quaternion = Quaternion(axis, math.radians(deg * sgn[pb.name])) @ base
            pb.keyframe_insert("rotation_quaternion", frame=f)

    targets = {}
    for s in SIDES:
        calf = pose[f"Bip01 {s} Calf"]
        update(0)
        ankle0 = w @ calf.tail
        planted = ball(kliff, s) + Vector((0.0, BACK, 0.0))
        planted.z = CLEARANCE
        t = bpy.data.objects.new(f"foot target {s}", None)
        bpy.context.scene.collection.objects.link(t)
        plan = [(0, ankle0), (3, ankle0 + Vector((0.0, -0.03, 0.05)))]
        plan += [(f, None) for f in CONTACT]
        plan += [(16, ankle0 + Vector((0.0, 0.10, -0.12))), (26, ankle0), (KICK_FRAMES, ankle0)]
        for f, p in plan:
            t.location = p if p is not None else ankle0
            t.keyframe_insert("location", frame=f)
        ik = calf.constraints.new("IK")
        ik.target, ik.chain_count = t, 2
        targets[s] = (t, planted)

    # Walk each contact frame's target until the ball of the foot sits on the
    # planted spot, which in Kliff's space moves opposite to his seat.
    for f in CONTACT:
        worst = 0.0
        for _round in range(8):
            update(f)
            worst = 0.0
            for s, (t, planted) in targets.items():
                want = planted - seat[f]
                err = want - ball(kliff, s)
                worst = max(worst, err.length)
                t.location = t.location + err
                t.keyframe_insert("location", frame=f)
            if worst < 0.001:
                break
        print(f"  frame {f}: feet within {worst * 1000:.1f} mm of the planted spot")
    return action


def clearance(kliff, seat, frames):
    rows = []
    for f in frames:
        update(f)
        rows.append((f, *[ball(kliff, s).z + seat[f].z for s in SIDES]))
    return rows


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.join(ROOT, "out", "push_off")
    os.makedirs(out, exist_ok=True)
    cd_animator.register()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for h in list(bpy.app.handlers.frame_change_pre):
        bpy.app.handlers.frame_change_pre.remove(h)

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "cd_r0032_00_broom.pab"))
    broom = bpy.context.object
    takeoff = build_broom(broom)
    seat = seat_track(broom, takeoff, range(KICK_FRAMES + 1))

    bpy.ops.cd_animator.import_pab(filepath=os.path.join(S, "phm_01.pab"))
    kliff = bpy.context.object
    anim.import_clip(bpy.context, kliff, os.path.join(S, KLIFF_IDLE + ".paa"))
    broom.animation_data.action = bpy.data.actions[BROOM_IDLE]
    anim.seat_rider(kliff, broom)
    broom.animation_data.action = takeoff
    kick = build_kliff(kliff, seat)

    print("  frame, ball of the left and right foot above the ground (m)")
    for f, l, r in clearance(kliff, seat, range(0, 21)):
        print(f"  {f:3d} {l:6.3f} {r:6.3f}")

    for obj, action, name in ((broom, takeoff, BROOM_NAME), (kliff, kick, KLIFF_NAME)):
        written, problems = export.export_with_companions(obj, action, os.path.join(out, name + ".paa"))
        for p in written:
            print("wrote", os.path.relpath(p, ROOT))
        for p in problems:
            print("  note:", p)
    sys.stdout.flush()
    os._exit(0)


main()
