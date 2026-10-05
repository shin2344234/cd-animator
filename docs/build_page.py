"""Build the CD Animator Guide, one web page that holds every page in this folder.

    python docs/build_page.py [out file]

Each Markdown page here becomes a section of page_template.html, shown one
at a time by the link's hash, with the page list, search and section list
the template draws. Links between pages become links between sections. The
page goes to out/cd-animator-guide.html unless another file is named.

The converter reads only the Markdown these pages use: headings down to ###,
paragraphs, pipe tables, numbered and dashed lists one level deep, fenced
code, inline code and links. A page missing from GROUPS stops the build.
"""

import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "page_template.html")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "out", "cd-animator-guide.html")
GROUPS = [("Start", ["README", "install", "sidebar"]),
          ("Building a scene", ["importing", "characters", "physics", "faces"]),
          ("Animating", ["making-clips", "ik-controls", "mocap", "exporting"]),
          ("In the game", ["in-the-game", "moves", "loader"]),
          ("Reference", ["examples", "checks", "troubleshooting"])]


def pid(name):
    return "overview" if name == "README" else name


def slug(h):
    """A heading's anchor, as GitHub makes it."""
    return re.sub(r"[^\w\- ]", "", h.strip().lower()).replace(" ", "-")


def esc(s):
    return html.escape(s, quote=False)


def link(text, target, page):
    if target.startswith("http"):
        return f'<a href="{html.escape(target)}" target="_blank" rel="noopener">{esc(text)}</a>'
    f, _, a = target.partition("#")
    p = pid(f[:-3]) if f else page
    return f'<a href="#{p}{"." + a if a else ""}">{esc(text)}</a>'


def inline(text, page):
    out = []
    for part in re.split(r"(`[^`]*`)", text):
        if len(part) >= 2 and part[0] == part[-1] == "`":
            out.append(f"<code>{esc(part[1:-1])}</code>")
            continue
        pos = 0
        for m in re.finditer(r"\[([^\]]+)\]\(([^)\s]+)\)", part):
            out.append(esc(part[pos:m.start()]) + link(m.group(1), m.group(2), page))
            pos = m.end()
        out.append(esc(part[pos:]))
    return "".join(out)


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def table(rows, page):
    head, body = cells(rows[0]), [cells(r) for r in rows[2:]]
    thead = ("<thead><tr>" + "".join(f"<th>{inline(c, page)}</th>" for c in head) + "</tr></thead>"
             if any(head) else "")
    tbody = "".join("<tr>" + "".join(f"<td>{inline(c, page)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="table-wrap"><table>{thead}<tbody>{tbody}</tbody></table></div>'


BLOCK = re.compile(r"^(#{1,3} |```|\||- |\d+\. )")
ITEM = re.compile(r"^(\d+\. |- )")


def convert(md, page):
    """(title, html) of one Markdown page whose anchors start with `page`."""
    lines, out, title, i = md.split("\n"), [], None, 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            out.append(f'<div class="code"><pre><code>{esc(chr(10).join(lines[i + 1:j]))}</code></pre></div>')
            i = j + 1
        elif m := re.match(r"^(#{1,3}) (.+)$", line):
            level, text = len(m.group(1)), m.group(2)
            if level == 1:
                title = text
                out.append(f"<h1>{inline(text, page)}</h1>")
            else:
                out.append(f'<h{level} id="{page}.{slug(text)}">{inline(text, page)}</h{level}>')
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows, page))
        elif ITEM.match(line):
            tag = "ol" if line[0].isdigit() else "ul"
            items = []
            while i < len(lines) and ITEM.match(lines[i]):
                items.append(ITEM.sub("", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x, page)}</li>" for x in items) + f"</{tag}>")
        elif line.strip():
            buf = []
            while i < len(lines) and lines[i].strip() and not BLOCK.match(lines[i]):
                buf.append(lines[i])
                i += 1
            out.append(f"<p>{inline(' '.join(buf), page)}</p>")
        else:
            i += 1
    return title, "\n".join(out)


def main():
    listed = {n for _group, names in GROUPS for n in names}
    missing = sorted({n[:-3] for n in os.listdir(HERE) if n.endswith(".md")} - listed)
    if missing:
        sys.exit(f"Put these pages in a group in GROUPS: {', '.join(missing)}")
    pages = []
    for group, names in GROUPS:
        for name in names:
            with open(os.path.join(HERE, name + ".md"), encoding="utf-8") as f:
                title, body = convert(f.read(), pid(name))
            pages.append((group, pid(name), "Overview" if name == "README" else title, body))

    nav = []
    for group, _names in GROUPS:
        items = "".join(f'<li><a href="#{p}" data-page="{p}">{esc(t)}</a></li>' for g, p, t, _b in pages if g == group)
        nav.append(f'<div class="group"><p class="group-title">{esc(group)}</p><ul>{items}</ul></div>')

    articles = []
    for n, (group, p, _title, body) in enumerate(pages):
        pager = ""
        if n:
            pager += f'<a class="prev" href="#{pages[n - 1][1]}"><small>Previous</small><span>{esc(pages[n - 1][2])}</span></a>'
        if n + 1 < len(pages):
            pager += f'<a class="next" href="#{pages[n + 1][1]}"><small>Next</small><span>{esc(pages[n + 1][2])}</span></a>'
        articles.append(f'<article class="page" id="{p}"><p class="eyebrow">{esc(group)}</p>\n{body}\n'
                        f'<nav class="pager" aria-label="Previous and next page">{pager}</nav></article>')

    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read().replace("{{NAV}}", "\n".join(nav)).replace("{{ARTICLES}}", "\n".join(articles))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote {OUT}, {len(pages)} pages, {len(page):,} bytes")


main()
