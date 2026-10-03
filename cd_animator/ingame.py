"""Send clips to the game through the CD Animator Loader.

The loader (loader/, CDAnimator.asi in the game's bin64 folder) hands the
game every file in bin64/CDAnimator in place of the game's file of that
name, and reads the folder once, when the game starts. send() exports a
clip's three files there under the game's name for it. sent() lists the
clips in the folder, and status() reads the loader's log, CDAnimator.log
beside it, to say whether the running or last session found each one at
startup and whether the game has loaded it since.

The log of the current or last session starts when the game does: the
loader renames the one before to CDAnimator.01.log and writes a new one.
At startup it logs a [folder] line for each file it found, and a [files]
line each time the game takes one of them. Its lines carry the time of
day only, so the session's date is the log file's creation time.
"""

import datetime
import os
import re

from . import export, packs

LOADER = "CDAnimator.asi"
FOLDER = "CDAnimator"
LOG = "CDAnimator.log"
GAME_EXE = "CrimsonDesert.exe"
SUFFIXES = ("_lod.paa", ".paa_metabin", ".paa")


class SendError(Exception):
    pass


def bin64(context=None):
    return os.path.join(packs.game_folder(context), "bin64")


def folder(context=None):
    """The loader's folder, made if the loader is installed and it is not."""
    b = bin64(context)
    if not os.path.isfile(os.path.join(b, LOADER)):
        raise SendError(f"the CD Animator Loader is not installed: {LOADER} is not in {b}. "
                        "Copy it from the loader's dist folder into bin64 first")
    path = os.path.join(b, FOLDER)
    os.makedirs(path, exist_ok=True)
    return path


def clip_name(action):
    """The game's name for the clip an action holds: the file it was
    imported from, or the name a new clip was given."""
    if "cd_template" in action:
        return action.name
    source = action.get("cd_source")
    if not source:
        raise SendError(f"{action.name} was not imported from a clip, so it has no name in the game")
    return os.path.splitext(os.path.basename(source))[0]


def stem_of(file_name):
    low = file_name.lower()
    for s in SUFFIXES:
        if low.endswith(s):
            return file_name[:-len(s)]
    return None


def _files(root):
    """{lower-case file name: path} of every file under `root`; the first
    of two with one name, as the loader takes it."""
    out = {}
    for here, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            out.setdefault(n.lower(), os.path.join(here, n))
    return out


def send(obj, action, root, bake=True):
    """Export `action` on armature `obj` into the loader folder `root` as
    the game's clip of its name. Same-named files of the clip elsewhere in
    the folder would win over the new ones, so then nothing is written and
    SendError names them. Returns (name, written paths, problems)."""
    name = clip_name(action)
    target = os.path.join(root, name + ".paa")
    # The loader walks the folder in directory order and keeps the first of
    # two same-named files, so any copy in a subfolder may win.
    wanted = {n.lower() for n in (name + ".paa", name + "_lod.paa", name + ".paa_metabin")}
    shadows = []
    for here, _dirs, names in os.walk(root):
        if os.path.normcase(os.path.abspath(here)) == os.path.normcase(os.path.abspath(root)):
            continue
        shadows += [os.path.join(here, n) for n in names if n.lower() in wanted]
    if shadows:
        raise SendError(f"{name} is already in a subfolder of the loader's folder, at {shadows[0]}, and the game "
                        "may take that copy; remove it from there first")
    written, problems = export.export_with_companions(obj, action, target, bake)
    return name, written, problems


def sent(root):
    """{clip name: (paths, newest change time)} of the clips in the folder."""
    out = {}
    for path in _files(root).values():
        stem = stem_of(os.path.basename(path))
        if stem is None:
            continue
        paths, newest = out.get(stem, ([], 0.0))
        out[stem] = (paths + [path], max(newest, os.path.getmtime(path)))
    return out


def remove(root, name):
    """Delete clip `name`'s files from the folder. Returns the paths removed."""
    gone = []
    for path in _files(root).values():
        stem = stem_of(os.path.basename(path))
        if stem is not None and stem.lower() == name.lower():
            os.remove(path)
            gone.append(path)
    return gone


_LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\.(\d+)\] \[[a-z ]+\] \[(folder|files)\] (.*)$")


def read_log(bin64_path):
    """(session start, {file name: time found}, {file name: time first
    taken}) from the loader's current log, names in lower case; None when
    there is no log."""
    path = os.path.join(bin64_path, LOG)
    if not os.path.isfile(path):
        return None
    start = datetime.datetime.fromtimestamp(os.path.getctime(path))
    found, taken = {}, {}
    day = start.date()
    last = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _LINE.match(line.rstrip("\n"))
            if not m:
                continue
            t = datetime.time(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if last is not None and t < last:
                day += datetime.timedelta(days=1)
            last = t
            when = datetime.datetime.combine(day, t)
            kind, rest = m.group(5), m.group(6)
            if kind == "folder" and "goes in for the game's file" in rest:
                name = rest.split(" (", 1)[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
                found.setdefault(name, when)
            elif kind == "files" and " is the plugin's (" in rest:
                name = rest.split(" is the plugin's", 1)[0].rsplit("/", 1)[-1].lower()
                taken.setdefault(name, when)
    return start, found, taken


def game_running():
    """True when the game's process runs, False when not, None when unknown."""
    import subprocess
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME_EXE}", "/NH"], capture_output=True,
                             text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return GAME_EXE.lower() in out.stdout.lower()


def status(root, log):
    """[(clip name, files, state)] for the clips in the folder. `log` is
    read_log()'s result. A state is one of:
    "waiting"  the clip changed after the session started, or the session
               did not find it; the game takes it at its next start;
    "ready"    the session found it at startup and the game has not loaded it;
    "played"   the game has loaded it this session, at the time given.
    """
    out = []
    for name, (paths, newest) in sorted(sent(root).items()):
        main = (name + ".paa").lower()
        files = sorted(os.path.basename(p) for p in paths)
        if log is None:
            out.append((name, files, ("waiting", None)))
            continue
        start, found, taken = log
        changed = datetime.datetime.fromtimestamp(newest)
        if main not in found or changed > start:
            out.append((name, files, ("waiting", None)))
        elif main in taken:
            out.append((name, files, ("played", taken[main])))
        else:
            out.append((name, files, ("ready", found[main])))
    return out


INI = "CDAnimator.ini"
_CLIP = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\.\d+\] \[[a-z ]+\] \[clip\] (.*)$")
_GAP = re.compile(r"^---- ([\d.]+) s with no new clip ----$")


def read_clips(bin64_path):
    """The clips the game loaded in the current or last session, in the
    blocks the loader logs: [(time, gap before it in seconds or None,
    [clip paths under character/motion/ without .paa])], oldest first.
    The loader logs a clip once a session, the first time the game loads
    it, and starts a block wherever none has loaded for 2 s. Blends and
    other files are left out."""
    path = os.path.join(bin64_path, LOG)
    if not os.path.isfile(path):
        return []
    start = datetime.datetime.fromtimestamp(os.path.getctime(path))
    day, last = start.date(), None
    blocks = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _CLIP.match(line.rstrip("\n"))
            if not m:
                continue
            t = datetime.time(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if last is not None and t < last:
                day += datetime.timedelta(days=1)
            last = t
            when = datetime.datetime.combine(day, t)
            rest = m.group(4).strip()
            gap = _GAP.match(rest)
            if gap:
                blocks.append((when, float(gap.group(1)), []))
                continue
            low = rest.lower()
            if not (low.startswith(packs.MOTION) and low.endswith(".paa")) or low.startswith(packs.MOTION_LOD):
                continue
            if not blocks:
                blocks.append((when, None, []))
            blocks[-1][2].append(rest[len(packs.MOTION):-len(".paa")])
    return [b for b in blocks if b[2]]


def logging_clips(bin64_path):
    """True when the loader's ini has LogClips=1, False when 0 or missing,
    None when there is no ini."""
    path = os.path.join(bin64_path, INI)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"\s*LogClips\s*=\s*(\d+)", line)
            if m:
                return m.group(1) != "0"
    return False


def log_clips(bin64_path, on=True):
    """Set LogClips in the loader's ini, keeping the rest of the file. The
    loader reads it when the game starts."""
    path = os.path.join(bin64_path, INI)
    if not os.path.isfile(path):
        raise SendError(f"the loader has not written {INI} yet; start the game once with it installed")
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        text = f.read()
    value = "LogClips=1" if on else "LogClips=0"
    new, n = re.subn(r"(?m)^\s*LogClips\s*=\s*\d+", value, text)
    if not n:
        nl = "\r\n" if "\r\n" in text else "\n"
        new = re.sub(r"(?m)^\[settings\]\s*$", "[settings]" + nl + value, text, count=1)
        if new == text:
            new = text + nl + "[settings]" + nl + value + nl
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new)
