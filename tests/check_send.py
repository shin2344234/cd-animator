"""Check Send to game against a stand-in bin64 folder.

    blender -b --factory-startup --python tests/check_send.py -- [game folder]

Needs the game installed, to build Kliff; it writes only to a temporary
folder that stands in for the game's bin64. It requires:

  * Send to game to refuse, naming the loader, when CDAnimator.asi is not
    in bin64;
  * Kliff's unchanged idle and his unchanged angry face to go in as three
    files each, named as the game's, byte for byte what Export writes, and
    the clip and its metadata byte for byte the game's own (Export makes
    its own _lod.paa);
  * a clip imported a second time, which Blender names .001, to keep the
    game's name, and a new clip to go in under the name it was given;
  * a same-named file already in a subfolder to stop the send with nothing
    written, since the loader would take that one;
  * the log reading to call a clip the game took "played", one it found at
    startup "ready", and one changed since the session started "waiting";
  * Take out of the game to delete exactly that clip's files.

Exit code 0 means every check passed.
"""

import os
import shutil
import sys
import tempfile
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import clip as clipmod  # noqa: E402
from cd_animator import export, ingame, packs  # noqa: E402
from cd_animator.formats import paz  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
FACE = "1_pc/1_phm/99_facial/99_emotion/f_cd_phm_emo_anger_00_0001_kliff"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def game_files(idx, clip):
    name = clip.rsplit("/", 1)[-1]
    return {name + ".paa": paz.read(idx.by_path[packs.MOTION + clip + ".paa"]),
            name + "_lod.paa": paz.read(idx.by_path[packs.MOTION_LOD + clip + "_lod.paa"]),
            name + ".paa_metabin": paz.read(idx.by_path[packs.ANIMMETA + clip + ".paa_metabin"])}


def same(root, files):
    ok = True
    for n, data in files.items():
        p = os.path.join(root, n)
        if not os.path.isfile(p) or open(p, "rb").read() != data:
            print(f"    differs: {n} ({os.path.getsize(p) if os.path.isfile(p) else None} bytes against {len(data)})")
            ok = False
    return ok


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = 0
    tmp = tempfile.mkdtemp(prefix="cd_send_")
    b64 = os.path.join(tmp, "bin64")
    os.makedirs(b64)
    ingame.bin64 = lambda context=None: b64
    root = os.path.join(b64, ingame.FOLDER)

    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, sway=False, gear="NONE",
                                       clip=IDLE, face=FACE)
    arm = bpy.context.view_layer.objects.active
    try:
        bpy.ops.cd_animator.send_to_game(clip="ACTION")
        refused = False
    except RuntimeError as exc:
        refused = "CDAnimator.asi" in str(exc)
    fails += report(refused and not os.path.isdir(root), "no loader in bin64: Send to game refuses and names it")

    open(os.path.join(b64, ingame.LOADER), "wb").close()
    bpy.ops.cd_animator.send_to_game(clip="ACTION")
    bpy.ops.cd_animator.send_to_game(clip="FACE")
    body, face = game_files(idx, IDLE), game_files(idx, FACE)
    exported = os.path.join(tmp, "export")
    os.makedirs(exported)
    for which in ("ACTION", "FACE"):
        action = cd_animator.CDANIM_OT_export_paa._action(arm, which)
        export.export_with_companions(arm, action, os.path.join(exported, ingame.clip_name(action) + ".paa"))
    as_export = {n: open(os.path.join(exported, n), "rb").read() for n in os.listdir(exported)}
    own = {n: d for n, d in {**body, **face}.items() if not n.endswith("_lod.paa")}
    listed = sorted(ingame.sent(root))
    fails += report(same(root, as_export) and same(root, own) and len(os.listdir(root)) == 6,
                    f"idle and face sent as Export writes them, clip and metadata the game's own: {listed}")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=IDLE)
    again = arm.animation_data.action
    name_again = ingame.clip_name(again)
    template = packs.fetch_clip(idx, IDLE)
    new = clipmod.new_clip(bpy.context, arm, template, "cd_phm_test_new_idle_00", 60)
    fails += report(again.name != name_again and name_again == IDLE.rsplit("/", 1)[-1]
                    and ingame.clip_name(new) == "cd_phm_test_new_idle_00",
                    f"re-imported {again.name} goes in as {name_again}; the new clip as {ingame.clip_name(new)}")

    sub = os.path.join(root, "older")
    os.makedirs(sub)
    shutil.copy(os.path.join(root, "cd_phm_basic_00_00_nor_std_idle_00.paa"), sub)
    before = {n: os.path.getmtime(os.path.join(root, n)) for n in os.listdir(root) if n != "older"}
    try:
        bpy.context.view_layer.objects.active = arm
        bpy.ops.cd_animator.game_clip(clip=IDLE)
        ingame.send(arm, arm.animation_data.action, root, True)
        stopped = False
    except ingame.SendError as exc:
        stopped = "older" in str(exc)
    after = {n: os.path.getmtime(os.path.join(root, n)) for n in os.listdir(root) if n != "older"}
    shutil.rmtree(sub)
    fails += report(stopped and before == after, "a same-named file in a subfolder stops the send, nothing written")

    time.sleep(1.2)
    with open(os.path.join(b64, ingame.LOG), "w", encoding="utf-8") as f:
        for n in sorted(os.listdir(root)):
            size = os.path.getsize(os.path.join(root, n))
            f.write(f"[10:00:00.001] [info ] [folder] CDAnimator/{n} ({size} bytes) goes in for the game's file of "
                    "that name.\n")
        f.write("[10:00:05.000] [info ] [files] character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa "
                "is the plugin's (35796 bytes).\n")
    states = {n: s for n, _f, (s, _w) in ingame.status(root, ingame.read_log(b64))}
    time.sleep(1.2)
    os.utime(os.path.join(root, FACE.rsplit("/", 1)[-1] + ".paa"))
    later = {n: s for n, _f, (s, _w) in ingame.status(root, ingame.read_log(b64))}
    idle_name, face_name = IDLE.rsplit("/", 1)[-1], FACE.rsplit("/", 1)[-1]
    fails += report(states.get(idle_name) == "played" and states.get(face_name) == "ready"
                    and later.get(face_name) == "waiting" and later.get(idle_name) == "played",
                    f"log: {states}; after the face changes: {later}")

    gone = ingame.remove(root, face_name)
    left = sorted(os.listdir(root))
    fails += report(len(gone) == 3 and left == sorted(body), f"took the face out ({len(gone)} files); left {left}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
