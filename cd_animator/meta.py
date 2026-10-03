"""A clip's metadata on its action: the events and phases of its .paa_metabin.

Events are timed tags the action charts react to, a begin and an end in
seconds and a type from 0 to 7 whose meanings are not known. Phases are timed
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
    type: IntProperty(name="Type", min=0, max=255, description="What the event signals; 0 to 7 in the game's clips")
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


def scale(action, factor):
    """Stretch every event and phase time by `factor`, onto half frames."""
    snap = lambda t: round(t * factor * FPS * 2.0) / 2.0 / FPS  # noqa: E731
    for e in action.cd_meta.events:
        e.begin, e.end = snap(e.begin), snap(e.end)
    for p in action.cd_meta.phases:
        p.t0, p.t1 = snap(p.t0), snap(p.t1)
