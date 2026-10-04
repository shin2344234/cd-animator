"""Put another rig's animation on a game skeleton.

Each mapped game bone takes the source bone's turn away from its own rest
pose, in world space, on top of the game bone's rest: rest orientations and
bone rolls may differ, but a source arm raised 90 degrees raises the game
arm 90 degrees. The pelvis also takes the source hips' travel, scaled by the
two rigs' hip heights. Bones without a source keep their bind pose under
their parent. The keys go on the active action, every frame, so Export
writes them like any other clip.

The source bone for each game bone is the first of its candidate names the
source rig has, ignoring case and a "prefix:" such as Mixamo's "mixamorig:".
The candidates cover Mixamo, the BVH files of the CMU and Daz sets, Rigify's
deform bones and plain names.
"""

import bpy

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


def _hip_height(obj, bone):
    return (obj.matrix_world @ obj.data.bones[bone].head_local).z


def retarget(target, source, action, frames):
    """Key `action` on armature `target` from `source`'s current animation
    over scene frames `frames` (a range), frame f of the source onto frame
    f - frames.start of the clip. Returns the mapping used."""
    pairs = mapping(target, source)
    if not any(g == HIPS for g, _s in pairs) or len(pairs) < 10:
        raise RetargetError(f"only {len(pairs)} of the source's bones match a game bone"
                            + ("" if any(g == HIPS for g, _s in pairs) else ", and none is the hips")
                            + "; it needs the hips and most of the limbs")
    scene = bpy.context.scene
    keep_frame = scene.frame_current
    target.animation_data.action = action
    tw, sw = target.matrix_world, source.matrix_world
    # Each bone's world rest rotation on both rigs, and the hips at rest.
    rest_t = {g: (tw @ target.data.bones[g].matrix_local).to_quaternion() for g, _s in pairs}
    rest_s = {s: (sw @ source.data.bones[s].matrix_local).to_quaternion() for _g, s in pairs}
    hips_src = dict(pairs)[HIPS]
    rest_hips_s = sw @ source.data.bones[hips_src].head_local
    rest_hips_t = tw @ target.data.bones[HIPS].head_local
    scale = _hip_height(target, HIPS) / max(_hip_height(source, hips_src), 1e-6)

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

    tw_inv = tw.inverted()
    for f in frames:
        scene.frame_set(f)
        out = f - frames.start
        for game, src in pairs:
            spb = source.pose.bones[src]
            turn = (sw @ spb.matrix).to_quaternion() @ rest_s[src].inverted()
            world_rot = (turn @ rest_t[game]).to_matrix().to_4x4()
            tpb = target.pose.bones[game]
            if game == HIPS:
                head = rest_hips_t + (sw @ spb.head - rest_hips_s) * scale
            else:
                bpy.context.view_layer.update()
                head = tw @ tpb.head
            world_rot.translation = head
            tpb.matrix = tw_inv @ world_rot
            bpy.context.view_layer.update()
            tpb.keyframe_insert("rotation_quaternion", frame=out, group=game)
            if game == HIPS:
                tpb.keyframe_insert("location", frame=out, group=game)
    scene.frame_set(keep_frame)
    return pairs
