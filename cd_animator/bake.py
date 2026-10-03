"""Bake what Blender shows into keys the game can play.

The exporter reads a bone's rotation_quaternion and location curves. A bone
moved by something else, a constraint, an IK chain, a driver or a rotation
mode other than quaternions, shows a pose in Blender those curves do not
hold. For those bones the exporter takes the pose Blender evaluates instead,
at every frame (every tick in a LOD's 8-bit blocks), in the bone's local space: the
same space as its curves, on top of the bind pose and under its parent's
evaluated pose.
"""

from . import export
from .anim import frame_step
from .formats.paa_codec import KIND_HALF

_ROT_PATHS = ("rotation_euler", "rotation_axis_angle")


def _active(c):
    return getattr(c, "enabled", not c.mute) and c.influence > 0.0


def _chain(pb, count):
    """The bone and `count - 1` parents above it; all of them for 0."""
    out = []
    while pb is not None and (count == 0 or len(out) < count):
        out.append(pb.name)
        pb = pb.parent
    return out


def bones_to_bake(obj, action):
    """{bone name: why} for every bone whose shown pose its curves do not hold."""
    why = {}
    for pb in obj.pose.bones:
        for c in pb.constraints:
            if not _active(c):
                continue
            if hasattr(c, "chain_count"):
                for name in _chain(pb, c.chain_count):
                    why.setdefault(name, f"{c.type.lower()} chain from {pb.name}")
            else:
                why.setdefault(pb.name, c.type.lower())
        if pb.rotation_mode != "QUATERNION":
            why.setdefault(pb.name, f"rotation mode {pb.rotation_mode}")
    ad = obj.animation_data
    for fc in ad.drivers if ad else ():
        if fc.data_path.startswith('pose.bones["') and not fc.mute:
            why.setdefault(fc.data_path[len('pose.bones["'):].partition('"]')[0], "driver")
    bag = export._channelbag(obj, action)
    for fc in bag.fcurves if bag else ():
        name, _, prop = fc.data_path[len('pose.bones["'):].partition('"].')
        if fc.data_path.startswith('pose.bones["') and prop in _ROT_PATHS:
            why.setdefault(name, prop.replace("_", " ") + " keys")
    bones = obj.data.bones
    return {n: w for n, w in why.items() if n in bones and "cd_index" in bones[n]}


def sample(context, obj, action, names, last, kinds):
    """{bone name: {frame: (quaternion wxyz, location xyz, scale xyz)}} for
    `names`, evaluated on frames 0 to `last`. `kinds` maps a bone to its key
    kind, for the LOD tick step. The action is shown on `obj` while sampling
    and the scene's frame, action and NLA state are put back after."""
    scene = context.scene
    ad = obj.animation_data or obj.animation_data_create()
    saved = (scene.frame_current, ad.action, ad.action_slot, ad.use_nla)
    out = {n: {} for n in names}
    try:
        if ad.action != action:
            ad.action = action
            slot = next((s for s in action.slots if s.target_id_type == "OBJECT"), None)
            if slot is not None:
                ad.action_slot = slot
        ad.use_nla = False
        for f in range(0, last + 1):
            wanted = [n for n in names if f % frame_step(kinds.get(n, KIND_HALF)) == 0]
            if not wanted:
                continue
            scene.frame_set(f)
            for n in wanted:
                pb = obj.pose.bones[n]
                m = obj.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL")
                q = m.to_quaternion()
                prev = out[n].get(max(out[n])) if out[n] else None
                if prev is not None and prev[0].dot(q) < 0.0:
                    q.negate()   # stay on one side so straight-line blending takes the short way
                out[n][f] = (q, m.to_translation(), m.to_scale())
    finally:
        frame, action0, slot0, use_nla = saved
        if ad.action != action0:
            ad.action = action0
            if action0 is not None and slot0 is not None:
                ad.action_slot = slot0
        ad.use_nla = use_nla
        scene.frame_set(frame)
    return out


def close(a, b, eps):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


def thin(frames, values, eps):
    """Drop keys that only repeat the keys on both sides of them."""
    keep = []
    for i, f in enumerate(frames):
        if 0 < i < len(frames) - 1 and close(values[i], values[i - 1], eps) and close(values[i], values[i + 1], eps):
            continue
        keep.append(f)
    return keep
