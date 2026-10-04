"""Point the game's action charts at clips under new names.

A clip under a name no pack has plays only if a chart names it. An action
chart (formats/paac.py) names each clip a node plays by an index into its
table of clip paths, so pointing a node at a new clip means adding the new
path to that table and setting the node's index to it. Nothing else in the
chart moves: no node is added or removed, and the game's own paths keep
their indexes.

The loader serves charts by file name like clips, and chart names are
unique among the game's 558. So the edited chart goes into the loader's
folder under its own name, and the game reads it in place of its own at the
next start. Several new clips can share one chart: each send starts from
the copy already in the folder. Taking a clip out puts its nodes back on
the game's clips, and deletes the copy once it matches the game's again.

Action names are hashes. The names table of a chart (strings[0]) holds the
names of other things, so 136 of the game's 84,133 actions have a name
anywhere in the game; an action is shown by its key instead.
"""

import json
import os

from . import packs
from .formats import paac, paz

CHARTS = "actionchart/bin__/"
SUFFIX = ".paac"


class ChartError(Exception):
    pass


def chart_paths(idx):
    if getattr(idx, "_chart_paths", None) is None:
        idx._chart_paths = sorted(p for p in idx.by_path if p.startswith(CHARTS) and p.endswith(SUFFIX))
    return idx._chart_paths


def chart_name(path):
    return path.rsplit("/", 1)[-1]


def short(path):
    """A chart's path as the game's charts name it, such as
    upperaction/1_pc/1_phm/basic_upper."""
    return path[len(CHARTS):-len(SUFFIX)]


def game_bytes(idx, path):
    return paz.read(idx.by_path[path])


def _table(chart):
    return chart.strings[1]


def _uses_file(idx):
    stamp = "_".join(str(int(t)) for t in idx.stamp)
    return os.path.join(packs.cache_root(), f"chart_uses_{stamp}.json")


def _all_uses(idx):
    """{clip path under character/motion/ without .paa, lower case:
    [[chart path, node, action key]]} for every chart the reader parses."""
    if getattr(idx, "_chart_uses", None) is not None:
        return idx._chart_uses
    path = _uses_file(idx)
    try:
        with open(path, encoding="utf-8") as f:
            idx._chart_uses = json.load(f)
        return idx._chart_uses
    except (OSError, ValueError):
        pass
    out = {}
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
                out.setdefault(table[k][:-4].lower(), []).append([p, i, owner.get(i, 0)])
    idx._chart_uses = out
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f)
    except OSError:
        pass
    return out


def uses(idx, clip):
    """[(chart path, node, action key)] of every chart node that plays
    `clip`, a path under character/motion/ without .paa."""
    return [tuple(u) for u in _all_uses(idx).get(clip.lower(), [])]


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
    .paa), adding its path to the chart's clip table if it is not there."""
    want = clip + ".paa"
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
    Returns the nodes put back."""
    want = (clip + ".paa").lower()
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
    nodes in `chart` that play a clip other than the game's chart's."""
    table, gtable = _table(chart), _table(game)
    out = {}
    for i, (n, g) in enumerate(zip(chart.nodes, game.nodes)):
        k, gk = n.header.anim_index, g.header.anim_index
        if k < len(table) and (gk >= len(gtable) or table[k].lower() != gtable[gk].lower()):
            out.setdefault(table[k][:-4] if table[k].lower().endswith(".paa") else table[k], []).append(i)
    return out


def _copy_in(root, path):
    """The chart's copy in the loader folder `root`, or None."""
    want = chart_name(path).lower()
    for here, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            if n.lower() == want:
                return os.path.join(here, n)
    return None


def current(idx, root, path):
    """(chart, game chart, file in the folder or None): the folder's copy
    of a chart if it has one, else the game's."""
    game = paac.Chart.parse(game_bytes(idx, path))
    mine = _copy_in(root, path) if root and os.path.isdir(root) else None
    if mine:
        with open(mine, "rb") as f:
            chart = paac.Chart.parse(f.read())
        if len(chart.nodes) != len(game.nodes):
            raise ChartError(f"{mine} has {len(chart.nodes)} nodes and the game's {chart_name(path)} has "
                             f"{len(game.nodes)}; it was not made from this version of the game's chart")
    else:
        chart = paac.Chart.parse(game_bytes(idx, path))
    return chart, game, mine


def send(idx, root, clip, plays):
    """Write into the loader folder `root` the charts that point the nodes
    `plays` ([(chart path, node)]) at `clip`. Returns the files written."""
    by_chart = {}
    for path, node in plays:
        by_chart.setdefault(path, []).append(node)
    written = []
    for path, nodes in sorted(by_chart.items()):
        chart, _game, mine = current(idx, root, path)
        point(chart, nodes, clip)
        target = mine or os.path.join(root, chart_name(path))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(chart.pack())
        written.append(target)
    return written


def take_out(idx, root, clip):
    """Put back every node of the charts in `root` that plays `clip`, a
    path under character/motion/ or only the clip's name, as the loader
    matches files; delete a chart that then matches the game's. Returns
    (rewritten, deleted) file paths."""
    rewritten, deleted = [], []
    if not os.path.isdir(root):
        return rewritten, deleted
    leaf = clip.rsplit("/", 1)[-1].lower() + ".paa"
    by_name = {chart_name(p): p for p in chart_paths(idx)}
    for here, _dirs, names in os.walk(root):
        for n in names:
            path = by_name.get(n.lower())
            if path is None:
                continue
            f = os.path.join(here, n)
            with open(f, "rb") as h:
                chart = paac.Chart.parse(h.read())
            game_data = game_bytes(idx, path)
            game = paac.Chart.parse(game_data)
            named = {s[:-4] for s in _table(chart) if s.rsplit("/", 1)[-1].lower() == leaf}
            if not [i for c in sorted(named) for i in unpoint(chart, game, c)]:
                continue
            data = chart.pack()
            if data == game_data:
                os.remove(f)
                deleted.append(f)
            else:
                with open(f, "wb") as h:
                    h.write(data)
                rewritten.append(f)
    return rewritten, deleted


def in_folder(idx, root):
    """[(chart file, {clip: [nodes]})] for the game's charts in `root`."""
    out = []
    if not os.path.isdir(root):
        return out
    by_name = {chart_name(p): p for p in chart_paths(idx)}
    for here, _dirs, names in os.walk(root):
        for n in sorted(names):
            path = by_name.get(n.lower())
            if path is None:
                continue
            f = os.path.join(here, n)
            with open(f, "rb") as h:
                chart = paac.Chart.parse(h.read())
            out.append((f, pointed(chart, paac.Chart.parse(game_bytes(idx, path)))))
    return out
