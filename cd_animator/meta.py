"""A clip's metadata on its action: the events and phases of its .paa_metabin.

Events are timed tags, the exe's AnimationFrameTag: a begin and an end in
seconds and a type from 0 to 7, TAG_NAMES below. Phases are timed
windows with two small selectors and a vector; mount and dismount clips have
them. Both are stored in seconds, as 32-bit floats like the file's own, so a
clip exported unedited writes the same numbers back. The panel shows them in
frames at 30 fps.
"""

import os

import bpy
from bpy.props import BoolProperty, CollectionProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import PropertyGroup

from .formats import metabin_codec

FPS = 30


def companion(source, suffix):
    """A file that goes with the clip at `source`: next to it, or in an
    actionchart folder beside its folder (where paz_unpack puts metabins)."""
    folder, leaf = os.path.split(source)
    stem = leaf[:-len(".paa")] if leaf.lower().endswith(".paa") else leaf
    for candidate in (os.path.join(folder, stem + suffix),
                      os.path.join(os.path.dirname(folder), "actionchart", stem + suffix)):
        if os.path.isfile(candidate):
            return candidate
    return None


def _frames(name):
    """A frame view of the seconds property `name`."""
    return FloatProperty(
        name=name.capitalize() + " (frame)", precision=1, step=50,
        get=lambda self: getattr(self, name) * FPS,
        set=lambda self, v: setattr(self, name, round(v * 2.0) / 2.0 / FPS))


class CDEvent(PropertyGroup):
    begin: FloatProperty(name="Begin", unit="TIME_ABSOLUTE", description="Seconds from the clip's start")
    end: FloatProperty(name="End", unit="TIME_ABSOLUTE", description="Seconds from the clip's start")
    type: IntProperty(name="Type", min=0, max=255, description="What the event marks: 2 and 3 a foot swinging, 4 and 5 "
                      "it planted, 6 and 7 the top of its step, left then right; 0 and 1 alternate, meaning unknown")
    begin_frame: _frames("begin")
    end_frame: _frames("end")


class CDPhase(PropertyGroup):
    t0: FloatProperty(name="Start")
    t1: FloatProperty(name="End")
    a: IntProperty(name="A", min=0, max=255)
    b: IntProperty(name="B", min=0, max=255)
    x: FloatProperty(name="X")
    y: FloatProperty(name="Y")
    z: FloatProperty(name="Z")
    t0_frame: _frames("t0")
    t1_frame: _frames("t1")


class CDClipMeta(PropertyGroup):
    loaded: BoolProperty(description="The events and phases came from the clip's .paa_metabin")
    events: CollectionProperty(type=CDEvent)
    phases: CollectionProperty(type=CDPhase)
    active_event: IntProperty()


classes = (CDEvent, CDPhase, CDClipMeta)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Action.cd_meta = PointerProperty(type=CDClipMeta)


def unregister():
    del bpy.types.Action.cd_meta
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


def load(action, metabin_bytes):
    """Fill the action's events and phases from a .paa_metabin."""
    mb = metabin_codec.read_metabin(metabin_bytes)
    m = action.cd_meta
    m.events.clear()
    m.phases.clear()
    for e in mb.events:
        it = m.events.add()
        it.begin, it.end, it.type = e.begin, e.end, e.type
    for p in mb.phases:
        it = m.phases.add()
        it.t0, it.t1, it.a, it.b, it.x, it.y, it.z = p.t0, p.t1, p.a, p.b, p.x, p.y, p.z
    m.loaded = True


def apply(action, mb):
    """Put the action's events and phases into metabin `mb`, events sorted by
    begin as the game's are. Leaves `mb` alone when the action never had any
    loaded."""
    m = action.cd_meta
    if not m.loaded:
        return
    mb.events = sorted((metabin_codec.Event(e.begin, e.end, e.type) for e in m.events), key=lambda e: e.begin)
    mb.phases = [metabin_codec.Phase(p.t0, p.t1, p.a, p.b, p.x, p.y, p.z) for p in m.phases]


# What the event types mark, from the feet inside each type's windows over a
# sample of 120 clips (NOTES.md). The exe calls them AnimationFrameTag.
TAG_NAMES = {0: "Unknown A", 1: "Unknown B", 2: "Left foot swings", 3: "Right foot swings", 4: "Left foot planted",
             5: "Right foot planted", 6: "Left step's top", 7: "Right step's top"}
FEET = ("Bip01 L Foot", "Bip01 R Foot")
FOOT_TYPES = (2, 3, 4, 5, 6, 7)
PLANTED = 1.0   # m/s; a foot slower than this is planted
LIFT = 0.03     # m; a foot that rises less than this between plants shuffled, not stepped


def foot_tags(obj, action, planted=PLANTED, lift=LIFT):
    """[(type, begin s, end s)] of the footstep tags the action's foot motion
    gives, tagged as the game's clips are: each foot planted (4, 5) while
    slower than `planted`, swinging (2, 3) otherwise, and lifting (6, 7) for
    one frame where a swing starts. Plays the action on `obj`."""
    scene = bpy.context.scene
    keep = obj.animation_data.action, scene.frame_current
    obj.animation_data.action = action
    n = max(1, int(round(action.frame_range[1])))
    pos = {b: [] for b in FEET}
    for f in range(n + 1):
        scene.frame_set(f)
        for b in FEET:
            pos[b].append((obj.matrix_world @ obj.pose.bones[b].head).copy())
    obj.animation_data.action = keep[0]
    scene.frame_set(keep[1])
    out = []
    for side, b in enumerate(FEET):
        p = pos[b]
        speed = [(p[min(f + 1, n)] - p[max(f - 1, 0)]).length * FPS / (min(f + 1, n) - max(f - 1, 0))
                 for f in range(n + 1)]
        down = [s < planted for s in speed]
        # A one-frame flicker is noise, not a step.
        for f in range(1, n):
            if down[f - 1] == down[f + 1] != down[f]:
                down[f] = down[f - 1]
        f = 0
        while f <= n:
            g = f
            while g + 1 <= n and down[g + 1] == down[f]:
                g += 1
            if not down[f] and max(q.z for q in p[f:g + 1]) - min(p[f].z, p[g].z) < lift:
                down[f:g + 1] = [True] * (g + 1 - f)
            f = g + 1
        f = 0
        while f <= n:
            g = f
            while g + 1 <= n and down[g + 1] == down[f]:
                g += 1
            end = g + 1 if g < n else g
            out.append((4 + side if down[f] else 2 + side, f / FPS, end / FPS))
            if not down[f]:
                top = max(range(f, g + 1), key=lambda i: p[i].z)
                out.append((6 + side, top / FPS, (top + 1) / FPS))
            f = g + 1
    return sorted(out, key=lambda t: (t[1], t[0]))


def tag_footsteps(obj, action, planted=PLANTED, lift=LIFT):
    """Replace the action's footstep tags (types 2 to 7) with ones from its
    foot motion; the other types stay. Returns how many it wrote."""
    tags = foot_tags(obj, action, planted, lift)
    m = action.cd_meta
    kept = [(e.begin, e.end, e.type) for e in m.events if e.type not in FOOT_TYPES]
    m.events.clear()
    for begin, end, t in sorted(kept + [(b, e, t) for t, b, e in tags]):
        e = m.events.add()
        e.begin, e.end, e.type = begin, end, t
    m.loaded = True
    return len(tags)


def scale(action, factor):
    """Stretch every event and phase time by `factor`, onto half frames."""
    snap = lambda t: round(t * factor * FPS * 2.0) / 2.0 / FPS  # noqa: E731
    for e in action.cd_meta.events:
        e.begin, e.end = snap(e.begin), snap(e.end)
    for p in action.cd_meta.phases:
        p.t0, p.t1 = snap(p.t0), snap(p.t1)
