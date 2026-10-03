"""Bones a mesh brings with it, and physics chains that hang and swing.

A mesh with bones of its own (formats/pac.py, flag 0x1) often has bones no
character skeleton has: a flail's links (B_Add_Flail_000, _002), the
segments of a flexible flail, rope and chain links, a helmet's neck guard.
The game moves the chains with physics; the files hold no settings for it
that the add-on reads (NOTES.md). add_bones() makes each such bone a bone
of the armature, so the mesh's vertices follow it, and bake() simulates the
chains over the scene's frames and keys them on an NLA track of their own,
"CD chains", which the clip's action plays over and the exporter never
reads.

A chain is a run of bones named as a family with a number, each the
parent of the next, whose name says chain, flail, rope, whip or feather:
B_Add_FlexibleFlail_000 to _004. Its first bone holds on to whatever
carries it, the weapon or a skeleton bone, and the rest swing. Other
numbered families, such as a bow's B_Add_Arrow_Down or a helmet's
B_Hel_Eye, are parts the game animates and stay rigid. Setting cd_chain
on any added bone makes bake() swing it too. A bone pivots at its head, except where its vertices are a rigid
piece that touches its parent's (the short flail's chain and ball, all on
B_Add_Flail_002, which sits at the ball's centre): then it pivots where the
two pieces meet. Each swinging bone's tail is its first swinging child's
pivot, or the middle of its own vertices at the end of a chain, so that
the weight sits where the ball is.
"""

import re

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

from . import convert

TRACK = "CD chains"
GRAVITY = 9.81
SUBSTEPS = 4
FPS = 30.0
_FAMILY = re.compile(r"^(.*?)[_ ]?(\d+)$")
# Families that hang. Others with numbered bones, a bow's arrow rest, a
# greatsword's handle, a helmet's visor, a scroll, are moved by the game's
# own animation and stay rigid.
_HANGS = re.compile(r"chain(?!saw)|flail|rope|whip|feather", re.I)
_BODY = "Bip01 Pelvis"
_FEET = ("Bip01 L Toe0", "Bip01 R Toe0", "Bip01 L Foot", "Bip01 R Foot")
_BODY_BONES = ("Pelvis", "Spine", "Spine1", "Spine2", "Neck", "Head", "L Thigh", "R Thigh", "L Calf", "R Calf",
               "L Foot", "R Foot", "L UpperArm", "R UpperArm", "L Forearm", "R Forearm", "L Hand", "R Hand")


def _family(name):
    m = _FAMILY.match(name)
    return m.group(1) if m else None


def _regions(mesh):
    """{bone index: [game-space vertex]} of vertices weighted over 0.5 to a bone."""
    index = {b.hash: i for i, b in enumerate(mesh.bones)}
    out = {}
    for sm in mesh.submeshes:
        for p, skin in zip(sm.positions, sm.skin):
            for slot, w in skin:
                if w > 0.5 and slot < len(mesh.palette) and mesh.palette[slot] in index:
                    out.setdefault(index[mesh.palette[slot]], []).append(Vector(p))
    return out


def _pivot(mesh, i, regions, touch=0.02):
    """Game-space point bone `i` turns about (module docstring)."""
    head = Vector(mesh.bones[i].world[3::4][:3])
    own = regions.get(i)
    j = mesh.bones[i].parent
    while j >= 0 and not regions.get(j):
        j = mesh.bones[j].parent
    if not own or j < 0:
        return head
    tree = KDTree(len(regions[j]))
    for k, v in enumerate(regions[j]):
        tree.insert(v, k)
    tree.balance()
    gaps = [(tree.find(v)[2], v) for v in own]
    near = min(d for d, _v in gaps)
    if near > touch:
        return head
    meet = [v for d, v in gaps if d <= near + 0.01]
    return sum(meet, Vector()) / len(meet)


def plan(mesh, keep):
    """[(bone index, head, tail, swings, vertex count, radius)] in game
    space for the bones of `mesh` to add to an armature, parents first;
    `keep(i)` is False for a bone the armature already has or that maps
    elsewhere. The vertex count stands in for the bone's mass in bake(),
    and the radius is how far its tail keeps from the body and the floor."""
    bones = mesh.bones
    swing = []
    for i, b in enumerate(bones):
        fam = _family(b.name)
        p = b.parent
        swing.append(keep(i) and fam is not None and bool(_HANGS.search(fam)) and p >= 0 and keep(p)
                     and _family(bones[p].name) == fam)
    regions = _regions(mesh)
    heads = {i: (_pivot(mesh, i, regions) if swing[i] else Vector(b.world[3::4][:3]))
             for i, b in enumerate(bones) if keep(i)}
    out = []
    for i, b in enumerate(bones):
        if not keep(i):
            continue
        kids = [k for k, c in enumerate(bones) if c.parent == i and k in heads]
        tail = None
        radius = 0.01
        if swing[i]:
            nxt = next((k for k in kids if swing[k]), None)
            if nxt is not None:
                tail = heads[nxt]
            elif regions.get(i):
                mid = sum(regions[i], Vector()) / len(regions[i])
                if (mid - heads[i]).length > 0.01:
                    tail = mid
                    # The end piece, a flail's ball, is about this round.
                    far = sorted((v - mid).length for v in regions[i])
                    radius = min(0.3, far[int(len(far) * 0.9)])
        else:
            nxt = next((k for k in kids if (heads[k] - heads[i]).length > 0.01), None)
            tail = heads[nxt] if nxt is not None else None
        if tail is None or (tail - heads[i]).length < 0.005:
            tail = heads[i] + Vector((0.0, 0.0, -0.05))
        out.append((i, heads[i], tail, swing[i], len(regions.get(i, ())), radius))
    return out


def add_bones(context, arm, mesh, name, remap, placement):
    """Add the bones of `mesh` that `remap` (palette hash to armature bone)
    leaves to its nearest ancestor or to a socket's bone as bones of their
    own, under the bone they mapped to, and point `remap` at them. The new
    bones are named "<mesh name>:<bone>" and carry cd_extra; a swinging
    one carries cd_chain. `placement` puts them as it puts the vertices; a
    mesh skinned to the skeleton takes its parent bone's rest offset
    instead. Returns the number of bones added."""
    names = {b.name for b in arm.data.bones}
    root = next((i for i, b in enumerate(mesh.bones) if b.parent < 0), None)
    socketed = placement is not None
    # A weapon at a socket: everything not added follows the socket's bone.
    fallback = next(iter(remap.values()), None) if socketed else None

    def keep(i):
        b = mesh.bones[i]
        if b.name in names:
            return False
        return not (socketed and i == root)

    rows = plan(mesh, keep)
    if not rows:
        return 0
    target = {}
    for i, b in enumerate(mesh.bones):
        target[i] = remap.get(b.hash) if b.hash in remap else (b.name if b.name in names else fallback)
    added = {}
    for i, _h, _t, _s, _m, _r in rows:
        base = f"{name}:{mesh.bones[i].name}"[:60]
        new, n = base, 1
        while new in names or new in added.values():
            new, n = f"{base}.{n}", n + 1
        added[i] = new

    def parent_of(i):
        p = mesh.bones[i].parent
        if p < 0:
            return target.get(i)
        return added.get(p) or target.get(p)

    offsets = {}
    for i, _h, _t, _s, _m, _r in rows:
        anchor = parent_of(i)
        while anchor in added.values():
            anchor = parent_of(next(k for k, v in added.items() if v == anchor))
        bone = arm.data.bones.get(anchor or "")
        flat = bone.get("cd_rest_offset") if bone is not None else None
        offsets[i] = Matrix([flat[0:4], flat[4:8], flat[8:12], flat[12:16]]) if flat else Matrix()
    move = placement if socketed else None

    active = context.view_layer.objects.active
    mode = arm.mode
    context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        ebs = arm.data.edit_bones
        for i, head, tail, _s, _m, _r in rows:
            m = move if move is not None else offsets[i]
            eb = ebs.new(added[i])
            eb.head = m @ convert.vec_in(head)
            eb.tail = m @ convert.vec_in(tail)
            eb.use_deform = True
            eb.use_connect = False
        for i, _h, _t, _s, _m, _r in rows:
            parent = parent_of(i)
            if parent:
                ebs[added[i]].parent = ebs.get(parent)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.objects.active = active
        if mode != "OBJECT" and active == arm:
            bpy.ops.object.mode_set(mode=mode)
    for i, _h, _t, swings, mass, radius in rows:
        bone = arm.data.bones[added[i]]
        bone["cd_extra"] = name
        if swings:
            bone["cd_chain"] = True
            bone["cd_mass"] = max(1, mass)
            bone["cd_radius"] = radius * (placement.to_scale().y if socketed else 1.0)
        if move is None and offsets[i] != Matrix():
            bone["cd_rest_offset"] = [x for row in offsets[i] for x in row]
        pb = arm.pose.bones[added[i]]
        pb.rotation_mode = "QUATERNION"
        remap[mesh.bones[i].hash] = added[i]
    return len(rows)


def chain_bones(arm):
    """Names of the armature's swinging bones, parents first."""
    return [b.name for b in arm.data.bones if b.get("cd_chain")]


def _capsules(arm):
    """[(bone name, radius)] for the body's main bones. A bone's radius is
    the median distance from it of the CD_Nude mesh's vertices whose
    strongest group is that bone or a helper under it (Bip01 Calf_Sub,
    UpArmTwist); 8 cm without a body mesh."""
    bones = arm.data.bones
    found = [n for n in ("Bip01 " + s for s in _BODY_BONES) if n in bones]
    body = next((o for o in arm.children if o.type == "MESH" and o.get("cd_component") == "CD_Nude"), None)
    radius = {}
    if body is not None:
        owner = {}
        for g in body.vertex_groups:
            b = bones.get(g.name)
            while b is not None and b.name not in found:
                b = b.parent
            if b is not None:
                owner[g.index] = b.name
        dists = {}
        for v in body.data.vertices:
            best = max(v.groups, key=lambda g: g.weight, default=None)
            if best is None or best.group not in owner:
                continue
            b = bones[owner[best.group]]
            a, c = b.head_local, b.tail_local
            t = max(0.0, min(1.0, (v.co - a).dot(c - a) / max((c - a).length_squared, 1e-9)))
            dists.setdefault(b.name, []).append((v.co - (a + (c - a) * t)).length)
        for name, ds in dists.items():
            ds.sort()
            radius[name] = ds[len(ds) // 2]
    return [(n, radius.get(n, 0.08)) for n in found]


def _push_out(p, a, c, r):
    ac = c - a
    t = max(0.0, min(1.0, (p - a).dot(ac) / max(ac.length_squared, 1e-12)))
    q = a + ac * t
    d = p - q
    if d.length < r:
        return q + (d.normalized() if d.length > 1e-9 else Vector((0.0, 0.0, 1.0))) * r
    return p


def remove(arm):
    """Drop the armature's chain keys, its CD chains track and its action."""
    ad = arm.animation_data
    if ad is None:
        return
    track = ad.nla_tracks.get(TRACK)
    if track is not None:
        for s in track.strips:
            if s.action is not None and s.action.get("cd_chains"):
                bpy.data.actions.remove(s.action)
        ad.nla_tracks.remove(track)


def bake(context, arm, start=None, end=None, damping=0.03, collide=True, settle=3.0):
    """Simulate the armature's chains over frames `start` to `end` (the
    scene's range by default) and key them on the CD chains track. A chain
    first hangs still for `settle` seconds at the first frame's pose.
    `damping` is the share of speed lost each substep. With `collide` the
    links keep out of the body's main bones and no lower than its lowest
    foot or toe bone, taken as the floor. Returns the number of chain bones
    keyed."""
    from bpy_extras import anim_utils
    names = chain_bones(arm)
    if not names:
        return 0
    remove(arm)
    scene = context.scene
    start = scene.frame_start if start is None else start
    end = scene.frame_end if end is None else end
    bones = arm.data.bones
    pbs = arm.pose.bones
    order = [b.name for b in bones if b.get("cd_chain")]
    capsules = _capsules(arm) if collide else []
    hold = set(b.name for b in bones if b.get("cd_extra")) - set(order)
    dt = 1.0 / FPS / SUBSTEPS
    keep = 1.0 - damping
    rest_len = {n: (bones[n].tail_local - bones[n].head_local).length for n in order}

    needed = {bones[n].parent.name for n in order if bones[n].parent} - set(order)
    needed |= {n for n, _r in capsules} | set(_FEET) | {_BODY}

    def frame_state():
        """World matrices of the bones the chains hang from or bump into."""
        mw = arm.matrix_world
        return {n: mw @ pbs[n].matrix for n in needed if n in pbs}

    head_prev = {}
    # A link hangs from its parent's tail particle when it starts where the
    # parent ends; otherwise from a point fixed on the parent bone.
    hung = {n: bool(bones[n].parent and bones[n].parent.name in rest_len
                    and (bones[n].head_local - bones[n].parent.tail_local).length < 1e-3) for n in order}
    inv_mass = {n: 1.0 / max(1.0, float(bones[n].get("cd_mass", 1))) for n in order}
    size = {n: float(bones[n].get("cd_radius", 0.01)) for n in order}
    rel = {n: bones[n].parent.matrix_local.inverted() @ bones[n].matrix_local for n in order}
    current = {}

    def solve(before, after, steps, record, keep):
        """Run `steps` substeps, the bones moving from `before` to `after`.
        Each substep moves the links under gravity, then pulls every link
        back to its length, the lighter end giving way more, ten times over.
        Damping takes speed off a link relative to the body's, so a running
        character does not drag its chains through a headwind."""
        mw = arm.matrix_world
        scale = mw.to_scale()
        g = Vector((0.0, 0.0, -GRAVITY))
        for k in range(1, steps + 1):
            state = after if before is after else {n: before[n].lerp(after[n], k / steps) for n in after}
            feet = [state[n].translation.z for n in _FEET if n in state]
            ground = min(feet) if feet else None
            caps = [(state[n].translation, (state[n] @ Matrix.Translation((0, bones[n].length, 0))).translation,
                     r * max(scale)) for n, r in capsules if n in state]
            fixed = {}
            for n in order:
                if not hung[n]:
                    parent = state.get(bones[n].parent.name) or current.get(bones[n].parent.name, mw)
                    fixed[n] = (parent @ rel[n]).translation
            # The air moves with the body, so a running character's chains
            # are not dragged backwards; the pelvis stands for the body.
            body = state[_BODY].translation if _BODY in state else mw.translation
            vh = body - head_prev.get(_BODY, body)
            head_prev[_BODY] = body.copy()
            for n in order:
                p = pos[n]
                v = vh + ((p - prev[n]) - vh) * keep
                prev[n] = p.copy()
                pos[n] = p + v + g * dt * dt
            for _ in range(10):
                for n in order:
                    if hung[n]:
                        a, wa = pos[bones[n].parent.name], inv_mass[bones[n].parent.name]
                    else:
                        a, wa = fixed[n], 0.0
                    wb = inv_mass[n]
                    d = pos[n] - a
                    length = rest_len[n] * scale.y
                    if d.length < 1e-9:
                        continue
                    fix = d.normalized() * (d.length - length) / (wa + wb)
                    pos[n] = pos[n] - fix * wb
                    if wa:
                        pos[bones[n].parent.name] = a + fix * wa
                    if collide:
                        p = pos[n]
                        reach = size[n] * scale.y
                        for ca, cc, r in caps:
                            p = _push_out(p, ca, cc, r + reach)
                        if ground is not None and p.z < ground + reach:
                            p.z = ground + reach
                        pos[n] = p
            current.clear()
            current.update(state)
            for n in order:
                b = bones[n]
                m0 = (current.get(b.parent.name) or mw) @ rel[n]
                head = m0.translation
                d = pos[n] - head
                y0 = (m0.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
                turn = y0.rotation_difference(d.normalized() if d.length > 1e-9 else y0).to_matrix().to_4x4()
                lin = m0.copy()
                lin.translation = Vector()
                mb = Matrix.Translation(head) @ turn @ lin
                current[n] = mb
                if record is not None and k == steps:
                    record[n] = (m0.inverted() @ mb).to_quaternion()

    scene.frame_set(start)
    state = frame_state()
    pos, prev = {}, {}
    mw = arm.matrix_world
    for n in order:
        p = (mw @ pbs[n].matrix @ Matrix.Translation((0, bones[n].length, 0))).translation
        pos[n] = p.copy()
        prev[n] = p.copy()
    # Settle with a little more damping than the clip gets, enough to stop
    # a chain that starts straight out within a second or two.
    solve(state, state, int(settle * FPS * SUBSTEPS), None, min(keep, 0.95))
    # Then start the chain moving with what carries it.
    scene.frame_set(min(start + 1, end))
    ahead = frame_state()
    for n in order:
        b = bones[n]
        if b.parent and b.parent.name in state:
            move = ahead[b.parent.name] @ state[b.parent.name].inverted()
            prev[n] = pos[n] - (move @ pos[n] - pos[n]) / SUBSTEPS
        else:
            prev[n] = pos[n].copy()
    head_prev.clear()

    keys = {n: [] for n in order}
    before = state
    for f in range(start, end + 1):
        scene.frame_set(f)
        after = frame_state()
        rot = {}
        solve(before if f > start else after, after, SUBSTEPS, rot, keep)
        before = after
        for n in order:
            keys[n].append((f, rot[n]))

    action = bpy.data.actions.new(f"{arm.name} chains")
    action["cd_chains"] = True
    slot = action.slots.new(id_type="OBJECT", name=arm.name)
    layer = action.layers.new("Layer")
    layer.strips.new(type="KEYFRAME")
    bag = anim_utils.action_ensure_channelbag_for_slot(action, slot)
    for n in order:
        qs = [q for _f, q in keys[n]]
        for i in range(1, len(qs)):
            if qs[i - 1].dot(qs[i]) < 0.0:
                qs[i].negate()
        for i in range(4):
            fc = bag.fcurves.new(f'pose.bones["{n}"].rotation_quaternion', index=i, group_name=n)
            pts = fc.keyframe_points
            pts.add(len(qs))
            co = []
            for (f, _q), q in zip(keys[n], qs):
                co += (f, q[i])
            pts.foreach_set("co", co)
            for k in pts:
                k.interpolation = "LINEAR"
            fc.update()
    ad = arm.animation_data or arm.animation_data_create()
    track = ad.nla_tracks.new()
    track.name = TRACK
    strip = track.strips.new(TRACK, start, action)
    strip.action_slot = slot
    strip.extrapolation = "HOLD"
    strip.blend_type = "REPLACE"
    for n in hold:
        pbs[n].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    scene.frame_set(start)
    return len(order)
