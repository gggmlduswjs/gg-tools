---
name: codebase-visualizer
description: Generates an interactive collapsible HTML tree of a project's file structure — collapsible directories, per-file sizes, type-based colors, and a summary sidebar (file/dir counts, total size, file types). Use when exploring a new repo, understanding project layout, or spotting large files. Stdlib-only, no dependencies.
---

# Codebase Visualizer

Run the script from the project root:

```bash
python "%CLAUDE_SKILL_DIR%/scripts/visualize.py" .
```

(or on POSIX: `python3 "$CLAUDE_SKILL_DIR/scripts/visualize.py" .`)

It writes `codebase-map.html` in the current directory. Open it in a browser.

Options:
- First arg: root path to scan (default `.`).
- `--out <file>`: output path (default `codebase-map.html`).

Skips `.git`, `node_modules`, `__pycache__`, `.venv`/`venv`, `dist`, `build`, `.mypy_cache`, `.pytest_cache`, `staticfiles`.
