"""New clips and clip lengths.

Every clip is written against a template, a shipped clip whose header, lead,
bone layout and metadata it keeps (export.py). A new clip is a template
imported under a new name, either keeping the template's motion or holding
its first frame, at a length of its own. Its events and phases come along
and can be stretched to the new length.
"""

import json

from mathutils import Quaternion

from . import anim, export, meta, retarget
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


ROOTS = [f'pose.bones["{b}"].location' for b in retarget.TRAVEL]
REST = {"rotation_quaternion": [1.0, 0.0, 0.0, 0.0], "location": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}


def travels(obj, action):
    """Whether the clip moves B_MoveControl_01, so the game should move the
    character with it."""
    return any(fc.data_path == ROOTS[0] and len({round(p.co[1], 5) for p in fc.keyframe_points}) > 1
               for fc in _curves(obj, action))


def _channels(obj, action):
    """{data path: {array index: fcurve}} of the clip's curves."""
    out = {}
    for fc in _curves(obj, action):
        out.setdefault(fc.data_path, {})[fc.array_index] = fc
    return out


def _ease(fcs, at, start, goal):
    """Key one channel's curves, {array index: fcurve}, on the frames `at`:
    the t-th eases from start(t) into goal(t), values by index, weighted by
    smoothstep from 0 to 1, the short way between quaternions."""
    order = sorted(fcs)
    quat = order == [0, 1, 2, 3] and fcs[0].data_path.endswith("rotation_quaternion")
    n = len(at) - 1
    if all(start(t) == goal(t) for t in range(n + 1)):
        return   # nothing to blend; a slerp would only normalize the game's not quite unit quaternions
    rows = []
    for t in range(n + 1):
        w = t / n
        w = w * w * (3 - 2 * w)
        a, b = start(t), goal(t)
        if quat:
            qa, qb = Quaternion(a), Quaternion(b)
            if qa.dot(qb) < 0:
                qa.negate()
            rows.append(list(qa.slerp(qb, w)))
        else:
            rows.append([x + (y - x) * w for x, y in zip(a, b)])
    for i, column in zip(order, zip(*rows)):
        fc = fcs[i]
        if all(abs(v - fc.evaluate(f)) < 1e-7 for f, v in zip(at, column)):
            continue
        for f, v in zip(at, column):
            fc.keyframe_points.insert(f, v, options={"FAST"}).interpolation = "LINEAR"
        fc.update()


def make_loop(context, obj, action, overlap):
    """Fold the clip's last `overlap` frames into its first, so it ends on
    the pose it starts with and loops without a seam. Frame t, up to
    `overlap`, takes the pose from frame end - overlap + t and eases into
    its own; the clip then ends at end - overlap, on the pose frame 0 now
    has. The motion runs on through the seam instead of slowing to a held
    pose. In a clip that travels, its B_MoveControl_01 moving, the travel
    bones' frames taken from the end are moved back by the clip's travel,
    so each round goes on from where the last one got to."""
    if action.get("cd_lod"):
        raise ValueError("a LOD clip follows its full clip; loop the full clip instead")
    end = int(action.frame_end)
    if overlap < 1 or end < 2 * overlap:
        raise ValueError(f"a {end} frame clip is too short to fold {overlap} frames into its start")
    tail = end - overlap
    moving = travels(obj, action)
    for path, fcs in _channels(obj, action).items():
        back = {i: fc.evaluate(tail) - fc.evaluate(0) if moving and path in ROOTS else 0.0 for i, fc in fcs.items()}
        _ease(fcs, range(overlap + 1), lambda t: [fcs[i].evaluate(tail + t) - back[i] for i in sorted(fcs)],
              lambda t: [fcs[i].evaluate(t) for i in sorted(fcs)])
    set_length(context, obj, action, tail)


def end_on(obj, action, overlap, pose):
    """Blend the clip's last `overlap` frames into `pose`, {data path:
    values} from anim.first_pose() of what the game plays next, so the clip
    ends where that starts. A channel the pose lacks eases to the bind
    pose, and one the clip lacks holds the bind pose from frame 0 until the
    blend. A clip
    that travels ends as far on: Bip01 eases into the pose moved by its
    travel, and B_MoveControl_01 keeps its keys."""
    if action.get("cd_lod"):
        raise ValueError("a LOD clip follows its full clip; blend the full clip instead")
    end = int(action.frame_end)
    if overlap < 1 or end < overlap:
        raise ValueError(f"a {end} frame clip is too short to blend {overlap} frames")
    start = end - overlap
    moving = travels(obj, action)
    channels = _channels(obj, action)
    bag = export._channelbag(obj, action)
    for path in sorted(set(channels) | set(pose)):
        bone, _, prop = path[len('pose.bones["'):].partition('"].')
        if not path.startswith('pose.bones["') or prop not in REST or bone == retarget.TRAVEL[0]:
            continue
        fcs = channels.get(path)
        if fcs is None:
            fcs = {i: bag.fcurves.new(path, index=i, group_name=bone) for i in range(len(REST[prop]))}
            for i, fc in fcs.items():
                for f in (0, start):   # every track of the game's clips starts on frame 0
                    fc.keyframe_points.insert(f, REST[prop][i]).interpolation = "LINEAR"
        goal = dict(enumerate(pose.get(path, REST[prop])))
        if moving and path in ROOTS:
            goal = {i: g + fcs[i].evaluate(end) - fcs[i].evaluate(0) for i, g in goal.items()}
        _ease(fcs, range(start, end + 1), lambda t: [fcs[i].evaluate(start + t) for i in sorted(fcs)],
              lambda t: [goal[i] for i in sorted(fcs)])


def hold(obj, action, pose, side):
    """Key the hand on `side`, "R" or "L", as `pose` has it, {data path:
    values} from anim.first_pose() of a clip that grips with that hand, for
    the whole clip, one key each: its fingers and Bip_Weapon_<side>, which
    the hand's prop sockets hang from. A clip from motion capture leaves
    that bone at its bind pose, where a prop sits up by the wrist."""
    bag = export._channelbag(obj, action)
    channels = _channels(obj, action)
    for path, values in pose.items():
        bone = path[len('pose.bones["'):].partition('"].')[0]
        if not (bone.startswith(f"Bip01 {side} Finger") or bone == f"Bip_Weapon_{side}"):
            continue
        fcs = channels.get(path) or {i: bag.fcurves.new(path, index=i, group_name=bone) for i in range(len(values))}
        for i, fc in fcs.items():
            fc.keyframe_points.clear()
            fc.keyframe_points.insert(0, values[i]).interpolation = "LINEAR"
            fc.update()


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
