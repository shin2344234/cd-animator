"""Point the game's action charts and blends at clips under new names.

A clip under a name no pack has plays only if a chart or a blend names it.
An action chart (formats/paac.py) names each clip a node plays by an index
into its table of clip paths, so pointing a node at a new clip means adding
the new path to that table and setting the node's index to it. Nothing else
in the chart moves: no node is added or removed, and the game's own paths
keep their indexes. A blend (formats/motionblend.py) lists the clips it
mixes, each once, and its examples name them by index, so a slot of that
list gets the new path in place of the old and the list keeps its length.
A blend plays wherever a chart node names it.

The loader serves most files by name, but a file under by_path in its
folder at the game's path for it goes in for that path only (loader 0.2.0
and later). Blend names are unique but for 44 of the 1,688, the male and
female versions of a blend among them, so every edited chart and blend
goes there, and the game reads it in place of its own at the next start. Several new clips can share one file: each send
starts from the copy already in the folder. Taking a clip out puts its
nodes and slots back on the game's clips, and deletes the copy once it
matches the game's again.

Action names are hashes. The names table of a chart (strings[0]) holds the
names of other things, so 136 of the game's 84,133 actions have a name
anywhere in the game; an action is shown by its key instead.
"""
import json
import os
from struct import error as struct_error

from . import packs
from .formats import motionblend, paac, paz

BY_PATH = "by_path"
CHARTS = "actionchart/bin__/"
SUFFIX = ".paac"
BLENDS = "character/binary/motionblending/"
BLEND_SUFFIX = ".motionblending"


class ChartError(Exception):
    pass


def chart_paths(idx):
    if getattr(idx, "_chart_paths", None) is None:
        idx._chart_paths = sorted(p for p in idx.by_path if p.startswith(CHARTS) and p.endswith(SUFFIX))
    return idx._chart_paths


def blend_paths(idx):
    if getattr(idx, "_blend_paths", None) is None:
        idx._blend_paths = sorted(p for p in idx.by_path if p.startswith(BLENDS) and p.endswith(BLEND_SUFFIX))
    return idx._blend_paths


def is_blend(path):
    return path.lower().endswith(BLEND_SUFFIX)


def chart_name(path):
    return path.rsplit("/", 1)[-1]


def short(path):
    """A chart's path as the game's charts name it, such as
    upperaction/1_pc/1_phm/basic_upper, or a blend's under
    motionblending/, such as phm_locomotion/basic_move_walk."""
    if is_blend(path):
        return path[len(BLENDS):-len(BLEND_SUFFIX)]
    return path[len(CHARTS):-len(SUFFIX)]


def _by_name(idx):
    """{file name: path} of the charts and blends whose name is the game's
    only file of that name, which 0.22.0 put in the folder by name."""
    if getattr(idx, "_files_by_name", None) is None:
        names = {}
        for p in chart_paths(idx) + blend_paths(idx):
            names.setdefault(chart_name(p), []).append(p)
        idx._files_by_name = {n: ps[0] for n, ps in names.items() if len(ps) == 1}
    return idx._files_by_name


def game_bytes(idx, path):
    return paz.read(idx.by_path[path])


def _table(chart):
    return chart.strings[1]


class _Blend:
    """A blend with the add-on's view of it: its clip list as text."""

    def __init__(self, data):
        self.mb = motionblend.parse(data)
        self.clips = [c.decode("ascii") for c in self.mb.root.values.get("_animationFileNames", [])]

    def pack(self):
        self.mb.root.values["_animationFileNames"] = [c.encode("ascii") for c in self.clips]
        return motionblend.write(self.mb)


def _parse(path, data):
    return _Blend(data) if is_blend(path) else paac.Chart.parse(data)


def _uses_file(idx):
    stamp = "_".join(str(int(t)) for t in idx.stamp)
    return os.path.join(packs.cache_root(), f"clip_uses_{stamp}.json")


def _all_uses(idx):
    """{"clips": {clip path under character/motion/ without .paa, lower
    case: [[chart path, node, action key] or [blend path, slot, None]]},
    "blends": {blend path: chart nodes that name it}} for every chart the
    reader parses and every blend."""
    if getattr(idx, "_chart_uses", None) is not None:
        return idx._chart_uses
    path = _uses_file(idx)
    try:
        with open(path, encoding="utf-8") as f:
            idx._chart_uses = json.load(f)
        return idx._chart_uses
    except (OSError, ValueError):
        pass
    clips, blends = {}, {}
    for p in chart_paths(idx):
        try:
            c = paac.Chart.parse(game_bytes(idx, p))
        except paac.ParseError:
            continue
        owner = {}
        for a in c.actions:
            for i in range(a.node_first, a.node_first + a.node_count):
                owner[i] = a.key_hash
        table = _table(c)
        for i, n in enumerate(c.nodes):
            k = n.header.anim_index
            if k < len(table) and table[k].lower().endswith(".paa"):
                clips.setdefault(table[k][:-4].lower(), []).append([p, i, owner.get(i, 0)])
            for b in {n.header.blend_index_a, n.header.blend_index_b}:
                if b < len(c.strings[5]):
                    name = c.strings[5][b].lower()
                    blends[name] = blends.get(name, 0) + 1
    for p in blend_paths(idx):
        try:
            b = _Blend(game_bytes(idx, p))
        except (motionblend.FormatError, struct_error, UnicodeDecodeError):
            continue
        for i, c in enumerate(b.clips):
            if c.lower().endswith(".paa"):
                clips.setdefault(c[:-4].lower(), []).append([p, i, None])
    idx._chart_uses = {"clips": clips, "blends": blends}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(idx._chart_uses, f)
    except OSError:
        pass
    return idx._chart_uses


def uses(idx, clip):
    """[(chart path, node, action key)] of every chart node that plays
    `clip`, a path under character/motion/ without .paa, then [(blend
    path, slot, None)] of every blend that mixes it."""
    return [tuple(u) for u in _all_uses(idx)["clips"].get(clip.lower(), [])]


def blend_users(idx, path):
    """How many chart nodes name the blend at `path`."""
    return _all_uses(idx)["blends"].get(path.lower(), 0)


def template_clip(action):
    """The game clip a new clip was started from, as a path under
    character/motion/, or None when it came from a file elsewhere."""
    t = action.get("cd_template")
    if not t:
        return None
    base = os.path.join(packs.cache_root(), "clips")
    try:
        rel = os.path.relpath(t, base)
    except ValueError:
        return None
    if rel.startswith("..") or not rel.lower().endswith(".paa"):
        return None
    return rel[:-4].replace("\\", "/")


def new_path(action, name):
    """The path under character/motion/ the charts give a new clip: the
    template's folder and the new name."""
    t = template_clip(action)
    folder = t.rsplit("/", 1)[0] + "/" if t and "/" in t else ""
    return folder + name


def point(chart, nodes, clip):
    """Point `nodes` of `chart` at `clip` (under character/motion/, no
    .paa), adding its path to the chart's clip table if it is not there.
    For a blend, `nodes` are slots of its clip list, which take the new
    path in place of the old."""
    want = clip + ".paa"
    if isinstance(chart, _Blend):
        for i in nodes:
            if not 0 <= i < len(chart.clips):
                raise ChartError(f"the blend has no clip {i}")
            chart.clips[i] = want
        return
    table = _table(chart)
    low = [s.lower() for s in table]
    if want.lower() in low:
        k = low.index(want.lower())
    else:
        k = len(table)
        if k > 0xFFFF:
            raise ChartError(f"the chart's clip table is full ({k} paths)")
        if len(want) + 1 > 255:
            raise ChartError(f"{want} is longer than a chart path may be")
        chart.strings[1].append(want)
    for i in nodes:
        if not 0 <= i < len(chart.nodes):
            raise ChartError(f"the chart has no node {i}")
        h = chart.nodes[i].header
        h.anim_index = k
        h.anim_index_a = k


def unpoint(chart, game, clip):
    """Put every node of `chart` that plays `clip` back on the clip the
    game's chart `game` gives it, then drop added paths no node plays.
    Returns the nodes put back; for a blend, the slots."""
    want = (clip + ".paa").lower()
    if isinstance(chart, _Blend):
        back = [i for i, c in enumerate(chart.clips) if c.lower() == want and c != game.clips[i]]
        for i in back:
            chart.clips[i] = game.clips[i]
        return back
    low = [s.lower() for s in _table(chart)]
    back = []
    for i, n in enumerate(chart.nodes):
        k = n.header.anim_index
        if k < len(low) and low[k] == want:
            g = game.nodes[i].header
            n.header.anim_index = g.anim_index
            n.header.anim_index_a = g.anim_index_a
            back.append(i)
    used = {n.header.anim_index for n in chart.nodes} | {n.header.anim_index_a for n in chart.nodes}
    keep = len(game.strings[1])
    for k in range(len(chart.strings[1]) - 1, keep - 1, -1):
        if k in used:
            continue
        del chart.strings[1][k]
        for n in chart.nodes:
            if n.header.anim_index > k:
                n.header.anim_index -= 1
            if n.header.anim_index_a > k:
                n.header.anim_index_a -= 1
    return back


def pointed(chart, game):
    """{clip path under character/motion/ without .paa: [nodes]} of the
    nodes in `chart` that play a clip other than the game's chart's; for a
    blend, its slots."""
    out = {}
    if isinstance(chart, _Blend):
        for i, (c, g) in enumerate(zip(chart.clips, game.clips)):
            if c.lower() != g.lower():
                out.setdefault(c[:-4] if c.lower().endswith(".paa") else c, []).append(i)
        return out
    table, gtable = _table(chart), _table(game)
    for i, (n, g) in enumerate(zip(chart.nodes, game.nodes)):
        k, gk = n.header.anim_index, g.header.anim_index
        if k < len(table) and (gk >= len(gtable) or table[k].lower() != gtable[gk].lower()):
            out.setdefault(table[k][:-4] if table[k].lower().endswith(".paa") else table[k], []).append(i)
    return out


def _target(root, path):
    """Where a chart or blend goes in the loader folder: under by_path, at
    the game's path for it."""
    return os.path.join(root, BY_PATH, *path.split("/"))


def _copy_in(root, path):
    """The file's copy in the loader folder `root`, or None: the one at
    its game path under by_path, else one by its name elsewhere, as 0.22.0
    wrote them."""
    at = _target(root, path)
    if os.path.isfile(at):
        return at
    want = chart_name(path).lower()
    for here, dirs, names in os.walk(root):
        if os.path.normcase(os.path.abspath(here)) == os.path.normcase(os.path.abspath(os.path.join(root, BY_PATH))):
            dirs[:] = []
            continue
        dirs.sort()
        for n in sorted(names):
            if n.lower() == want:
                return os.path.join(here, n)
    return None


def _size(doc):
    return len(doc.clips) if isinstance(doc, _Blend) else len(doc.nodes)


def current(idx, root, path):
    """(chart, game chart, file in the folder or None): the folder's copy
    of a chart or blend if it has one, else the game's."""
    game = _parse(path, game_bytes(idx, path))
    mine = _copy_in(root, path) if root and os.path.isdir(root) else None
    if mine and mine != _target(root, path) and _by_name(idx).get(chart_name(path)) != path:
        mine = None   # a file of that name, but not this one's
    if mine:
        with open(mine, "rb") as f:
            chart = _parse(path, f.read())
        if _size(chart) != _size(game):
            raise ChartError(f"{mine} does not match the game's {chart_name(path)}; it was not made from this "
                             "version of the game's file")
    else:
        chart = _parse(path, game_bytes(idx, path))
    return chart, game, mine


def send(idx, root, clip, plays):
    """Write into the loader folder `root` the charts and blends that
    point `plays` ([(path, node or slot)]) at `clip`. Returns the files
    written."""
    by_chart = {}
    for path, node in plays:
        by_chart.setdefault(path, []).append(node)
    written = []
    for path, nodes in sorted(by_chart.items()):
        chart, _game, mine = current(idx, root, path)
        point(chart, nodes, clip)
        target = _target(root, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(chart.pack())
        if mine and mine != target:
            os.remove(mine)
            _prune(os.path.dirname(mine), root)
        written.append(target)
    return written


def _ours(idx, root):
    """(file, game path) of each chart and blend in the folder `root`:
    those under by_path at a game path, and those elsewhere by name."""
    under = os.path.normcase(os.path.abspath(os.path.join(root, BY_PATH)))
    by_name = _by_name(idx)
    for here, dirs, names in os.walk(root):
        dirs.sort()
        inside = os.path.normcase(os.path.abspath(here)).startswith(under)
        for n in sorted(names):
            f = os.path.join(here, n)
            if inside:
                path = os.path.relpath(f, os.path.join(root, BY_PATH)).replace("\\", "/").lower()
                if (path.startswith(CHARTS) and path.endswith(SUFFIX) or is_blend(path)) and path in idx.by_path:
                    yield f, path
            elif by_name.get(n.lower()):
                yield f, by_name[n.lower()]


def _clips_of(doc):
    return doc.clips if isinstance(doc, _Blend) else _table(doc)


def _prune(folder, root):
    """Remove `folder` and the folders above it while empty, up to `root`."""
    root = os.path.normcase(os.path.abspath(root))
    folder = os.path.abspath(folder)
    while os.path.normcase(folder) != root and os.path.normcase(folder).startswith(root):
        try:
            os.rmdir(folder)
        except OSError:
            return
        folder = os.path.dirname(folder)


def take_out(idx, root, clip):
    """Put back every node and slot of the charts and blends in `root`
    that plays `clip`, a path under character/motion/ or only the clip's
    name, as the loader matches files; delete a file that then matches the
    game's. Returns (rewritten, deleted) file paths."""
    rewritten, deleted = [], []
    if not os.path.isdir(root):
        return rewritten, deleted
    leaf = clip.rsplit("/", 1)[-1].lower() + ".paa"
    for f, path in list(_ours(idx, root)):
        with open(f, "rb") as h:
            chart = _parse(path, h.read())
        game_data = game_bytes(idx, path)
        game = _parse(path, game_data)
        named = {s[:-4] for s in _clips_of(chart) if s.rsplit("/", 1)[-1].lower() == leaf}
        if not [i for c in sorted(named) for i in unpoint(chart, game, c)]:
            continue
        data = chart.pack()
        if data == game_data:
            os.remove(f)
            _prune(os.path.dirname(f), root)
            deleted.append(f)
        else:
            with open(f, "wb") as h:
                h.write(data)
            rewritten.append(f)
    return rewritten, deleted


def in_folder(idx, root):
    """[(file, {clip: [nodes or slots]})] for the game's charts and blends
    in `root`."""
    if not os.path.isdir(root):
        return []
    out = []
    for f, path in _ours(idx, root):
        with open(f, "rb") as h:
            chart = _parse(path, h.read())
        out.append((f, pointed(chart, _parse(path, game_bytes(idx, path)))))
    return out
