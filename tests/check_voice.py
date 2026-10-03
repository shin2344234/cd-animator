"""Check voice lines: the Wwise to Ogg conversion and the voice strip.

    blender -b --factory-startup --python tests/check_voice.py -- [game folder]

Needs the game installed with English voice. It requires:

  * the voice index to hold more than 50,000 English lines;
  * 200 random English lines to convert to Ogg Vorbis that Blender's own
    audio library decodes to exactly the line's sample count;
  * the voice of each of those lines with a lip sync clip of the same name
    to last as long as the clip plus up to 0.1 s on 95% of them (clips end
    on a whole frame, and the voice runs on a median 51 ms);
  * Kliff with an idle and one of his lines to get a sound strip from frame
    0 holding that line, the scene to play in step with the sound, and
    Remove facial clip to take the strip out again;
  * a French line, with no French voice installed, to warn and add nothing;
  * an English line with no English voice file but a Korean one to point to
    the Korean lip sync clip, and a line voiced in no installed language to
    say so.

Exit code 0 means every check passed.
"""

import os
import random
import sys
import time

import aud
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cd_animator  # noqa: E402
from cd_animator import anim, packs, voice  # noqa: E402
from cd_animator.formats import paa_codec, paz, wwise  # noqa: E402

KLIFF = "cd_phm_macduff_00000"
IDLE = "1_pc/1_phm/cd_phm_basic_00_00_nor_std_idle_00"
LINE = "1_pc/1_phm/99_autofacial/english(us)/unique_kliff_aidialogstringinfo_minigame_idle_43226"
FRENCH = "1_pc/1_phm/99_autofacial/french/unique_kliff_15286332413776243713"


def report(ok, what):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    sys.stdout.flush()
    return not ok


def samples(path):
    return len(aud.Sound(path).data())


def check_conversion(idx):
    fails = 0
    t = time.time()
    lines = voice.voices(idx)
    took = time.time() - t
    english = sorted(k for k in lines if k.startswith("english(us)/"))
    fails += report(len(english) > 50000, f"voice index: {len(lines)} lines in {voice.languages(idx)}, "
                                          f"{len(english)} English, read in {took:.1f} s")

    random.seed(7)
    pick = random.sample(english, 200)
    out = os.path.join(packs.cache_root(), "voice_check")
    os.makedirs(out, exist_ok=True)
    bad, slow = [], 0.0
    for key in pick:
        data = paz.read(lines[key])
        t = time.time()
        try:
            ogg = wwise.convert(data)
        except wwise.WemError as exc:
            bad.append(f"{key}: {exc}")
            continue
        slow = max(slow, time.time() - t)
        path = os.path.join(out, "line.ogg")
        with open(path, "wb") as f:
            f.write(ogg)
        _ch, _rate, count = wwise.info(data)
        got = samples(path)
        if got != count:
            bad.append(f"{key}: {got} samples decoded, {count} in the file")
    fails += report(not bad, f"200 English lines converted, decoded to their sample counts, slowest "
                             f"{slow * 1000:.0f} ms; {len(bad)} wrong {bad[:3]}")

    clips = {c.rsplit("/", 1)[-1]: c for c in idx.clips if "/99_autofacial/english(us)/" in c}
    diffs = []
    for key in pick:
        clip = clips.get(key.split("/", 1)[1])
        if clip is None:
            continue
        _c, td = paa_codec.decode_file(paz.read(idx.by_path[packs.MOTION + clip + ".paa"]))
        _ch, rate, count = wwise.info(paz.read(lines[key]))
        diffs.append(count / rate - td.lead.duration)
    within = sum(1 for d in diffs if 0.0 <= d <= 0.1)
    fails += report(diffs and within >= 0.95 * len(diffs),
                    f"{len(diffs)} of them have a lip sync clip; on {within} the voice runs 0 to 0.1 s past it, "
                    f"from {min(diffs, default=0):+.3f} to {max(diffs, default=0):+.3f} s")
    return fails


def check_kliff():
    fails = 0
    bpy.ops.cd_animator.game_character(character=KLIFF, textures=False, cloth=False, gear="NONE", clip=IDLE,
                                       face=LINE)
    arm = bpy.context.view_layer.objects.active
    scene = bpy.context.scene
    strip = voice.strip_of(scene, arm)
    length = samples(bpy.path.abspath(strip.sound.filepath)) / 48000 if strip else 0.0
    face = anim.face_action(arm)
    fails += report(strip is not None and strip.frame_start == 0 and strip.get("cd_voice_line") == LINE.rsplit("/", 1)[-1]
                    and scene.sync_mode == "AUDIO_SYNC" and face is not None
                    and 0.0 <= length - face["cd_duration"] <= 0.1,
                    f"Kliff speaking: strip {strip.name if strip else None} from frame "
                    f"{strip.frame_start if strip else None}, {length:.3f} s of voice for a "
                    f"{face['cd_duration'] if face else 0:.3f} s clip, sync {scene.sync_mode}")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.cd_animator.game_clip(clip=FRENCH)
    kept = voice.strip_of(scene, arm)
    fails += report(kept is not None and kept.get("cd_voice_line") == LINE.rsplit("/", 1)[-1],
                    "a French line with no French voice installed leaves the English strip and warns")

    bpy.ops.cd_animator.remove_face()
    ed = scene.sequence_editor
    fails += report(voice.strip_of(scene, arm) is None and not any(s.name == f"{arm.name} voice" for s in ed.strips),
                    f"Remove facial clip takes the voice out; {len(ed.strips)} strips left")
    return fails


def check_missing(idx):
    lines = voice.voices(idx)
    english = [c for c in idx.clips if "/1_phm/99_autofacial/english(us)/" in c]
    korean_only = next(c for c in english if "english(us)/" + c.rsplit("/", 1)[-1] not in lines
                       and voice.elsewhere(idx, c))
    nowhere = next(c for c in english if "english(us)/" + c.rsplit("/", 1)[-1] not in lines
                   and not voice.elsewhere(idx, c))
    arm = bpy.context.view_layer.objects.active
    strip, note = voice.add_for_clip(bpy.context, idx, arm, korean_only)
    other = voice.elsewhere(idx, korean_only)[0][1]
    strip2, note2 = voice.add_for_clip(bpy.context, idx, arm, nowhere)
    return report(strip is None and other in note and strip2 is None and "any installed language" in note2,
                  f"unvoiced English lines: {note!r}; {note2!r}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cd_animator.register()
    if argv:
        packs.game_folder = lambda context=None: argv[0]
    idx = packs.index()
    fails = check_conversion(idx)
    fails += check_kliff()
    fails += check_missing(idx)
    print("PASS" if not fails else f"FAIL: {fails} checks")
    sys.stdout.flush()
    os._exit(1 if fails else 0)


main()
