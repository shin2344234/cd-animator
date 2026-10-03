"""Voice lines for the game's lip sync clips.

A lip sync clip is `<skeleton folder>/99_autofacial/<language>/<line>`, and
the line's voice is `sound/windows/<language>/<line>.wem` in a pack group
of that language: 0006 holds English, 0005 Korean, 0035 Chinese on this
install, each about 61,000 lines. The game's Wwise Vorbis files become Ogg
Vorbis (formats/wwise.py), kept in the add-on's cache, and play as a sound
strip in the scene from frame 0, where the facial clip starts.
"""

import bisect
import os

from . import packs
from .formats import paz, wwise

AUTOFACIAL = "99_autofacial"
VOICE = "sound/windows/"


def voices(idx):
    """{"<language>/<line>": pack entry} of every voice line in the game,
    read once per index from every group but the ones the index reads."""
    if getattr(idx, "_voices", None) is None:
        out = {}
        for group in sorted(os.listdir(idx.folder)):
            pamt = os.path.join(idx.folder, group, "0.pamt")
            if group in packs.GROUPS or not os.path.isfile(pamt):
                continue
            for e in paz.read_index(pamt, {"wem"}):
                p = e.path.lower()
                # sound/windows/<language>/<line>.wem; sound/windows/media/
                # holds numbered sound effects and music
                if p.startswith(VOICE) and p.count("/") == 3 and not p.startswith(VOICE + "media/"):
                    out[p[len(VOICE):-4]] = e
        idx._voices = out
    return idx._voices


def line_of(clip):
    """("<language>", "<line>") of a lip sync clip's path, or None for any
    other clip."""
    parts = clip.lower().split("/")
    if AUTOFACIAL not in parts[:-2]:
        return None
    i = parts.index(AUTOFACIAL)
    return parts[i + 1], parts[-1]


def languages(idx):
    """The installed voice languages, such as english(us)."""
    if getattr(idx, "_voice_languages", None) is None:
        idx._voice_languages = sorted({k.split("/", 1)[0] for k in voices(idx)})
    return idx._voice_languages


def fetch(idx, clip):
    """The cached .ogg of a lip sync clip's voice line, converted on first
    use, or None when the game has no voice for it in that language."""
    line = line_of(clip)
    if line is None:
        return None
    entry = voices(idx).get("/".join(line))
    if entry is None:
        return None
    path = os.path.join(packs.cache_root(), "voice", line[0], line[1] + ".ogg")
    if not os.path.isfile(path):
        data = wwise.convert(paz.read(entry))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    return path


def strip_of(scene, obj):
    ed = scene.sequence_editor
    name = obj.get("cd_voice")
    return ed.strips.get(name) if ed and name else None


def remove(scene, obj):
    """Take the armature's voice strip out of the scene. Returns True if it had one."""
    strip = strip_of(scene, obj)
    if "cd_voice" in obj:
        del obj["cd_voice"]
    if strip is None:
        return False
    scene.sequence_editor.strips.remove(strip)
    return True


def attach(context, obj, path, name):
    """Play the sound file at `path` from frame 0 as the armature's voice,
    in place of any voice it had, on the lowest free channel. The scene
    plays in step with the sound, dropping frames if it has to, so the lips
    keep up with the line."""
    scene = context.scene
    remove(scene, obj)
    ed = scene.sequence_editor or scene.sequence_editor_create()
    used = {s.channel for s in ed.strips}
    channel = next(c for c in range(1, 129) if c not in used)
    strip = ed.strips.new_sound(f"{obj.name} voice", path, channel, 0)
    strip["cd_voice_line"] = name
    obj["cd_voice"] = strip.name
    scene.sync_mode = "AUDIO_SYNC"
    return strip


def _has_clip(idx, clip):
    i = bisect.bisect_left(idx.clips, clip)
    return i < len(idx.clips) and idx.clips[i] == clip


def elsewhere(idx, clip):
    """The same line's lip sync clips in the other installed languages that
    have its voice: [(language, clip)]."""
    line = line_of(clip)
    if line is None:
        return []
    lang, name = line
    out = []
    for other in languages(idx):
        if other == lang or f"{other}/{name}" not in voices(idx):
            continue
        parts = clip.split("/")
        i = [p.lower() for p in parts].index(AUTOFACIAL)
        parts[i + 1] = other
        candidate = "/".join(parts)
        if _has_clip(idx, candidate):
            out.append((other, candidate))
    return out


def add_for_clip(context, idx, obj, clip):
    """Give the armature the voice of lip sync clip `clip` (a path under
    character/motion/). Returns (strip or None, note)."""
    line = line_of(clip)
    if line is None:
        return None, ""
    try:
        path = fetch(idx, clip)
    except (wwise.WemError, OSError, ValueError) as exc:
        return None, f"{line[1]}: the voice could not be read ({exc})"
    if path is None:
        have = languages(idx)
        if line[0] not in have:
            return None, (f"{line[1]}: no {line[0]} voice is installed; the game here has "
                          f"{', '.join(have) or 'none'}")
        others = elsewhere(idx, clip)
        if others:
            return None, (f"{line[1]}: the game has no {line[0]} voice for this line, but it is voiced in "
                          f"{others[0][0]}; import {others[0][1]} to hear it with its own lip sync")
        return None, f"{line[1]}: the game has no {line[0]} voice for this line in any installed language"
    strip = attach(context, obj, path, line[1])
    return strip, f"{obj.name}: speaking {line[1]} ({line[0]})"
