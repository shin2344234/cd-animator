"""Write a Blender action on a Crimson Desert armature back to a .paa clip.

Every clip is written against a template: the file it was imported from,
whose header and lead are kept and whose block order new bones are fitted
into. An action that was imported and not edited comes out byte for byte
the same as its source, which tests/check_export.py checks on all 44 riding
clips.
"""

import json
import os

from bpy_extras import anim_utils

from . import convert
from .anim import FPS, frame_step
from .formats import metabin_codec, paa_codec


class ExportError(Exception):
    pass


def _channelbag(obj, action):
    ad = obj.animation_data
    slot = ad.action_slot if ad and ad.action == action and ad.action_slot else None
    if slot is None:
        slot = next((s for s in action.slots if s.target_id_type == "OBJECT"), None)
    if slot is None:
        return None
    return anim_utils.action_get_channelbag_for_slot(action, slot)


def _bone_curves(bag):
    """{bone name: {"rot": {index: fcurve}, "pos": {index: fcurve}}}"""
    out = {}
    for fc in bag.fcurves if bag else ():
        path = fc.data_path
        if not path.startswith('pose.bones["'):
            continue
        name, _, prop = path[len('pose.bones["'):].partition('"].')
        kind = {"rotation_quaternion": "rot", "location": "pos"}.get(prop)
        if kind is None:
            continue
        out.setdefault(name, {"rot": {}, "pos": {}})[kind][fc.array_index] = fc
    return out


def _frames(curves, step, bone, problems):
    """Sorted integer frames to write for one channel: the frames that hold a
    key on any of its curves, or every frame (every tick in LOD section 1)
    from the first key to the last when a curve bends between keys, since
    the game only interpolates in straight lines."""
    found = set()
    curved = False
    for fc in curves.values():
        pts = fc.keyframe_points
        for i, p in enumerate(pts):
            found.add(p.co[0])
            if i < len(pts) - 1 and p.interpolation != "LINEAR":
                curved = True
    if curved and found:
        first, last = round(min(found)), round(max(found))
        problems.append(f"{bone}: keys are not linear, sampled every {'tick' if step > 1 else 'frame'} from {first} to {last}")
        first = -(-first // step) * step
        return list(range(first, last + 1, step))
    frames = []
    for f in sorted(found):
        r = round(f)
        if abs(f - r) > 1e-3:
            problems.append(f"{bone}: key at frame {f:.2f} moved to {r}, clips hold whole frames")
        if r % step:
            problems.append(f"{bone}: key at frame {r} is not on a 1/5 s tick of a LOD clip, moved to {round(r / step) * step}")
        frames.append(round(r / step) * step)
    return sorted(set(frames))


def _value(fc, frame, default):
    """The curve's value at `frame`, read from the key itself when there is
    one so stored numbers pass through untouched."""
    if fc is None:
        return default
    for p in fc.keyframe_points:
        if abs(p.co[0] - frame) < 1e-3:
            return p.co[1]
    return fc.evaluate(frame)


def build_track_data(obj, action):
    """-> (container, TrackData, problems) for `action` on armature `obj`."""
    if "cd_source" not in action:
        raise ExportError(f"{action.name} was not imported from a clip, so it has no template to write against")
    try:
        with open(action["cd_source"], "rb") as f:
            template_bytes = f.read()
    except OSError as exc:
        raise ExportError(f"cannot read the template clip {action['cd_source']}: {exc}")
    container, template = paa_codec.decode_file(template_bytes)
    lod = template.lod
    blocks = json.loads(action["cd_blocks"])
    curves = _bone_curves(_channelbag(obj, action))
    problems = []

    # New bones (keyed now, absent from the template) go into section 1 after
    # the last template bone that comes before them in the skeleton.
    known = {b["name"] for b in blocks if b["name"]}
    bones = obj.data.bones
    for name in sorted((n for n in curves if n not in known and n in bones),
                       key=lambda n: bones[n]["cd_index"]):
        idx = bones[name]["cd_index"]
        pos = 0
        for i, b in enumerate(blocks):
            if b["section"] == 1 and b["name"] and bones[b["name"]]["cd_index"] < idx:
                pos = i + 1
        blocks.insert(pos, {"hash": paa_codec.bone_hash(name), "name": name, "section": 1,
                            "flags": 0, "aux": 0, "neg": []})
        problems.append(f"{name}: not in the template, added as a new track")

    template_tracks = {b.name_hash: b for b in template.bones}
    tracks = []
    for b in blocks:
        name = b["name"]
        if name is None:
            # a bone this skeleton does not have: carry the template's track over
            tracks.append(template_tracks[b["hash"]])
            continue
        c = curves.get(name, {"rot": {}, "pos": {}})
        axis = bones[name]["cd_axis"]
        neg = set(b["neg"])
        step = frame_step(lod, b["section"])

        rot_keys = []
        for f in _frames(c["rot"], step, name, problems):
            q = [_value(c["rot"].get(i), f, d) for i, d in enumerate((1.0, 0.0, 0.0, 0.0))]
            if f in neg:
                q = [-v for v in q]
            x, y, z, w = convert.basis_to_key(axis, q, (0.0, 0.0, 0.0))[0]
            rot_keys.append(paa_codec.RotKey(f // step, x, y, z, w))

        pos_keys = []
        for f in _frames(c["pos"], step, name, problems):
            t = [_value(c["pos"].get(i), f, 0.0) for i in range(3)]
            x, y, z = convert.basis_to_key(axis, (1.0, 0.0, 0.0, 0.0), t)[1]
            pos_keys.append(paa_codec.PosKey(f // step, x, y, z, b["aux"]))

        if not rot_keys and not pos_keys:
            problems.append(f"{name}: no keys left, the bone stays on its bind pose")
            continue
        sec = b["section"]
        if lod and sec == 1:
            rf, pf = paa_codec.ROT_I8, paa_codec.POS_I8
        else:
            rf = paa_codec.ROT_HALF
            pf = paa_codec.POS_F32 if (sec == 2 and not lod) else paa_codec.POS_HALF
        tracks.append(paa_codec.BoneTrack(
            name, b["hash"], b["flags"], rot_keys, pos_keys, pf == paa_codec.POS_F32,
            pos_keys[0].aux if pos_keys and pf == paa_codec.POS_F32 else 0, sec, rf, pf))

    lead = template.lead
    duration = action["cd_duration"]
    if int(action.frame_end) != round(duration * FPS):
        duration = action.frame_end / FPS
    td = paa_codec.TrackData(
        paa_codec.Lead(tuple(action["cd_rec_a"]), tuple(action["cd_rec_b"]), action["cd_ref_scale"],
                       duration, lead.lod_const, lead.lod_zero),
        tracks, lod)

    last = round(duration * FPS)
    for t in tracks:
        step = frame_step(lod, t.section)
        for keys in (t.rot_keys, t.pos_keys):
            # a LOD clip rounds its last tick up (75 frames end on tick 13), past the end
            if keys and keys[-1].frame > -(-last // step):
                raise ExportError(f"{t.name} has a key after the clip's last frame ({last})")
    return container, td, problems


def export_clip(obj, action, path):
    container, td, problems = build_track_data(obj, action)
    data = paa_codec.encode_file(container, td)
    paa_codec.decode_file(data)   # refuse to write anything the reader cannot read back
    with open(path, "wb") as f:
        f.write(data)
    return data, problems


def _companion(source, suffix):
    """A file that goes with the clip at `source`: next to it, or in an
    actionchart folder beside its folder (where paz_unpack puts metabins)."""
    folder, leaf = os.path.split(source)
    stem = leaf[:-len(".paa")] if leaf.lower().endswith(".paa") else leaf
    for candidate in (os.path.join(folder, stem + suffix),
                      os.path.join(os.path.dirname(folder), "actionchart", stem + suffix)):
        if os.path.isfile(candidate):
            return candidate
    return None


def _track(td, name_hash):
    return next((b for b in td.bones if b.name_hash == name_hash), None)


def _same_keys(a, b):
    key = lambda k: (k.frame, k.x, k.y, k.z, getattr(k, "w", 0.0))  # noqa: E731
    return (a is None) == (b is None) and (a is None or (
        [key(k) for k in a.rot_keys] == [key(k) for k in b.rot_keys]
        and [key(k) for k in a.pos_keys] == [key(k) for k in b.pos_keys]))


def build_metabin(template_clip, template_metabin, clip):
    """The .paa_metabin for `clip` (full clip bytes). Events, phases and the
    two unexplained bytes come from the template clip's metabin, so a clip
    that keeps its template's timing keeps its state changes. The motion
    block is the clip's B_MoveControl_01 track; when that track is the
    template's, the template's block is kept as it is."""
    _c, new = paa_codec.decode_file(clip)
    _t, old = paa_codec.decode_file(template_clip)
    move = paa_codec.bone_hash("B_MoveControl_01")
    new_move, old_move = _track(new, move), _track(old, move)
    if template_metabin is not None:
        mb = metabin_codec.read_metabin(template_metabin)
    else:
        mb = metabin_codec.new_metabin(new.lead.duration)
    if not _same_keys(new_move, old_move):
        mb.motion = None if new_move is None else metabin_codec.MotionTrack(
            [paa_codec.RotKey(k.frame, k.x, k.y, k.z, k.w) for k in new_move.rot_keys],
            [paa_codec.PosKey(k.frame, k.x, k.y, k.z) for k in new_move.pos_keys])
        mb.flags = mb.expected_flags()
    mb.duration = new.lead.duration
    return metabin_codec.write_metabin(mb)


def export_with_companions(obj, action, path):
    """Write the clip at `path`, plus `<stem>_lod.paa` and `<stem>.paa_metabin`
    beside it, the three files the game loads for one clip. Returns
    (written paths, problems)."""
    data, problems = export_clip(obj, action, path)
    written = [path]
    if action.get("cd_lod"):
        return written, problems
    source = action["cd_source"]
    stem = path[:-len(".paa")] if path.lower().endswith(".paa") else path

    template_lod = _companion(source, "_lod.paa")
    if template_lod is None:
        problems.append("no _lod.paa beside the template clip, so the LOD uses Kliff's bone list")
    paa_codec.register_names([b.name for b in obj.data.bones])
    lod = paa_codec.make_lod(data, open(template_lod, "rb").read() if template_lod else None)
    paa_codec.decode_file(lod)
    with open(stem + "_lod.paa", "wb") as f:
        f.write(lod)
    written.append(stem + "_lod.paa")

    template_mb = _companion(source, ".paa_metabin")
    if template_mb is None:
        problems.append("no .paa_metabin found for the template clip, so the new one has no events")
    with open(source, "rb") as f:
        template_clip = f.read()
    mb = build_metabin(template_clip, open(template_mb, "rb").read() if template_mb else None, data)
    metabin_codec.read_metabin(mb)
    with open(stem + ".paa_metabin", "wb") as f:
        f.write(mb)
    written.append(stem + ".paa_metabin")
    return written, problems
