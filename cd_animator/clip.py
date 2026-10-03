"""New clips and clip lengths.

Every clip is written against a template, a shipped clip whose header, lead,
bone layout and metadata it keeps (export.py). A new clip is a template
imported under a new name, either keeping the template's motion or holding
its first frame, at a length of its own. Its events and phases come along
and can be stretched to the new length.
"""

import json

from . import anim, export, meta
from .anim import FPS


def _curves(obj, action):
    bag = export._channelbag(obj, action)
    return list(bag.fcurves) if bag else []


def _set_end(context, action, frames):
    action.use_frame_range = True
    action.frame_start = 0
    action.frame_end = frames
    action["cd_duration"] = frames / FPS
    context.scene.frame_start = 0
    context.scene.frame_end = frames


def _keep_neg(action, frames):
    """Drop the stored sign flips past the clip's end."""
    blocks = json.loads(action["cd_blocks"])
    for b in blocks:
        b["neg"] = [f for f in b["neg"] if f <= frames]
    action["cd_blocks"] = json.dumps(blocks)


def set_length(context, obj, action, frames, stretch_events=False):
    """Make `action` `frames` long. A shorter clip loses its keys past the
    new end and gets a key on the end holding the pose there; a longer one
    holds its last keys. With `stretch_events`, events and phases scale with
    the length."""
    if action.get("cd_lod"):
        raise ValueError("a LOD clip follows its full clip; change the full clip's length instead")
    if frames < 1:
        raise ValueError("a clip needs at least one frame")
    old = int(action.frame_end)
    if frames < old:
        for fc in _curves(obj, action):
            pts = fc.keyframe_points
            if not len(pts) or pts[-1].co[0] <= frames:
                continue
            value = fc.evaluate(frames)
            keep = [(p.co[0], p.co[1]) for p in pts if p.co[0] < frames] + [(float(frames), value)]
            pts.clear()
            pts.add(len(keep))
            for p, (f, v) in zip(pts, keep):
                p.co = (f, v)
                p.interpolation = "LINEAR"
            fc.update()
        _keep_neg(action, frames)
    if stretch_events and old > 0:
        meta.scale(action, frames / old)
    _set_end(context, action, frames)


def new_clip(context, obj, template, name, frames, hold=False, stretch_events=True):
    """A new action on `obj` from the template clip at `template`, named
    `name`, `frames` long. `hold` keeps every bone on the template's first
    frame for the whole clip; otherwise the template's motion is the
    starting point. Returns the action."""
    action, _unknown = anim.import_clip(context, obj, template, layer=False)
    if action.get("cd_lod"):
        raise ValueError("start a new clip from a full clip, not a _lod.paa")
    old = int(action.frame_end)
    if hold:
        for fc in _curves(obj, action):
            value = fc.evaluate(0)
            pts = fc.keyframe_points
            pts.clear()
            pts.add(2)
            for p, f in zip(pts, (0.0, float(frames))):
                p.co = (f, value)
                p.interpolation = "LINEAR"
            fc.update()
        _keep_neg(action, -1)
        _set_end(context, action, frames)
        if stretch_events and old > 0:
            meta.scale(action, frames / old)
    else:
        set_length(context, obj, action, frames, stretch_events)
    action.name = name
    action["cd_template"] = template
    return action
