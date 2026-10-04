"""New clips and clip lengths.

Every clip is written against a template, a shipped clip whose header, lead,
bone layout and metadata it keeps (export.py). A new clip is a template
imported under a new name, either keeping the template's motion or holding
its first frame, at a length of its own. Its events and phases come along
and can be stretched to the new length.
"""

import json

from mathutils import Quaternion

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


def make_loop(context, obj, action, overlap):
    """Fold the clip's last `overlap` frames into its first, so it ends on
    the pose it starts with and loops without a seam. Frame t, up to
    `overlap`, takes the pose from frame end - overlap + t and eases into
    its own; the clip then ends at end - overlap, on the pose frame 0 now
    has. The motion runs on through the seam instead of slowing to a held
    pose."""
    if action.get("cd_lod"):
        raise ValueError("a LOD clip follows its full clip; loop the full clip instead")
    end = int(action.frame_end)
    if overlap < 1 or end < 2 * overlap:
        raise ValueError(f"a {end} frame clip is too short to fold {overlap} frames into its start")
    tail = end - overlap
    channels = {}
    for fc in _curves(obj, action):
        channels.setdefault(fc.data_path, {})[fc.array_index] = fc
    for path, fcs in channels.items():
        order = sorted(fcs)
        quat = path.endswith("rotation_quaternion") and order == [0, 1, 2, 3]
        rows = []
        for t in range(overlap + 1):
            w = t / overlap
            w = w * w * (3 - 2 * w)
            a = [fcs[i].evaluate(tail + t) for i in order]
            b = [fcs[i].evaluate(t) for i in order]
            if quat:
                qa, qb = Quaternion(a), Quaternion(b)
                if qa.dot(qb) < 0:
                    qa.negate()
                rows.append(list(qa.slerp(qb, w)))
            else:
                rows.append([x + (y - x) * w for x, y in zip(a, b)])
        for i, column in zip(order, zip(*rows)):
            fc = fcs[i]
            if all(abs(v - fc.evaluate(t)) < 1e-7 for t, v in enumerate(column)):
                continue
            for t, v in enumerate(column):
                fc.keyframe_points.insert(t, v, options={"REPLACE", "FAST"}).interpolation = "LINEAR"
            fc.update()
    set_length(context, obj, action, tail)


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
