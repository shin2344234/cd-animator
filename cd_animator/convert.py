"""Coordinate conversion between Crimson Desert and Blender.

The game is left-handed with Y up: Kliff faces -Z in his bind pose and his
left side is +X. Blender is right-handed with Z up, and a character faces -Y
with its left side at +X. Swapping Y and Z maps one onto the other. The swap
is a reflection, so it also flips handedness, which is what makes Kliff's left
arm come out on his left.

Every transform T converts as M @ T @ M with M the swap (M is its own
inverse). For a quaternion that works out to (w, -x, -z, -y) and for a vector
to (x, z, y). Both are exact, so no precision is lost on the way in or out.

A game clip key K is a local transform applied on top of the bone's bind
transform: local = bind @ K, rotation and position both (NOTES.md has the
evidence). That is Blender's own pose model, rest @ basis, so a key becomes a
pose basis with no extra math, except for the bone direction correction below.

Blender draws a bone along its local +Y. The game's bones point along any
axis (biped bones mostly along +X), so each Blender bone's rest is the game
bind rotated by a fixed axis swap C that turns +Y towards the bone's child.
With rest_blender = bind @ C the pose basis must be C^-1 @ K @ C for the
skinned result to match the game. C is one of six 90 degree rotations, stored
on the bone as "cd_axis", so export can undo it.
"""

from mathutils import Matrix, Quaternion, Vector

SWAP = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))

# Rotation C for each game local axis that the Blender bone's +Y should follow.
# Each maps (0, 1, 0) onto the named axis.
AXIS_CORRECTION = {
    "+Y": Quaternion((1.0, 0.0, 0.0, 0.0)),
    "-Y": Quaternion((0.0, 0.0, 0.0, 1.0)),                        # 180 about Z
    "+X": Quaternion((0.7071067811865476, 0.0, 0.0, -0.7071067811865476)),  # -90 about Z
    "-X": Quaternion((0.7071067811865476, 0.0, 0.0, 0.7071067811865476)),   # +90 about Z
    "+Z": Quaternion((0.7071067811865476, 0.7071067811865476, 0.0, 0.0)),   # +90 about X
    "-Z": Quaternion((0.7071067811865476, -0.7071067811865476, 0.0, 0.0)),  # -90 about X
}

AXIS_VECTORS = {
    "+X": Vector((1, 0, 0)), "-X": Vector((-1, 0, 0)),
    "+Y": Vector((0, 1, 0)), "-Y": Vector((0, -1, 0)),
    "+Z": Vector((0, 0, 1)), "-Z": Vector((0, 0, -1)),
}


def quat_in(xyzw):
    """Game quaternion (x, y, z, w) to a Blender Quaternion, sign kept."""
    x, y, z, w = xyzw
    return Quaternion((w, -x, -z, -y))


def quat_out(q):
    """Blender Quaternion to a game (x, y, z, w), sign kept."""
    return (-q.x, -q.z, -q.y, q.w)


def vec_in(xyz):
    x, y, z = xyz
    return Vector((x, z, y))


def vec_out(v):
    return (v.x, v.z, v.y)


def matrix_in(xyzw, xyz):
    """Game rotation plus translation to a Blender 4x4 matrix."""
    m = quat_in(xyzw).to_matrix().to_4x4()
    m.translation = vec_in(xyz)
    return m


def pick_axis(local_dir):
    """The game local axis closest to a direction given in the bone's frame."""
    best, best_dot = "+Y", -2.0
    for name, v in AXIS_VECTORS.items():
        d = v.dot(local_dir)
        if d > best_dot:
            best, best_dot = name, d
    return best


def key_to_basis(axis, key_q, key_t):
    """Game key (quaternion xyzw, position xyz) to Blender pose basis
    (Quaternion, Vector) for a bone with correction `axis`."""
    c = AXIS_CORRECTION[axis]
    ci = c.conjugated()
    q = ci @ quat_in(key_q) @ c
    t = ci @ vec_in(key_t)
    return q, t


def basis_to_key(axis, q, t):
    """Inverse of key_to_basis."""
    c = AXIS_CORRECTION[axis]
    ci = c.conjugated()
    gq = c @ q @ ci
    gt = c @ t
    return quat_out(gq), vec_out(gt)
