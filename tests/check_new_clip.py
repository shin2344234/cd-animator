"""Check new clips, clip lengths and event editing.

    blender -b --factory-startup --python tests/check_new_clip.py -- <samples folder>

1. A new clip from Kliff's left broom dismount (70 frames, events and two
   phases), cut to 35 frames with its events stretched: the clip, its LOD
   and its metadata must all say 35 frames, no key may lie past the end, and
   every event and phase time must be half the template's, on a half frame.
2. A new clip holding the first frame of Kliff's standing idle for 45
   frames must pose every bone at frame 45 exactly as at frame 0.
3. An event added in Blender must be in the exported metadata, in order.
4. Lengthening an imported clip keeps its keys and moves only the end.
Exit code 0 means every check passed.
"""

import os
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import clip, export  # noqa: E402
from cd_animator.formats import metabin_codec, paa_codec  # noqa: E402

DISMOUNT = "cd_phm_rd_broom_basic_00_00_nor_std_dismount_l_00"
IDLE = "cd_phm_basic_00_00_nor_std_idle_00"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    return not ok


def kliff(folder):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.cd_animator.import_pab(filepath=os.path.join(folder, "phm_01.pab"))
    return bpy.context.object


def last_key(td):
    return max((k.frame * (6 if b.kind == paa_codec.KIND_I8 else 1)
                for b in td.bones for k in b.rot_keys + b.pos_keys), default=0)


def check_cut(folder, out):
    obj = kliff(folder)
    src = os.path.join(folder, DISMOUNT + ".paa")
    meta_src = os.path.join(os.path.dirname(folder), "actionchart", DISMOUNT + ".paa_metabin")
    old = metabin_codec.read_metabin(open(meta_src, "rb").read())
    action = clip.new_clip(bpy.context, obj, src, "dismount_half", 35)
    written, _p = export.export_with_companions(obj, action, os.path.join(out, "dismount_half.paa"))
    _c, full = paa_codec.decode_file(open(written[0], "rb").read())
    _l, lod = paa_codec.decode_file(open(written[1], "rb").read())
    mb = metabin_codec.read_metabin(open(written[2], "rb").read())
    f = 0
    f += report(round(full.lead.duration * 30) == 35 and round(lod.lead.duration * 30) == 35
                and round(mb.duration * 30) == 35, f"cut: clip, LOD and metadata all 35 frames "
                f"({full.lead.duration * 30:.2f}, {lod.lead.duration * 30:.2f}, {mb.duration * 30:.2f})")
    f += report(last_key(full) <= 35, f"cut: last key at frame {last_key(full)}")
    half = lambda t: round(t * 0.5 * 60) / 60  # noqa: E731
    want = sorted((half(e.begin), half(e.end), e.type) for e in old.events)
    got = sorted((e.begin, e.end, e.type) for e in mb.events)
    close = len(want) == len(got) and all(abs(a - c) < 1e-5 and abs(b - d) < 1e-5 and t == u
                                          for (a, b, t), (c, d, u) in zip(want, got))
    f += report(close, f"cut: {len(got)} events at half their times")
    phases = len(mb.phases) == len(old.phases) and all(
        abs(n.t0 - half(o.t0)) < 1e-5 and abs(n.t1 - half(o.t1)) < 1e-5 and (n.a, n.b) == (o.a, o.b)
        for n, o in zip(mb.phases, old.phases))
    f += report(phases, f"cut: {len(mb.phases)} phases at half their times")
    return f


def check_hold(folder, out):
    obj = kliff(folder)
    action = clip.new_clip(bpy.context, obj, os.path.join(folder, IDLE + ".paa"), "idle_hold", 45, hold=True)
    written, _p = export.export_with_companions(obj, action, os.path.join(out, "idle_hold.paa"))
    obj2 = kliff(folder)
    from cd_animator import anim
    anim.import_clip(bpy.context, obj2, written[0])
    poses = {}
    for frame in (0, 45):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        poses[frame] = {pb.name: pb.matrix.copy() for pb in obj2.pose.bones}
    worst = max((poses[0][n].translation - poses[45][n].translation).length for n in poses[0])
    return report(worst < 1e-6, f"hold: frame 45 matches frame 0 within {worst:.1e} m")


def check_event(folder, out):
    obj = kliff(folder)
    action = clip.new_clip(bpy.context, obj, os.path.join(folder, IDLE + ".paa"), "idle_event", 60)
    e = action.cd_meta.events.add()
    e.begin_frame, e.end_frame, e.type = 12.5, 20, 3
    written, _p = export.export_with_companions(obj, action, os.path.join(out, "idle_event.paa"))
    mb = metabin_codec.read_metabin(open(written[2], "rb").read())
    found = [(round(x.begin * 30, 2), round(x.end * 30, 2), x.type) for x in mb.events]
    ordered = [x.begin for x in mb.events] == sorted(x.begin for x in mb.events)
    return report((12.5, 20.0, 3) in found and ordered, f"event: added event in the metadata, in order ({found})")


def check_lengthen(folder, out):
    obj = kliff(folder)
    from cd_animator import anim
    src = os.path.join(folder, IDLE + ".paa")
    action, _u = anim.import_clip(bpy.context, obj, src)
    clip.set_length(bpy.context, obj, action, 300)
    written, _p = export.export_with_companions(obj, action, os.path.join(out, "idle_long.paa"))
    _c, td = paa_codec.decode_file(open(written[0], "rb").read())
    _c, old = paa_codec.decode_file(open(src, "rb").read())
    same = [(b.name_hash, len(b.rot_keys), len(b.pos_keys)) for b in td.bones] == \
           [(b.name_hash, len(b.rot_keys), len(b.pos_keys)) for b in old.bones]
    return report(round(td.lead.duration * 30) == 300 and same,
                  f"lengthen: 300 frames ({td.lead.duration * 30:.1f}), every track's keys kept")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    folder = argv[0] if argv else os.path.join(os.path.dirname(HERE), "samples", "character")
    cd_animator.register()
    out = tempfile.mkdtemp(prefix="cd_new_clip_")
    failures = check_cut(folder, out) + check_hold(folder, out) + check_event(folder, out) + check_lengthen(folder, out)
    print("PASS" if not failures else f"FAIL: {failures} checks")
    sys.stdout.flush()
    os._exit(1 if failures else 0)


main()
