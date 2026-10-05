"""IK controls, to pose a game skeleton's arms and legs by their hands and feet.

add_controls() gives each arm a hand control and an elbow control, and each
leg a foot control and a knee control. They are bones of the armature in
the bone collection "CD controls", keyed to match the clip. An IK
constraint makes the limb reach its hand or foot control and bend towards
its elbow or knee control, and the hand or foot takes its control's turn.
The controls have no cd_index, so export never writes them; it bakes the
limbs as Blender shows them (bake.py).

Blender's IK puts the tail of the chain's last bone on its target, and the
game's bones are not joined end to end. Kliff's hand starts 2.3 cm short of
his forearm's tail, on the forearm's axis, and so does every hand and foot
of the 110 skeletons with Bip01 limbs but one boss's. So the IK goes on the
forearm, two bones long, and the hand control sits at the forearm's tail
with the hand's turn. The hand copies its control's whole transform, which
moves it to the forearm's tail, and then a Copy Location puts it back on
the forearm where the clip has it. A Copy Rotation would do it in one, but
it goes through Euler angles, and a foot flat on the ground is at gimbal
lock in Kliff's bone axes, where it missed by 0.8 degrees. The legs are the
same with the calf and the foot.

With a pole target Blender turns the chain about the line from its first
bone's head to the target until that bone's axis X cos(a) + Z sin(a), a
being the pole angle, points at the pole, both taken square to the line
(ConstrainPoleVector in Blender's IK solver). The pole angle is the way the
elbow or knee bends in the upper arm's or thigh's own axes, summed over the
clip, and each frame's pole goes out along that axis as the clip turns it,
so the IK shows the clip's pose on every frame it keys until a control
moves. Between keys the controls and the clip's bones blend differently,
by under a millimetre in Kliff's idle.
"""

import math

import bpy
from mathutils import Matrix

from . import export

COLLECTION = "CD controls"
IK, TURN, PLACE = "CD IK", "CD turn", "CD place"
REACH = 0.4   # how far out from the limb its elbow or knee control sits, in metres
PARTS = (("Hand", "Forearm", "UpperArm", "Elbow"), ("Foot", "Calf", "Thigh", "Knee"))


def limbs(obj):
    """[(tip, middle, root, control, pole control)] for each arm and leg of
    armature `obj`, by the game's bone names, whose tip starts on the
    middle bone's axis between its head and tail."""
    bones = obj.data.bones
    out = []
    for side in "LR":
        for tip, mid, root, pole in PARTS:
            names = [f"Bip01 {side} {n}" for n in (tip, mid, root)]
            if not all(n in bones for n in names):
                continue
            t, m = bones[names[0]], bones[names[1]]
            if t.parent == m and m.parent == bones[names[2]] and abs(t.head.x) < 1e-4 and abs(t.head.z) < 1e-4 \
                    and -m.length <= t.head.y < 1e-4:
                out.append((*names, f"Ctrl {side} {tip}", f"Ctrl {side} {pole}"))
    return out


def _keyed(fc):
    """The bone an F-curve keys, or False."""
    return fc.data_path.startswith('pose.bones["') and fc.data_path.rpartition(".")[0][12:-2]


def _sample(context, obj, fcurves, limbs_):
    """{limb: {frame: (tip turn, middle tail, middle head, root head, root
    turn)}} on every frame `fcurves` key a bone of the limb or one above it,
    with the controls' constraints off."""
    keyed = {}
    for fc in fcurves:
        keyed.setdefault(_keyed(fc), set()).update(round(p.co[0]) for p in fc.keyframe_points)
    frames = {}
    for limb in limbs_:
        frames[limb], bone = set(), obj.data.bones[limb[0]]
        while bone is not None:
            frames[limb] |= keyed.get(bone.name, set())
            bone = bone.parent
    ours = [c for pb in obj.pose.bones for c in pb.constraints if c.name in (IK, TURN, PLACE)]
    scene, now = context.scene, context.scene.frame_current
    out = {limb: {} for limb in limbs_}
    for c in ours:
        c.enabled = False
    try:
        for f in sorted(set().union(*frames.values())):
            scene.frame_set(f)
            for limb in limbs_:
                if f in frames[limb]:
                    tip, mid, root = (obj.pose.bones[n] for n in limb[:3])
                    out[limb][f] = (tip.matrix.to_quaternion(), mid.tail.copy(), mid.head.copy(), root.head.copy(),
                                    root.matrix.to_3x3().normalized())
    finally:
        for c in ours:
            c.enabled = True
        scene.frame_set(now)
    return out


def _bend(samples):
    """The pole angle: the way the middle joint bends, in the root bone's X
    and Z axes, summed over the frames."""
    x = z = 0.0
    for _turn, goal, joint, start, rturn in samples.values():
        line = (goal - start).normalized()
        out = joint - start
        out -= out.dot(line) * line
        x += out.dot(rturn.col[0])
        z += out.dot(rturn.col[2])
    return math.atan2(z, x)


def _add_bones(context, obj, limbs_, angles):
    active, mode = context.view_layer.objects.active, obj.mode
    context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        ebs = obj.data.edit_bones
        coll = obj.data.collections.get(COLLECTION) or obj.data.collections.new(COLLECTION)
        for (tip, mid, root, ctrl, pole), a in zip(limbs_, angles):
            t, m, r = ebs[tip], ebs[mid], ebs[root]
            c = ebs.new(ctrl)
            c.head, c.tail, c.roll = m.tail, m.tail + (t.tail - t.head), t.roll
            p = ebs.new(pole)
            p.head = m.head + (r.x_axis * math.cos(a) + r.z_axis * math.sin(a)) * REACH
            p.tail = p.head + (m.head - r.head).normalized() * 0.1
            for e in (c, p):
                e.use_deform = False
                e.color.palette = "THEME09"
                coll.assign(e)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.objects.active = active
        if mode != "OBJECT" and active == obj:
            bpy.ops.object.mode_set(mode=mode)


def _constrain(obj, limb, a):
    tip, mid, _root, ctrl, pole = limb
    pose = obj.pose.bones
    ik = pose[mid].constraints.new("IK")
    ik.name, ik.target, ik.subtarget, ik.chain_count = IK, obj, ctrl, 2
    ik.pole_target, ik.pole_subtarget, ik.pole_angle = obj, pole, a
    turn = pose[tip].constraints.new("COPY_TRANSFORMS")
    turn.name, turn.target, turn.subtarget = TURN, obj, ctrl
    place = pose[tip].constraints.new("COPY_LOCATION")
    place.name, place.target, place.subtarget = PLACE, obj, mid
    place.head_tail = min(1.0, 1.0 + obj.data.bones[tip].head.y / obj.data.bones[mid].length)


def add_controls(context, obj, action):
    """Give armature `obj` IK controls on each limb it has, the first time,
    and key them on `action` to match its pose on every frame it keys the
    limb or a bone above it. Returns (limbs, frames keyed)."""
    found = limbs(obj)
    if not found:
        raise ValueError(f"{obj.name} has no Bip01 arms or legs to put controls on")
    ctrls = {n for limb in found for n in limb[3:]}
    bag = export._channelbag(obj, action)
    fcurves = bag.fcurves if bag else []
    if any(_keyed(fc) in ctrls for fc in fcurves):
        raise ValueError(f"{action.name} already keys the IK controls")
    samples = _sample(context, obj, fcurves, found)
    angles = []
    for limb in found:
        ik = obj.pose.bones[limb[1]].constraints.get(IK)
        angles.append(ik.pole_angle if ik else _bend(samples[limb]))
    if any(n not in obj.data.bones for n in ctrls):
        _add_bones(context, obj, found, angles)
    pose = obj.pose.bones
    keyed = set()
    for limb, a in zip(found, angles):
        _tip, mid, _root, ctrl, pole = limb
        c, p, last = pose[ctrl], pose[pole], None
        for f, (turn, goal, joint, start, rturn) in sorted(samples[limb].items()):
            c.matrix = Matrix.Translation(goal) @ turn.to_matrix().to_4x4()
            q = c.rotation_quaternion.copy()
            if last is not None and q.dot(last) < 0.0:
                q.negate()   # the short way between keys
                c.rotation_quaternion = q
            last = q
            line = (goal - start).normalized()
            up = rturn.col[0] * math.cos(a) + rturn.col[2] * math.sin(a)
            up -= up.dot(line) * line
            at = start + (joint - start).dot(line) * line + up.normalized() * REACH
            p.matrix = Matrix.Translation(at) @ p.bone.matrix_local.to_3x3().to_4x4()
            for b in (c, p):
                b.keyframe_insert("location", frame=f, group=b.name)
            c.keyframe_insert("rotation_quaternion", frame=f, group=ctrl)
            keyed.add(f)
        if IK not in pose[mid].constraints:
            _constrain(obj, limb, a)
    context.scene.frame_set(context.scene.frame_current)
    return found, sorted(keyed)
