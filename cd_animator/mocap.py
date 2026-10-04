"""Motion capture from the CMU Graphics Lab Motion Capture Database, through
its BVH release at github.com/una-dinosauria/cmu-mocap.

cmu-mocap-index-text.txt, that release's list of its motions with their
descriptions, comes with the add-on: 2,435 motions of 109 subjects, named
like 93_03 for subject 93's third. A motion's file downloads once into the
add-on's cache. CMU places no restrictions on the data ("free for use in
research and commercial projects worldwide") and the BVH release adds none.
The files run at 120 frames a second, each with a T-pose added as frame 1,
which Retarget from armature takes for the actor's rest pose.
"""

import os
import re
import urllib.request

import bpy

from . import packs

INDEX = os.path.join(os.path.dirname(__file__), "cmu-mocap-index-text.txt")
URL = "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data/{subject:03d}/{name}.bvh"

_motions = None


class MocapError(Exception):
    pass


def motions():
    """Every motion as "name description (its subject's description)", in
    lower case for packs.search(), read once from the index."""
    global _motions
    if _motions is None:
        _motions, subject = [], ""
        with open(INDEX, encoding="utf-8") as f:
            for line in f:
                head = re.match(r"Subject #\d+ \((.*)\)", line)
                if head:
                    subject = head.group(1)
                m = re.match(r"(\d+_\d+)\t(.*)", line.rstrip())
                if m:
                    _motions.append(f"{m.group(1)} {m.group(2)} ({subject})".lower())
    return _motions


def find(text):
    """The motion `text` names: one from the list, its name alone, or words
    only one motion's description holds."""
    names = {m.split()[0]: m for m in motions()}
    first = (text.split() or [""])[0].lower()
    if first in names:
        return names[first]
    hits = packs.search(motions(), text)
    if len(hits) == 1:
        return hits[0]
    raise MocapError(f'{len(hits) or "No"} CMU motions match "{text.strip()}"; pick one from the list')


def url(name):
    return URL.format(subject=int(name.split("_")[0]), name=name)


def fetch(motion):
    """The local BVH file of `motion`, from find(), downloading it the first
    time."""
    name = motion.split()[0]
    path = os.path.join(packs.cache_root(), "mocap", name + ".bvh")
    if not os.path.isfile(path):
        if not bpy.app.online_access:
            raise MocapError("Blender may not go online: turn on Allow Online Access in Preferences > System")
        try:
            with urllib.request.urlopen(url(name), timeout=60) as r:
                data = r.read()
        except OSError as exc:
            raise MocapError(f"could not download {name} from {url(name)}: {exc}")
        packs._write(path, data)
    return path
