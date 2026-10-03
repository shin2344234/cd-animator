"""Turn a .paa clip into a Blender action on a Crimson Desert armature."""

import json
import os

import bpy
from bpy_extras import anim_utils

from . import convert, meta
from .formats import paa_codec

FPS = 30
frame_step = paa_codec.frame_step   # by key kind: 8-bit LOD blocks count 1/5 s ticks


def block_kind(block, lod):
    """A stored block's key kind. Actions imported before 0.7.0 stored a
    section instead: 1 and 2 in that order were 8-bit and half float keys in
    a LOD clip, half float and float positions in a full one."""
    if "kind" in block:
        return block["kind"]
    return block["section"] + (0 if lod else 1)


def _fill(fcurve, frames, values):
    pts = fcurve.keyframe_points
    pts.add(len(frames))
    co = []
    for f, v in zip(frames, values):
        co += (f, v)
    pts.foreach_set("co", co)
    for p in pts:
        p.interpolation = "LINEAR"
    fcurve.update()


def import_clip(context, obj, path):
    """Load the clip at `path` onto armature `obj` as a new action and make
    it the active one. Returns (action, unknown_hashes)."""
    with open(path, "rb") as f:
        data = f.read()
    _container, td = paa_codec.decode_file(data)

    names = {paa_codec.bone_hash(b.name): b.name for b in obj.data.bones}
    name = os.path.splitext(os.path.basename(path))[0]

    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    slot = action.slots.new(id_type="OBJECT", name=obj.name)
    layer = action.layers.new("Layer")
    layer.strips.new(type="KEYFRAME")
    bag = anim_utils.action_ensure_channelbag_for_slot(action, slot)

    unknown = []
    blocks = []
    for bt in td.bones:
        bone_name = names.get(bt.name_hash)
        block = {
            "hash": bt.name_hash, "name": bone_name, "kind": bt.kind,
            "scale": len(bt.scale_keys), "rot": len(bt.rot_keys), "pos": len(bt.pos_keys),
            # padding u16 of float position keys, the same in every key of a track
            "aux": bt.pos_keys[0].aux if bt.pos_keys else 0,
            "neg": [],
        }
        blocks.append(block)
        if bone_name is None:
            unknown.append(bt.name_hash)
            continue
        axis = obj.data.bones[bone_name]["cd_axis"]
        base = f'pose.bones["{bone_name}"]'
        step = frame_step(bt.kind)

        if bt.rot_keys:
            frames = [k.frame * step for k in bt.rot_keys]
            quats = [convert.key_to_basis(axis, (k.x, k.y, k.z, k.w), (0.0, 0.0, 0.0))[0]
                     for k in bt.rot_keys]
            # Some tracks change sign between neighbouring keys (Kliff's
            # Bip_Weapon_C in the mount clips, 20 times in 44 clips). Read
            # literally that is a 340 degree spin in one frame, so the game
            # takes the short way, and Blender only does if the signs agree.
            # The export puts the stored signs back on the frames in "neg".
            for i in range(1, len(quats)):
                if quats[i - 1].dot(quats[i]) < 0.0:
                    quats[i].negate()
                    block["neg"].append(frames[i])
            for i in range(4):
                fc = bag.fcurves.new(base + ".rotation_quaternion", index=i, group_name=bone_name)
                _fill(fc, frames, [q[i] for q in quats])
        if bt.pos_keys:
            frames = [k.frame * step for k in bt.pos_keys]
            locs = [convert.key_to_basis(axis, (0.0, 0.0, 0.0, 1.0), (k.x, k.y, k.z))[1]
                    for k in bt.pos_keys]
            for i in range(3):
                fc = bag.fcurves.new(base + ".location", index=i, group_name=bone_name)
                _fill(fc, frames, [v[i] for v in locs])
        if bt.scale_keys:
            frames = [k.frame * step for k in bt.scale_keys]
            sizes = [convert.scale_to_basis(axis, (k.x, k.y, k.z)) for k in bt.scale_keys]
            for i in range(3):
                fc = bag.fcurves.new(base + ".scale", index=i, group_name=bone_name)
                _fill(fc, frames, [v[i] for v in sizes])

    last = round(td.lead.duration * FPS)
    action.use_frame_range = True
    action.frame_start = 0
    action.frame_end = max(last, 1)

    action["cd_source"] = path
    action["cd_lod"] = td.lod
    action["cd_duration"] = td.lead.duration
    if td.lead.rec1 is not None:
        action["cd_rec1"] = list(td.lead.rec1)
    action["cd_blocks"] = json.dumps(blocks)
    metabin = None if td.lod else meta.companion(path, ".paa_metabin")
    if metabin is not None:
        with open(metabin, "rb") as f:
            meta.load(action, f.read())

    reset_pose(obj)
    ad = obj.animation_data or obj.animation_data_create()
    ad.action = action
    ad.action_slot = slot
    if obj.get("cd_seated"):
        seat_rider(obj)

    scene = context.scene
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.frame_start = 0
    scene.frame_end = max(last, 1)
    # Chains swing with the new clip (chains.py).
    from . import chains, cloth
    if chains.chain_bones(obj):
        chains.bake(context, obj, 0, max(last, 1))
    # Cloth simulates from the clip's first frame as it plays (cloth.py).
    cloth.set_range(obj, 0, max(last, 1))
    return action, unknown


def seat_rider(obj, mount=None):
    """Place a rider armature relative to its mount by the rotation and
    position of the active clip's first transform record. Rider clips are
    authored in the mount's space offset by it: in the left mount clip it
    puts Kliff's origin 0.86 m to the broom's left and turned 90 degrees, in
    the idle it sits on the seat. Bones are untouched; only the object
    moves."""
    if mount is not None:
        obj.parent = mount
        obj.parent_type = "OBJECT"
        obj.matrix_parent_inverse.identity()
        obj["cd_seated"] = True
    action = obj.animation_data.action if obj.animation_data else None
    if action is None:
        return False
    if "cd_rec1" in action:
        r = action["cd_rec1"]
        q, t = r[3:7], r[7:10]
    elif "cd_rec_a" in action:   # imported before 0.7.0: rotation and position came first
        r = action["cd_rec_a"]
        q, t = r[0:4], r[4:7]
    else:
        return False
    obj.matrix_basis = convert.matrix_in(q, t)
    return True


def reset_pose(obj):
    """Put every bone back on its bind pose. Bones a clip does not animate
    keep whatever pose they had, so this runs before a clip is shown."""
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
