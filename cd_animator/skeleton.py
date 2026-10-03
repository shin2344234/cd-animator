"""Build a Blender armature from a .pab skeleton."""

import os

import bpy
from mathutils import Matrix

from . import convert
from .formats import paa as paa_format

# Names that mark helper bones. A chain bone prefers a child without these
# when it picks which way to point.
_HELPER_TAGS = ("Twist", "Dummy", "_Sub", "Sub_", "Nub", "Front", "Back", "Attach", "Weapon", "Cloak")

MIN_LENGTH = 0.02
LEAF_LENGTH = 0.05


def _bind_world(skeleton):
    """Blender-space bind matrices (4x4, armature space), in bone order,
    without scale. A bone sits where the game's hierarchy puts it, its
    parents' bind scale included: the horse's tail bones have a bind scale
    of 1.85, 1.14, 1.17 and 1.16, and ignoring it left the tail 40% short."""
    world, scaled = [], []
    for b in skeleton.bones:
        local = convert.matrix_in(b.quat, b.trans)
        size = Matrix.Diagonal(convert.vec_in(b.scale).to_4d())
        size[3][3] = 1.0
        if b.parent < 0:
            w, s = local.copy(), local @ size
        else:
            w = world[b.parent] @ local
            s = scaled[b.parent] @ local @ size
            w.translation = (scaled[b.parent] @ local).translation
        world.append(w)
        scaled.append(s)
    return world


def _children(skeleton):
    kids = [[] for _ in skeleton.bones]
    for i, b in enumerate(skeleton.bones):
        if b.parent >= 0:
            kids[b.parent].append(i)
    return kids


def _main_child(skeleton, i, kids, world):
    head = world[i].translation
    best, best_len = None, 0.0
    plain = [k for k in kids[i] if not any(t in skeleton.bones[k].name for t in _HELPER_TAGS)]
    for k in plain or kids[i]:
        d = (world[k].translation - head).length
        if d > best_len:
            best, best_len = k, d
    return best if best_len >= MIN_LENGTH else None


def build_armature(context, path, skeleton=None):
    """Create an armature object for the .pab at `path` and link it to the
    scene. Returns the object."""
    if skeleton is None:
        with open(path, "rb") as f:
            skeleton = paa_format.read_pab(f.read())
    name = os.path.splitext(os.path.basename(path))[0]

    world = _bind_world(skeleton)
    kids = _children(skeleton)

    # Pick each bone's direction and length. Bones without a usable child
    # follow their parent's local axis.
    axes, lengths = [], []
    for i, b in enumerate(skeleton.bones):
        child = _main_child(skeleton, i, kids, world)
        if child is not None:
            d = world[child].translation - world[i].translation
            local_dir = world[i].to_3x3().inverted() @ d
            axes.append(convert.pick_axis(local_dir.normalized()))
            lengths.append(max(d.length, MIN_LENGTH))
        elif b.parent >= 0:
            axes.append(axes[b.parent])
            lengths.append(max(lengths[b.parent] * 0.5, MIN_LENGTH))
        else:
            axes.append("+Y")
            lengths.append(LEAF_LENGTH)

    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    context.collection.objects.link(obj)
    arm.display_type = "STICK"
    obj.show_in_front = True

    for o in context.view_layer.objects.selected:
        o.select_set(False)
    context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        ebs = []
        for i, b in enumerate(skeleton.bones):
            eb = arm.edit_bones.new(b.name)
            eb.head = (0.0, 0.0, 0.0)
            eb.tail = (0.0, lengths[i], 0.0)
            rest = world[i] @ convert.AXIS_CORRECTION[axes[i]].to_matrix().to_4x4()
            eb.matrix = rest
            eb.use_connect = False
            eb.use_deform = True
            if b.parent >= 0:
                eb.parent = ebs[b.parent]
            ebs.append(eb)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    for i, b in enumerate(skeleton.bones):
        bone = arm.bones[b.name]
        bone["cd_axis"] = axes[i]
        bone["cd_index"] = i
        bone["cd_bind_q"] = list(b.quat)
        bone["cd_bind_t"] = list(b.trans)
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"

    obj["cd_pab"] = path
    obj["cd_bone_count"] = len(skeleton.bones)

    # Blender bones hold no rest scale. The children of a bone with a bind
    # scale still sit where the game puts them (_bind_world), but a key that
    # moves such a child is not scaled by it, as it would be in the game.
    odd_scale = [b.name for i, b in enumerate(skeleton.bones)
                 if kids[i] and any(abs(s - 1.0) > 1e-4 for s in b.scale)]
    return obj, odd_scale


def is_cd_armature(obj):
    return obj is not None and obj.type == "ARMATURE" and "cd_pab" in obj
