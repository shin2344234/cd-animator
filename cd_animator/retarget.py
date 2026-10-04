"""Put another rig's animation on a game skeleton.

Each mapped game bone takes the source bone's turn away from its own rest
pose, in world space, on top of the game bone's rest. A limb bone's rest is
first turned to point the way the source bone's rest points, from its joint
to the next mapped joint, the upper arm to the elbow, the thigh to the knee,
since a bone's own axis says little. So the rests may differ: a T-pose
source, as BVH and Mixamo rigs are, puts the game's arms out in a T where
the source's are, though Kliff's bind pose has them down. Bone rolls may
differ too. A hand or a foot turns as its parent's rest does, and the
pelvis, spine, neck and head keep the game's rest, as both rests stand
upright and look ahead. A source whose first frame is a T-pose,
as every frame 1 of CMU's BVH files is, takes that frame for its rest
pose, and the clip starts on the next: CMU made those T-poses for
retargeting, while the files' own rest pose splays the legs and bends the
neck forward.

The pelvis takes the source hips' travel from the first frame, scaled by
the two rigs' leg lengths, hip to knee to ankle, so an actor anywhere in a
capture area starts where the game skeleton stands. The pelvis height puts
the feet's lowest point over the clip where the game skeleton's feet rest,
on the floor, since where the hip joint sits on the leg differs between
rigs. Each ankle goes where the source's ankle is from its hips, scaled the
same, and the thigh swings to reach it with the knee bend kept: rigs set
the hip joints apart differently (CMU's 43 cm at Kliff's size, his own
23 cm), and the leg angles alone brought his feet together. Facing forward
turns the whole motion about the vertical so the hips face on the first
frame as the game skeleton's rest does, wherever the actor faced. The
fingers, which no rig here maps, hold the pose of the clip the new clip
started from on its first frame, his idle's relaxed hands for one started
from it; other bones without a source keep their bind pose under their
parent. The keys go on
the active action, every frame, so Export writes them like any other clip.

On its own the pelvis's travel only moves the body within the clip, and
the game puts him back where he started when it ends. With travel,
B_MoveControl_01 and Bip01 also take
the hips' travel over the ground. The game moves a character by
B_MoveControl_01 and draws the body from it, and its own clips move Bip01
the same distance, so he ends where the actor did.

The source bone for each game bone is the first of its candidate names the
source rig has, ignoring case and a "prefix:" such as Mixamo's "mixamorig:".
The candidates cover Mixamo, the BVH files of the CMU and Daz sets, Rigify's
deform bones and plain names.
"""

import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import anim

# Game bone: candidate source names, parent bones before their children.
HUMAN = [
    ("Bip01 Pelvis", ["Hips", "hip", "pelvis", "DEF-spine", "root"]),
    ("Bip01 Spine", ["Spine", "abdomen", "LowerBack", "DEF-spine.001", "spine"]),
    ("Bip01 Spine1", ["Spine1", "chest", "DEF-spine.002", "spine.001"]),
    ("Bip01 Spine2", ["Spine2", "Chest", "UpperChest", "DEF-spine.003", "spine.002", "spine.003"]),
    ("Bip01 Neck", ["Neck", "neck", "DEF-spine.004", "Neck1"]),
    ("Bip01 Head", ["Head", "head", "DEF-spine.006"]),
    ("Bip01 L Clavicle", ["LeftShoulder", "lCollar", "DEF-shoulder.L", "shoulder.L", "clavicle_l", "LeftCollar"]),
    ("Bip01 L UpperArm", ["LeftArm", "lShldr", "DEF-upper_arm.L", "upper_arm.L", "upperarm_l", "LeftUpArm"]),
    ("Bip01 L Forearm", ["LeftForeArm", "lForeArm", "DEF-forearm.L", "forearm.L", "lowerarm_l", "LeftLowArm"]),
    ("Bip01 L Hand", ["LeftHand", "lHand", "DEF-hand.L", "hand.L", "hand_l"]),
    ("Bip01 R Clavicle", ["RightShoulder", "rCollar", "DEF-shoulder.R", "shoulder.R", "clavicle_r", "RightCollar"]),
    ("Bip01 R UpperArm", ["RightArm", "rShldr", "DEF-upper_arm.R", "upper_arm.R", "upperarm_r", "RightUpArm"]),
    ("Bip01 R Forearm", ["RightForeArm", "rForeArm", "DEF-forearm.R", "forearm.R", "lowerarm_r", "RightLowArm"]),
    ("Bip01 R Hand", ["RightHand", "rHand", "DEF-hand.R", "hand.R", "hand_r"]),
    ("Bip01 L Thigh", ["LeftUpLeg", "lThigh", "DEF-thigh.L", "thigh.L", "thigh_l", "LeftHip"]),
    ("Bip01 L Calf", ["LeftLeg", "lShin", "DEF-shin.L", "shin.L", "calf_l", "LeftKnee", "LeftLowLeg"]),
    ("Bip01 L Foot", ["LeftFoot", "lFoot", "DEF-foot.L", "foot.L", "foot_l", "LeftAnkle"]),
    ("Bip01 L Toe0", ["LeftToeBase", "LeftToe", "DEF-toe.L", "toe.L", "ball_l"]),
    ("Bip01 R Thigh", ["RightUpLeg", "rThigh", "DEF-thigh.R", "thigh.R", "thigh_r", "RightHip"]),
    ("Bip01 R Calf", ["RightLeg", "rShin", "DEF-shin.R", "shin.R", "calf_r", "RightKnee", "RightLowLeg"]),
    ("Bip01 R Foot", ["RightFoot", "rFoot", "DEF-foot.R", "foot.R", "foot_r", "RightAnkle"]),
    ("Bip01 R Toe0", ["RightToeBase", "RightToe", "DEF-toe.R", "toe.R", "ball_r"]),
]
HIPS = "Bip01 Pelvis"
TRAVEL = ["B_MoveControl_01", "Bip01"]   # the root bones that carry travel over the ground
LEG =["Bip01 L Thigh", "Bip01 L Calf", "Bip01 L Foot"]
FEET = ["Bip01 L Foot", "Bip01 R Foot", "Bip01 L Toe0", "Bip01 R Toe0"]
# The joints a limb bone points to, the first one mapped.
NEXT = {}
for _s in "LR":
    NEXT.update({f"Bip01 {_s} Clavicle": [f"Bip01 {_s} UpperArm"], f"Bip01 {_s} UpperArm": [f"Bip01 {_s} Forearm"],
                 f"Bip01 {_s} Forearm": [f"Bip01 {_s} Hand"], f"Bip01 {_s} Thigh": [f"Bip01 {_s} Calf"],
                 f"Bip01 {_s} Calf": [f"Bip01 {_s} Foot"]})
# No foot points anywhere: rigs place the toe joint differently (CMU's sits
# level with the ankle on a flat foot, the game's well below it), and both
# rest poses stand on flat feet. Nor does the trunk: both rests stand
# upright and look ahead, and CMU's hips-to-back line leans 16 degrees
# further back than Kliff's and its neck 26 to 32, which tipped his head
# back to the sky.


class RetargetError(Exception):
    pass


def _plain(name):
    return name.rsplit(":", 1)[-1].lower()


def mapping(target, source):
    """[(game bone, source bone)] for the bones both rigs have, parents
    first; a game bone already in the list is never given twice."""
    names = {}
    for b in source.data.bones:
        names.setdefault(_plain(b.name), b.name)
    out, used = [], set()
    for game, candidates in HUMAN:
        if game not in target.pose.bones:
            continue
        for c in candidates:
            src = names.get(c.lower())
            if src and src not in used:
                out.append((game, src))
                used.add(src)
                break
    return out


def _joint(obj, bone):
    return obj.matrix_world @ obj.data.bones[bone].head_local


def _hip_height(obj, hips, bones):
    """The hips' height over the lowest of `bones`' joints, at rest."""
    return _joint(obj, hips).z - min(_joint(obj, b).z for b in bones)


def _length(obj, bones):
    """The length from joint to joint along `bones`, at rest."""
    pts = [_joint(obj, b) for b in bones]
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


def _yaw(turn):
    """How far `turn` swings a level line about the vertical, in radians."""
    v = turn @ Vector((1, 0, 0))
    return math.atan2(v.y, v.x)


def split(target, source, frames):
    """(reference frame or None, frames to key) for retarget(): a source
    whose first frame is a T-pose, both arms level and pointing apart,
    takes that frame for its rest pose and leaves it out of the clip."""
    src = dict(mapping(target, source))
    arms = [(f"Bip01 {side} UpperArm", f"Bip01 {side} Forearm") for side in "LR"]
    if len(frames) < 2 or not all(a in src and b in src for a, b in arms):
        return None, frames
    scene = bpy.context.scene
    keep = scene.frame_current
    scene.frame_set(frames.start)
    sw = source.matrix_world
    dirs = [(sw @ source.pose.bones[src[b]].head - sw @ source.pose.bones[src[a]].head).normalized() for a, b in arms]
    scene.frame_set(keep)
    if all(abs(d.z) < 0.35 for d in dirs) and dirs[0].dot(dirs[1]) < -0.85:
        return frames.start, frames[1:]
    return None, frames


def _rest_turns(target, pairs, joints):
    """{game bone: the world turn that points its rest the way the source
    bone points in its rest pose, whose joints are `joints`}, joint to next
    joint."""
    src = dict(pairs)
    turns = {}
    for game, _s in pairs:
        nxt = next((n for n in NEXT.get(game, []) if n in src), None)
        if nxt is not None:
            a = _joint(target, nxt) - _joint(target, game)
            b = joints[src[nxt]] - joints[src[game]]
            if a.length > 1e-6 and b.length > 1e-6:
                turns[game] = a.rotation_difference(b)
                continue
        p = target.data.bones[game].parent
        while p is not None and p.name not in turns:
            p = p.parent
        turns[game] = turns[p.name].copy() if p is not None else Quaternion()
    return turns


def _go(scene, f):
    """Go to scene frame `f`, between frames when it has a fraction."""
    whole = math.floor(f)
    scene.frame_set(int(whole), subframe=f - whole)


def times(frames, start=None, end=None, speed=1.0):
    """The source frames to sample: from `start` to `end`, both in `frames`
    when not given, `speed` frames of the source to each frame of the clip.
    At 0.5 the clip plays the source at half speed."""
    a = frames[0] if start is None else start
    b = frames[-1] if end is None else end
    if b <= a or speed <= 0:
        raise RetargetError(f"no frames from {a} to {b} at speed {speed}")
    return [a + i * speed for i in range(int((b - a) / speed + 1e-6) + 1)]


def retarget(target, source, action, frames, face=True, reference=None, travel=False):
    """Key `action` on armature `target` from `source`'s current animation
    at scene frames `frames`, the n-th onto frame n of the clip; a frame
    with a fraction samples between frames. Facing forward with `face`.
    The source's pose on frame `reference`, from split(), stands for its
    rest pose. With `travel` the TRAVEL bones carry the hips' travel over
    the ground. Returns the mapping used."""
    pairs = mapping(target, source)
    if not any(g == HIPS for g, _s in pairs) or len(pairs) < 10:
        raise RetargetError(f"only {len(pairs)} of the source's bones match a game bone"
                            + ("" if any(g == HIPS for g, _s in pairs) else ", and none is the hips")
                            + "; it needs the hips and most of the limbs")
    roots = TRAVEL if travel else []
    if not all(b in target.pose.bones for b in roots):
        raise RetargetError(f"the skeleton has no {' and '.join(TRAVEL)} to carry travel")
    scene = bpy.context.scene
    keep_frame = scene.frame_current
    target.animation_data.action = action
    tw, sw = target.matrix_world, source.matrix_world
    src = dict(pairs)
    # The source's rest pose, each bone's world rotation and joint: its bind pose or the reference frame's.
    if reference is None:
        rest_s = {s: (sw @ source.data.bones[s].matrix_local).to_quaternion() for _g, s in pairs}
        joints = {s: _joint(source, s) for _g, s in pairs}
    else:
        scene.frame_set(reference)
        rest_s = {s: (sw @ source.pose.bones[s].matrix).to_quaternion() for _g, s in pairs}
        joints = {s: sw @ source.pose.bones[s].head for _g, s in pairs}
    align = _rest_turns(target, pairs, joints)
    rest_t = {g: align[g] @ (tw @ target.data.bones[g].matrix_local).to_quaternion() for g, _s in pairs}
    hips_src = src[HIPS]
    rest_hips_t = _joint(target, HIPS)
    if all(g in src for g in LEG):
        scale = _length(target, LEG) / max(_length(source, [src[g] for g in LEG]), 1e-6)
    else:
        scale = (_hip_height(target, HIPS, [g for g, _s in pairs])
                 / max(_hip_height(source, hips_src, [s for _g, s in pairs]), 1e-6))
    _go(scene, frames[0])
    first = sw @ source.pose.bones[hips_src].head
    hips_turn = (sw @ source.pose.bones[hips_src].matrix).to_quaternion() @ rest_s[hips_src].inverted()
    facing = Quaternion((0, 0, 1), -_yaw(hips_turn)) if face else Quaternion()
    start = Vector((first.x, first.y, sw.translation.z))
    ground = Vector((rest_hips_t.x, rest_hips_t.y, tw.translation.z))
    feet = [g for g in FEET if g in src]
    legs = [(f"Bip01 {side} Thigh", f"Bip01 {side} Foot", f"Bip01 {side} Toe0") for side in "LR"]
    legs = [leg for leg in legs if leg[0] in src and leg[1] in src]

    # Unmapped bones hold their bind pose; mapped ones are set below.
    for pb in target.pose.bones:
        pb.rotation_mode = "QUATERNION"
    fcurves = action.fcurves if hasattr(action, "fcurves") else None
    if fcurves is not None:
        for fc in list(fcurves):
            fcurves.remove(fc)
    else:
        from bpy_extras import anim_utils
        bag = anim_utils.action_get_channelbag_for_slot(action, action.slots[0])
        for fc in list(bag.fcurves):
            bag.fcurves.remove(fc)
    for pb in target.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    if "cd_source" in action:
        for path, values in anim.first_pose(target, action["cd_source"]).items():
            bone, _, prop = path[len('pose.bones["'):].partition('"].')
            if "Finger" in bone:
                setattr(target.pose.bones[bone], prop, values)
                target.pose.bones[bone].keyframe_insert(prop, frame=0, group=bone)

    tw_inv = tw.inverted()
    rest_roots = {b: tw @ target.data.bones[b].matrix_local for b in roots}

    def pose(f, lift):
        """Pose the target as the source stands on frame f, the pelvis
        raised by `lift`. Returns the lowest foot joint's height."""
        _go(scene, f)
        if roots:
            step = facing @ (sw @ source.pose.bones[hips_src].head - start) * scale
            for b in roots:
                target.pose.bones[b].matrix = tw_inv @ Matrix.Translation((step.x, step.y, 0)) @ rest_roots[b]
            bpy.context.view_layer.update()
        turns = {}
        for game, name in pairs:
            spb = source.pose.bones[name]
            turn = facing @ (sw @ spb.matrix).to_quaternion() @ rest_s[name].inverted()
            turns[game] = turn @ rest_t[game]
            world_rot = turns[game].to_matrix().to_4x4()
            tpb = target.pose.bones[game]
            if game == HIPS:
                head = ground + facing @ (sw @ spb.head - start) * scale + Vector((0, 0, lift))
            else:
                bpy.context.view_layer.update()
                head = tw @ tpb.head
            world_rot.translation = head
            tpb.matrix = tw_inv @ world_rot
        bpy.context.view_layer.update()
        hips_t = tw @ target.pose.bones[HIPS].head
        hips_s = sw @ source.pose.bones[hips_src].head
        for thigh, foot, toe in legs:
            hip = tw @ target.pose.bones[thigh].head
            want = hips_t + facing @ (sw @ source.pose.bones[src[foot]].head - hips_s) * scale
            swing = (tw @ target.pose.bones[foot].head - hip).rotation_difference(want - hip)
            tpb = target.pose.bones[thigh]
            tpb.matrix = tw_inv @ (Matrix.Translation(hip) @ swing.to_matrix().to_4x4() @ Matrix.Translation(-hip)
                                   @ tw @ tpb.matrix)
            bpy.context.view_layer.update()
            for b in (foot, toe):   # the foot keeps the source's turn
                if b in turns:
                    m = turns[b].to_matrix().to_4x4()
                    m.translation = tw @ target.pose.bones[b].head
                    target.pose.bones[b].matrix = tw_inv @ m
                    bpy.context.view_layer.update()
        return min(((tw @ target.pose.bones[g].head).z for g in feet), default=0.0)

    # The feet's lowest point over the clip goes as low as they are at rest.
    lift = min(_joint(target, g).z for g in feet) - min(pose(f, 0.0) for f in frames) if feet else 0.0
    for n, f in enumerate(frames):
        pose(f, lift)
        for game, _s in pairs:
            tpb = target.pose.bones[game]
            tpb.keyframe_insert("rotation_quaternion", frame=n, group=game)
            if game == HIPS:
                tpb.keyframe_insert("location", frame=n, group=game)
        for b in roots:
            target.pose.bones[b].keyframe_insert("location", frame=n, group=b)
    scene.frame_set(keep_frame)
    return pairs
