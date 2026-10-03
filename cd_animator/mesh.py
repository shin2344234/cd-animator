"""Show a game mesh (.pac) on a Crimson Desert armature.

The mesh comes in skinned to the armature: one vertex group per bone it is
weighted to, named after the bone, and an Armature modifier, so any clip on
the armature moves it. Vertices are in the skeleton's bind space, which is
where the armature's rest pose puts the bones (skeleton.py), so the mesh
needs no offset. Each submesh, such as Kliff's head, hands and body, gets a
material of its own, named after the game's material. Textures are not read.
"""

import os

import bpy

from . import convert
from .formats import paa_codec


class MeshError(Exception):
    pass


def build_mesh(context, armature, mesh, name):
    """A mesh object for `mesh` (formats.pac.Mesh), parented to `armature`
    and deformed by it. Returns (object, bone hashes the armature lacks)."""
    bone_of = {paa_codec.bone_hash(b.name): b.name for b in armature.data.bones}
    missing = sorted({h for h in mesh.palette if h not in bone_of})

    verts, tris, uvs, normals, mat_index, weights = [], [], [], [], [], []
    for i, sm in enumerate(mesh.submeshes):
        base = len(verts)
        verts += [convert.vec_in(p) for p in sm.positions]
        normals += [convert.vec_in(n) for n in sm.normals]
        uvs += sm.uvs
        weights += sm.skin
        for a, b, c in sm.triangles:
            if a != b and b != c and a != c:
                # The Y-Z swap into Blender mirrors the mesh, which turns
                # each triangle inside out unless two corners trade places.
                tris.append((base + a, base + c, base + b))
                mat_index.append(i)
    if not tris:
        raise MeshError("the mesh has no triangles at this detail level")

    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], tris)
    me.validate(clean_customdata=False)
    if len(me.polygons) != len(tris):
        raise MeshError(f"Blender kept {len(me.polygons)} of {len(tris)} triangles")

    uv_layer = me.uv_layers.new(name="UVMap")
    loop_verts = [0] * len(me.loops)
    me.loops.foreach_get("vertex_index", loop_verts)
    flat = []
    for v in loop_verts:
        u, w = uvs[v]
        flat += (u, 1.0 - w)
    uv_layer.data.foreach_set("uv", flat)

    for sm in mesh.submeshes:
        mat = bpy.data.materials.get(sm.material) or bpy.data.materials.new(sm.material)
        me.materials.append(mat)
    me.polygons.foreach_set("material_index", mat_index)
    # Faces must be smooth for the file's normals to show; flat ones override them.
    me.shade_smooth()
    me.normals_split_custom_set_from_vertices([tuple(n.normalized()) for n in normals])
    me.update()

    obj = bpy.data.objects.new(name, me)
    context.collection.objects.link(obj)
    obj.parent = armature
    obj.matrix_parent_inverse.identity()
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = armature

    groups = {}
    for v, skin in enumerate(weights):
        for slot, w in skin:
            if slot >= len(mesh.palette):
                continue
            bone = bone_of.get(mesh.palette[slot])
            if bone is None:
                continue
            g = groups.get(bone)
            if g is None:
                g = groups[bone] = obj.vertex_groups.new(name=bone)
            g.add([v], w, "ADD")
    obj["cd_pac"] = name
    return obj, missing


def known_hashes(armature, extra=()):
    """Bone hashes the palette search may match: the armature's own, plus
    `extra`, such as every bone of every skeleton in the game."""
    out = {paa_codec.bone_hash(b.name) for b in armature.data.bones}
    out.update(extra)
    return out


def mesh_name(path):
    return os.path.splitext(os.path.basename(path))[0]
