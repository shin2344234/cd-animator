"""Hair and beard sway: strands that lag behind the head and spring back
to their style.

Hair and beard vertices carry the same values as cloth (formats/pac.py, a
Submesh's pins), from 63 at the root, where the skeleton alone moves them,
down to 13 at the tips of Kliff's hair, and never 0. add() reads a value v
as a blend: the skeleton moves the vertex by v / 63 and a sway bone by the
rest. There is one sway bone for each side of the head with strands below
63 (back, left, right, front). It runs from the middle of that side's
roots to the middle of its swaying part, and hangs from the bone that carries most of that part: Bip01 Head
for hair, Bip01 Neck_Sub for a long beard on the chest, a face bone for a
beard on the chin, so a beard follows the face as it talks. chains.bake()
moves it as a damped spring: it is pulled back to where its parent carries
it, lags when the parent moves, and swings a little past before it
settles, never further than 45 degrees from there. The skeleton keeps the
strands' shape; only the swaying share follows the spring, so the tips
move most and the roots not at all. A side with swaying strands and no
roots of its own, such as the sides of a beard rooted around the mouth,
starts where its strands' nearest roots are.

The game's sway is not in a file the add-on reads beyond these values, so
the spring is a choice: as stiff as a pendulum half the bone's length, so
short hair swings faster and through about the same angle as long hair,
and damped to half of what would stop it without a swing.
"""

import math

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

HEAD = "Bip01 Head"
FULL = 63
GRAVITY = 9.81
STIFFNESS = 2.0  # times a pendulum of the bone's length
DAMPING = 0.5  # of critical damping
LIMIT = 45.0  # degrees from where the parent carries the bone
# Sides in order of angle from the back (+Y) toward the left (+X).
SIDES = ("back", "left", "front", "right")


def sway_parts(mesh):
    """Indices of submeshes whose vertices all sway or hold, none free:
    hair, where cloth has 0 (cloth.py)."""
    return [i for i, sb in enumerate(mesh.submeshes) if sb.pins and 0 < min(sb.pins) < FULL]


def _sides(offset):
    """[(side, share)]: the two sides of the head an armature-space offset
    from it lies between, shared by angle so that a strand across two sides
    bends as one; the character faces -Y."""
    angle = math.degrees(math.atan2(offset.x, offset.y)) % 360.0
    i = int(angle // 90.0)
    t = angle / 90.0 - i
    return [(SIDES[i % 4], 1.0 - t), (SIDES[(i + 1) % 4], t)]


def _carrier(arm, obj, members):
    """The armature bone that carries most of `members`, (vertex, sway
    weight) pairs of `obj`, by its skin weights; Bip01 Head when none
    does. Chain bones are left out, since they swing themselves."""
    groups = {g.index: g.name for g in obj.vertex_groups}
    verts = obj.data.vertices
    load = {}
    for k, w in members:
        for g in verts[k].groups:
            name = groups.get(g.group)
            if name is not None:
                load[name] = load.get(name, 0.0) + w * g.weight
    bones = arm.data.bones
    for name in sorted(load, key=load.get, reverse=True):
        b = bones.get(name)
        if b is not None and not b.get("cd_chain"):
            return name
    return HEAD


def add(context, arm, obj, mesh, name):
    """Give the swaying parts of `obj`, built from `mesh`, sway bones and
    blend their vertices onto them (module docstring). Returns the number
    of sway bones added."""
    parts = set(sway_parts(mesh))
    head = arm.data.bones.get(HEAD)
    if not parts or head is None:
        return 0
    centre = head.head_local
    verts = obj.data.vertices
    sway, roots, side_roots = {}, [], {}
    base = 0
    for i, sb in enumerate(mesh.submeshes):
        if i in parts:
            for j, pin in enumerate(sb.pins):
                k = base + j
                co = verts[k].co
                for side, share in _sides(co - centre):
                    if share <= 0.0:
                        continue
                    if pin < FULL:
                        sway.setdefault(side, []).append((k, (1.0 - pin / FULL) * share))
                    elif share >= 0.5:
                        side_roots.setdefault(side, []).append(co)
                if pin >= FULL:
                    roots.append(co)
        base += len(sb.positions)
    tree = None
    if roots:
        tree = KDTree(len(roots))
        for i, co in enumerate(roots):
            tree.insert(co, i)
        tree.balance()
    rows = []
    for side, members in sway.items():
        total = sum(w for _k, w in members)
        if total < 1.0:
            continue
        tip = sum((verts[k].co * w for k, w in members), Vector()) / total
        if side_roots.get(side):
            root = sum(side_roots[side], Vector()) / len(side_roots[side])
        elif tree:
            root = sum((tree.find(verts[k].co)[0] * w for k, w in members), Vector()) / total
        else:
            root = centre.copy()
        if (tip - root).length < 0.02:
            tip = root + Vector((0.0, 0.0, -0.05))
        rows.append((side, root, tip, members, _carrier(arm, obj, members)))
    if not rows:
        return 0

    names = {b.name for b in arm.data.bones}
    added = {}
    active = context.view_layer.objects.active
    context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        ebs = arm.data.edit_bones
        for side, root, tip, _m, parent in rows:
            bone = f"{name}:Sway_{side}"[:60]
            n = 1
            while bone in names or bone in added.values():
                bone, n = f"{name}:Sway_{side}.{n}"[:63], n + 1
            eb = ebs.new(bone)
            eb.head, eb.tail = root, tip
            eb.parent = ebs[parent]
            eb.use_deform = True
            added[side] = bone
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.objects.active = active
    swaying = {}
    for _side, _r, _t, members, _p in rows:
        for k, w in members:
            swaying[k] = swaying.get(k, 0.0) + w
    for k, w in swaying.items():
        for g in verts[k].groups:
            g.weight *= 1.0 - w
    for side, _r, _t, members, _p in rows:
        b = arm.data.bones[added[side]]
        b["cd_extra"] = name
        b["cd_chain"] = True
        b["cd_stiffness"] = STIFFNESS * GRAVITY / max(b.length, 0.01)
        b["cd_damping"] = DAMPING
        b["cd_limit"] = LIMIT
        b["cd_mass"] = 1
        b["cd_radius"] = 0.0
        arm.pose.bones[added[side]].rotation_mode = "QUATERNION"
        group = obj.vertex_groups.new(name=added[side])
        for k, w in members:
            group.add([k], w, "REPLACE")
    obj["cd_sway"] = len(rows)
    return len(rows)

