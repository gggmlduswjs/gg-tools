#!/usr/bin/env python3
"""Codebase visualizer: emit a collapsible HTML tree of a directory.

Stdlib only. ponytail: one file, no deps, no framework.
"""
import os, sys, html, json

IGNORE = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
          "build", ".mypy_cache", ".pytest_cache", "staticfiles", ".idea"}

# extension -> color (type-based coloring)
COLORS = {
    ".py": "#3572A5", ".js": "#f1e05a", ".ts": "#3178c6", ".html": "#e34c26",
    ".css": "#563d7c", ".md": "#083fa1", ".json": "#292929", ".yml": "#cb171e",
    ".yaml": "#cb171e", ".txt": "#6e7681", ".sql": "#e38c00", ".sh": "#89e051",
    ".ps1": "#012456", ".xlsx": "#217346", ".png": "#a074c4", ".jpg": "#a074c4",
    ".svg": "#ff9800",
}
DEFAULT_COLOR = "#8b949e"


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def scan(root):
    """Return (node, stats). node = nested dict tree."""
    stats = {"files": 0, "dirs": 0, "size": 0, "exts": {}}

    def walk(path):
        entries = []
        try:
            names = sorted(os.listdir(path))
        except OSError:
            names = []
        # dirs first, then files, each alphabetical
        dirs = [n for n in names if os.path.isdir(os.path.join(path, n)) and n not in IGNORE]
        files = [n for n in names if os.path.isfile(os.path.join(path, n))]
        for n in dirs:
            child = walk(os.path.join(path, n))
            stats["dirs"] += 1
            entries.append(child)
        for n in files:
            fp = os.path.join(path, n)
            try:
                sz = os.path.getsize(fp)
            except OSError:
                sz = 0
            ext = os.path.splitext(n)[1].lower()
            stats["files"] += 1
            stats["size"] += sz
            stats["exts"][ext] = stats["exts"].get(ext, 0) + 1
            entries.append({"name": n, "size": sz, "ext": ext})
        total = sum(e.get("total", e.get("size", 0)) for e in entries)
        return {"name": os.path.basename(path) or path, "dir": True,
                "children": entries, "total": total}

    tree = walk(root)
    return tree, stats


def render_node(node, depth=0):
    if node.get("dir"):
        open_attr = " open" if depth < 1 else ""
        parts = [f'<details{open_attr}><summary><span class="dir">📁 {html.escape(node["name"])}</span>'
                 f'<span class="sz">{human(node["total"])}</span></summary><div class="kids">']
        for c in node["children"]:
            parts.append(render_node(c, depth + 1))
        parts.append("</div></details>")
        return "".join(parts)
    color = COLORS.get(node["ext"], DEFAULT_COLOR)
    return (f'<div class="file"><span class="dot" style="background:{color}"></span>'
            f'{html.escape(node["name"])}<span class="sz">{human(node["size"])}</span></div>')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = os.path.abspath(args[0] if args else ".")
    out = "codebase-map.html"
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]

    tree, stats = scan(root)
    exts_sorted = sorted(stats["exts"].items(), key=lambda x: -x[1])
    ext_rows = "".join(
        f'<div class="erow"><span class="dot" style="background:{COLORS.get(e, DEFAULT_COLOR)}"></span>'
        f'{html.escape(e or "(no ext)")}<span class="sz">{c}</span></div>'
        for e, c in exts_sorted)

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Codebase Map — {html.escape(os.path.basename(root))}</title>
<style>
body{{font:14px/1.5 ui-monospace,Consolas,monospace;background:#0d1117;color:#c9d1d9;margin:0}}
.wrap{{display:flex;min-height:100vh}}
.side{{width:240px;padding:20px;background:#161b22;border-right:1px solid #30363d;position:sticky;top:0;height:100vh;overflow:auto}}
.main{{flex:1;padding:20px;overflow:auto}}
h1{{font-size:16px;margin:0 0 4px}} h2{{font-size:12px;color:#8b949e;text-transform:uppercase;margin:20px 0 8px}}
.stat{{font-size:22px;font-weight:700;color:#58a6ff}} .stat small{{font-size:12px;color:#8b949e;font-weight:400}}
details{{margin-left:14px}} summary{{cursor:pointer;padding:2px 0;list-style:none}}
summary::-webkit-details-marker{{display:none}}
summary:hover{{background:#161b22}}
.dir{{color:#58a6ff}} .kids{{border-left:1px solid #21262d;margin-left:6px}}
.file{{margin-left:28px;padding:2px 0;color:#c9d1d9}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:8px;vertical-align:middle}}
.sz{{float:right;color:#6e7681;font-size:12px}}
.erow{{padding:2px 0}}
</style></head><body><div class="wrap">
<div class="side">
<h1>{html.escape(os.path.basename(root))}</h1>
<div style="color:#6e7681;font-size:11px;word-break:break-all">{html.escape(root)}</div>
<h2>Summary</h2>
<div class="stat">{stats['files']}<small> files</small></div>
<div class="stat">{stats['dirs']}<small> dirs</small></div>
<div class="stat">{human(stats['size'])}<small> total</small></div>
<div class="stat">{len(stats['exts'])}<small> types</small></div>
<h2>File types</h2>{ext_rows}
</div>
<div class="main">{render_node(tree)}</div>
</div></body></html>"""

    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"Wrote {out}  ({stats['files']} files, {stats['dirs']} dirs, {human(stats['size'])})")


if __name__ == "__main__":
    main()
