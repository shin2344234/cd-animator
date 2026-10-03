"""Check Seen in game: reading the clips the game played from the loader's log.

    blender -b --factory-startup --python tests/check_seen.py -- [game folder]

Needs the game installed, to build Kliff; the log and ini it reads are
written to a temporary folder that stands in for the game's bin64. It
requires:

  * the log to come back as its blocks, split at the loader's "no new clip"
    markers, with each block's time and the pause before it, the first block
    marked as the game's start, blends and LOD copies left out, and a block
    after midnight dated the next day;
  * the clip logging switch to read LogClips from the ini, and turning it on
    to change only that line, keeping the file's other lines and its CRLF
    line ends;
  * Kliff's armature to list its clips from 1_pc/1_phm/;
  * a body clip and a facial clip picked from the blocks to import onto
    Kliff, the facial one onto his face over the body clip.

Exit code 0 means every check passed.
"""

import datetime
import os
import shutil
import sys
import tempfile

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import anim, ingame, packs  # noqa: E402

M = "character/motion/"
LOG = f"""[23:59:50.100] [info ] [mod] CD Animator Loader 0.1.0 for Crimson Desert 2.03.02 (exe 1.0.0.2976).
[23:59:51.000] [info ] [clip] {M}1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.paa
[23:59:51.000] [info ] [clip] {M}1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.motionblending
[23:59:51.001] [info ] [clip] {M}motion_lod__/1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00_lod.paa
[23:59:51.002] [info ] [clip] {M}2_mon/cd_m0002_00_fourfeet/cd_m0002_00_racoon/00_mon/cd_racoon_basic_00_00_nor_std_wait_00.paa
[23:59:58.000] [info ] [clip] ---- 4.7 s with no new clip ----
[23:59:58.000] [info ] [clip] {M}1_pc/1_phm/cd_kliff_basic_00_00_nor_so_std_idle_desert_stt_00.paa
[23:59:59.500] [info ] [files] {M}1_pc/1_phm/cd_kliff_basic_00_00_nor_so_std_idle_desert_stt_00.paa is the plugin's (100 bytes).
[00:00:03.000] [info ] [clip] ---- 3.5 s with no new clip ----
[00:00:03.000] [info ] [clip] {M}1_pc/1_phm/cd_kliff_basic_00_00_nor_so_std_idle_desert_ing_00.paa
[00:00:03.001] [info ] [clip] {M}1_pc/1_phm/99_facial/00_action/f_cd_phm_act_wait_00_0001_kliff.paa
[00:00:09.000] [info ] [clip] ---- 6.0 s with no new clip ----
[00:00:09.000] [info ] [clip] {M}1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00.motionblending
"""
INI = ("; CD Animator Loader\r\n;\r\n[settings]\r\n; Log each animation clip.\r\nLogClips=0\r\n"
       "SomethingElse=7\r\n")


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    packs.index()
    fails = 0
    tmp = tempfile.mkdtemp(prefix="cd_seen_")
    b64 = os.path.join(tmp, "bin64")
    os.makedirs(b64)
    with open(os.path.join(b64, ingame.LOG), "w", encoding="utf-8") as f:
        f.write(LOG)
    with open(os.path.join(b64, ingame.INI), "w", encoding="utf-8", newline="") as f:
        f.write(INI)
    ingame.bin64 = lambda context=None: b64

    blocks = ingame.read_clips(b64)
    shape = [(when.strftime("%H:%M:%S"), gap, [c.rsplit("/", 1)[-1] for c in clips]) for when, gap, clips in blocks]
    day0 = blocks[0][0].date() if blocks else None
    fails += report(shape == [("23:59:51", None, ["cd_phm_basic_00_00_nor_std_idle_00",
                                                  "cd_racoon_basic_00_00_nor_std_wait_00"]),
                              ("23:59:58", 4.7, ["cd_kliff_basic_00_00_nor_so_std_idle_desert_stt_00"]),
                              ("00:00:03", 3.5, ["cd_kliff_basic_00_00_nor_so_std_idle_desert_ing_00",
                                                 "f_cd_phm_act_wait_00_0001_kliff"])]
                    and blocks[2][0].date() == day0 + datetime.timedelta(days=1),
                    f"log read as {len(blocks)} blocks: {shape}")

    before = ingame.logging_clips(b64)
    bpy.ops.cd_animator.log_clips()
    text = open(os.path.join(b64, ingame.INI), encoding="utf-8", newline="").read()
    fails += report(before is False and ingame.logging_clips(b64) is True
                    and text == INI.replace("LogClips=0", "LogClips=1"),
                    f"clip logging: off, then on, the rest of the ini unchanged with CRLF ends")

    bpy.ops.cd_animator.game_character(character="cd_phm_macduff_00000", textures=False, cloth=False, sway=False,
                                       gear="NONE")
    arm = bpy.context.view_layer.objects.active
    folder = cd_animator._clip_folder(arm)
    mine = [c for _w, _g, clips in blocks for c in clips if c.lower().startswith(folder or "-")]
    fails += report(folder == "1_pc/1_phm/" and len(mine) == 4, f"Kliff's clips from {folder}: {len(mine)} of 5")

    body = blocks[2][2][0]
    face = blocks[2][2][1]
    bpy.ops.cd_animator.game_clip(clip=body, voice=False)
    bpy.ops.cd_animator.game_clip(clip=face, voice=False)
    active = arm.animation_data.action
    on_face = anim.face_action(arm)
    fails += report(active.name.startswith(body.rsplit("/", 1)[-1]) and on_face is not None
                    and on_face.name.startswith(face.rsplit("/", 1)[-1]),
                    f"picked clips imported: {active.name} on the body, {on_face.name if on_face else None} on the face")

    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
