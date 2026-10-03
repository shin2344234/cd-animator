"""Cloth: cloaks, coat tails, skirts and flags that hang and flow.

A mesh vertex says how far the skeleton moves it (formats/pac.py, the pins
of a Submesh): 63 for the skeleton alone, 0 for the game's cloth
simulation alone, values between for a blend. setup() gives the parts of a
mesh with any vertex at 0 to Blender's cloth simulation: those parts move
into an object of their own, "<mesh> cloth", with the Armature modifier
first and a Cloth modifier after it. Its "CD pin" vertex group holds each
vertex's value over 63, so the skeleton holds the collar and the hem hangs
free. The character's body, its CD_Nude mesh, gets a Collision modifier so
the cloth rests on it. The parts the skeleton alone moves, such as the hair
cards on a fur collar, stay in the first object.

The game's own cloth settings (stiffness, weight) are in Havok data in the
mesh that the add-on does not read, so the cloth uses one set of values
for heavy cloth. Blender simulates it from the clip's first frame as the
frames play; bake() stores it so any frame can be shown or rendered.
"""

import bmesh
import bpy

PIN_GROUP = "CD pin"
FREE = 0
FULL = 63


def cloth_parts(mesh, chained=()):
    """Indices of the submeshes of `mesh` with any vertex the cloth moves
    alone. A part whose free vertices mostly hang on the palette hashes in
    `chained`, bones chains.py swings, is left to the chain: the short and
    long flails' chain and ball are free vertices in the game, and as
    Blender cloth the iron ball would sag like a sack."""
    out = []
    for i, sb in enumerate(mesh.submeshes):
        free = [skin for pin, skin in zip(sb.pins, sb.skin) if pin == FREE]
        if not free:
            continue
        tops = [max(skin, key=lambda s: s[1])[0] for skin in free if skin]
        on_chain = sum(1 for t in tops if t < len(mesh.palette) and mesh.palette[t] in chained)
        if on_chain * 2 <= len(free):
            out.append(i)
    return out


def _keep_materials(obj, keep):
    """Delete the faces of `obj` whose material index is not in `keep`,
    and the vertices left with no face."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    gone = [f for f in bm.faces if f.material_index not in keep]
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _weld(obj, distance=0.0005):
    """Join the cloth's vertices that sit on one spot. The game's meshes
    split vertices along texture seams; left split, a free panel has no
    hold on the pinned collar and falls away from it."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
    bm.to_mesh(me)
    bm.free()
    me.update()


def _hold_loose(obj):
    """Pin every piece of the cloth with no pinned vertex to the skeleton,
    and return how many there were. The fur strands on Kliff's appearance
    cloak (195 of them), a strip of his coat and a scabbard's tassel touch
    nothing the skeleton holds; the game attaches them through cloth data
    the add-on does not read, and left free they fall away."""
    group = obj.vertex_groups[PIN_GROUP]
    weight = {}
    for v in obj.data.vertices:
        weight[v.index] = next((g.weight for g in v.groups if g.group == group.index), 0.0)
    links = {}
    for e in obj.data.edges:
        a, b = e.vertices
        links.setdefault(a, []).append(b)
        links.setdefault(b, []).append(a)
    seen, loose = set(), []
    for start in weight:
        if start in seen:
            continue
        piece, stack = [], [start]
        seen.add(start)
        while stack:
            v = stack.pop()
            piece.append(v)
            for w in links.get(v, ()):
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        if max(weight[v] for v in piece) == 0.0:
            loose.append(piece)
    for piece in loose:
        group.add(piece, 1.0, "REPLACE")
    return len(loose)


def _body(arm):
    return next((o for o in arm.children if o.type == "MESH" and o.get("cd_component") == "CD_Nude"), None)


def setup(context, arm, obj, mesh, chained=()):
    """Give the cloth parts of `obj`, built from `mesh`, a cloth simulation
    (module docstring); `chained` is for cloth_parts. Returns the cloth
    object, `obj` itself when every part is cloth, or None when no part
    is."""
    parts = cloth_parts(mesh, chained)
    if not parts:
        return None
    group = obj.vertex_groups.new(name=PIN_GROUP)
    base = 0
    by_weight = {}
    for sb in mesh.submeshes:
        for i, pin in enumerate(sb.pins):
            by_weight.setdefault(pin, []).append(base + i)
        base += len(sb.positions)
    for pin, ids in by_weight.items():
        group.add(ids, pin / FULL, "REPLACE")

    cloth_obj = obj
    if len(parts) < len(mesh.submeshes):
        cloth_obj = obj.copy()
        cloth_obj.data = obj.data.copy()
        cloth_obj.name = obj.name + " cloth"
        for coll in obj.users_collection:
            coll.objects.link(cloth_obj)
        _keep_materials(cloth_obj, set(parts))
        _keep_materials(obj, set(range(len(mesh.submeshes))) - set(parts))
        obj.vertex_groups.remove(obj.vertex_groups[PIN_GROUP])
        obj["cd_cloth_part"] = cloth_obj.name
        cloth_obj["cd_cloth_of"] = obj.name
    cloth_obj["cd_cloth"] = True
    _weld(cloth_obj)
    held = _hold_loose(cloth_obj)
    if held:
        cloth_obj["cd_cloth_held"] = held

    mod = cloth_obj.modifiers.new("Cloth", "CLOTH")
    c = mod.settings
    c.quality = 6
    c.mass = 0.4
    c.air_damping = 1.5
    c.tension_stiffness = c.compression_stiffness = 20.0
    c.shear_stiffness = 10.0
    c.bending_stiffness = 1.0
    c.vertex_group_mass = PIN_GROUP
    c.pin_stiffness = 1.0
    col = mod.collision_settings
    col.use_collision = True
    col.distance_min = 0.01
    col.collision_quality = 3
    col.use_self_collision = False
    scene = context.scene
    mod.point_cache.frame_start = scene.frame_start
    mod.point_cache.frame_end = scene.frame_end

    collide_body(arm)
    return cloth_obj


def collide_body(arm):
    """Give the armature's body mesh a Collision modifier when it has cloth."""
    body = _body(arm)
    if body is None or not cloth_objects(arm) or any(m.type == "COLLISION" for m in body.modifiers):
        return
    body.modifiers.new("Collision", "COLLISION")
    body.collision.thickness_outer = 0.015
    body.collision.cloth_friction = 5.0


def cloth_objects(arm):
    return [o for o in arm.children if o.type == "MESH" and o.get("cd_cloth")]


def set_range(arm, start, end):
    """Simulate the armature's cloth over frames `start` to `end`, dropping
    any bake."""
    for o in cloth_objects(arm):
        for m in o.modifiers:
            if m.type == "CLOTH":
                pc = m.point_cache
                if pc.is_baked:
                    with bpy.context.temp_override(point_cache=pc):
                        bpy.ops.ptcache.free_bake()
                pc.frame_start = start
                pc.frame_end = end


def bake(context, arm):
    """Simulate and store the armature's cloth over its cache range, so any
    frame shows without playing from the start. Returns the number of
    cloth objects baked."""
    done = 0
    for o in cloth_objects(arm):
        for m in o.modifiers:
            if m.type == "CLOTH":
                pc = m.point_cache
                with context.temp_override(point_cache=pc, scene=context.scene):
                    if pc.is_baked:
                        bpy.ops.ptcache.free_bake()
                    bpy.ops.ptcache.bake(bake=True)
                done += 1
    return done
