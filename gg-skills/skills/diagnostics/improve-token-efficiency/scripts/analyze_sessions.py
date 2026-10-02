#!/usr/bin/env python3
"""Analyze Claude Code session JSONL files for token/context efficiency.

Usage:
  python3 analyze_sessions.py --repo /path/to/repo [--out /tmp/session_analysis.json]
  python3 analyze_sessions.py --sessions-dir ~/.claude/projects/-Users-x-Projects-Foo

The script finds the encoded session directory under ~/.claude/projects/,
parses every .jsonl file, extracts per-session token usage from each
assistant message's `usage` field, applies per-model pricing, and
computes a 4-axis efficiency score.
"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict

# Anthropic pricing (USD per 1M tokens). Keys match the exact model string the
# CLI records in `message.model`. Add new rows when new models ship.
PRICING = {
    "claude-opus-4-6":   {"in": 15.00, "out": 75.00, "cw5": 18.75, "cw1h": 30.00, "cr": 1.50},
    "claude-opus-4-7":   {"in": 15.00, "out": 75.00, "cw5": 18.75, "cw1h": 30.00, "cr": 1.50},
    "claude-sonnet-4-6": {"in":  3.00, "out": 15.00, "cw5":  3.75, "cw1h":  6.00, "cr": 0.30},
    "claude-sonnet-4-5": {"in":  3.00, "out": 15.00, "cw5":  3.75, "cw1h":  6.00, "cr": 0.30},
    "claude-haiku-4-5":  {"in":  0.80, "out":  4.00, "cw5":  1.00, "cw1h":  1.60, "cr": 0.08},
    "<synthetic>":       {"in":  0.00, "out":  0.00, "cw5":  0.00, "cw1h":  0.00, "cr": 0.00},
}
# Opus default for unknown models (conservative = higher estimate, so the
# report doesn't silently under-report cost).
DEFAULT_PRICE = PRICING["claude-opus-4-6"]


def encode_repo_path(repo_path):
    """Turn /Users/x/Projects/Foo into -Users-x-Projects-Foo."""
    abs_path = os.path.abspath(os.path.expanduser(repo_path))
    return abs_path.replace("/", "-")


def resolve_sessions_dir(args):
    if args.sessions_dir:
        return os.path.expanduser(args.sessions_dir)
    repo = args.repo or os.getcwd()
    encoded = encode_repo_path(repo)
    return os.path.expanduser(f"~/.claude/projects/{encoded}")


def price_for(model):
    if model in PRICING:
        return PRICING[model]
    # Warn once per unknown model
    if model and model not in price_for._warned:
        print(f"[warn] unknown model: {model}, applying Opus default pricing", file=sys.stderr)
        price_for._warned.add(model)
    return DEFAULT_PRICE
price_for._warned = set()


def analyze_session(path):
    stats = {
        "session_id": os.path.basename(path).replace(".jsonl", ""),
        "file_size": os.path.getsize(path),
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_create_5m": 0,
        "cache_create_1h": 0,
        "cache_read": 0,
        "num_assistant_msgs": 0,
        "num_user_msgs": 0,
        "num_tool_calls": 0,
        "tool_use_counter": defaultdict(int),
        "file_read_counter": defaultdict(int),
        "first_ts": None,
        "last_ts": None,
        "models": set(),
        "cost_usd": 0.0,
        "image_count": 0,
        "compact_count": 0,
    }

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue

                ts = rec.get("timestamp")
                if ts:
                    if stats["first_ts"] is None:
                        stats["first_ts"] = ts
                    stats["last_ts"] = ts

                rtype = rec.get("type")

                if rtype == "user":
                    stats["num_user_msgs"] += 1
                    msg = rec.get("message", {})
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "image":
                                stats["image_count"] += 1

                elif rtype == "assistant":
                    stats["num_assistant_msgs"] += 1
                    msg = rec.get("message", {})
                    model = msg.get("model", "") or ""
                    if model:
                        stats["models"].add(model)
                    usage = msg.get("usage", {})
                    price = price_for(model)

                    inp = usage.get("input_tokens", 0)
                    out = usage.get("output_tokens", 0)
                    cw = usage.get("cache_creation_input_tokens", 0)
                    cr = usage.get("cache_read_input_tokens", 0)

                    cw_detail = usage.get("cache_creation", {}) or {}
                    cw5 = cw_detail.get("ephemeral_5m_input_tokens", 0)
                    cw1h = cw_detail.get("ephemeral_1h_input_tokens", 0)
                    if cw5 + cw1h == 0 and cw > 0:
                        # Older CLI: no breakdown. Assume 5m (cheaper default).
                        cw5 = cw

                    stats["input_tokens"] += inp
                    stats["output_tokens"] += out
                    stats["cache_create_5m"] += cw5
                    stats["cache_create_1h"] += cw1h
                    stats["cache_read"] += cr

                    stats["cost_usd"] += (
                        inp * price["in"] / 1e6
                        + out * price["out"] / 1e6
                        + cw5 * price["cw5"] / 1e6
                        + cw1h * price["cw1h"] / 1e6
                        + cr * price["cr"] / 1e6
                    )

                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "tool_use":
                                stats["num_tool_calls"] += 1
                                tname = c.get("name", "unknown")
                                stats["tool_use_counter"][tname] += 1
                                if tname == "Read":
                                    fp = c.get("input", {}).get("file_path", "")
                                    if fp:
                                        stats["file_read_counter"][fp] += 1

                elif rtype == "compact-summary":
                    stats["compact_count"] += 1
    except Exception as e:
        stats["error"] = str(e)

    total_input_any = (
        stats["input_tokens"]
        + stats["cache_create_5m"]
        + stats["cache_create_1h"]
        + stats["cache_read"]
    )
    stats["total_input_tokens"] = total_input_any
    stats["cache_hit_ratio"] = (stats["cache_read"] / total_input_any) if total_input_any else 0.0
    stats["uncached_ratio"] = (stats["input_tokens"] / total_input_any) if total_input_any else 0.0
    stats["output_ratio"] = (stats["output_tokens"] / total_input_any) if total_input_any else 0.0

    stats["redundant_reads"] = sum((c - 1) for c in stats["file_read_counter"].values() if c > 1)
    stats["unique_files_read"] = len(stats["file_read_counter"])
    stats["total_file_reads"] = sum(stats["file_read_counter"].values())
    stats["had_image"] = stats["image_count"] > 0

    stats["models"] = sorted(list(stats["models"]))
    stats["tool_use_counter"] = dict(stats["tool_use_counter"])
    stats.pop("file_read_counter", None)
    return stats


def score_session(s):
    """4-axis 0–100 scoring. Weighted: cache 40 / density 20 / redundancy 20 / tool 20."""
    tot = s["total_input_tokens"] or 1

    # Cache utilization: cache_read / total_input, 85% = full marks.
    cache_score = min(100, s["cache_hit_ratio"] / 0.85 * 100)

    # Output density: sweet spot ~2%. Penalize too low (churn) and too high (monologue).
    od = s["output_ratio"]
    if od < 0.005:
        density_score = od / 0.005 * 60
    elif od < 0.02:
        density_score = 60 + (od - 0.005) / 0.015 * 40
    elif od < 0.05:
        density_score = 100 - (od - 0.02) / 0.03 * 20
    else:
        density_score = max(40, 80 - (od - 0.05) * 200)

    # Read redundancy: penalize per redundant read as share of total reads.
    total_reads = s["total_file_reads"] or 1
    redundancy_ratio = s["redundant_reads"] / total_reads
    redundancy_score = max(0, 100 - redundancy_ratio * 200)

    # Tool economy: healthy 2–10 tool calls per 1k output tokens. >20 = thrash.
    out_k = max(1, s["output_tokens"] / 1000)
    tpk = s["num_tool_calls"] / out_k
    if tpk < 2:
        tool_score = 70 + tpk * 15
    elif tpk < 10:
        tool_score = 100 - (tpk - 2) * 2
    elif tpk < 20:
        tool_score = 84 - (tpk - 10) * 4
    else:
        tool_score = max(0, 44 - (tpk - 20) * 2)

    composite = (
        cache_score * 0.40
        + density_score * 0.20
        + redundancy_score * 0.20
        + tool_score * 0.20
    )

    return {
        "cache_score": round(cache_score, 1),
        "density_score": round(density_score, 1),
        "redundancy_score": round(redundancy_score, 1),
        "tool_score": round(tool_score, 1),
        "composite": round(composite, 1),
        "grade": grade_of(composite),
    }


def grade_of(score):
    for threshold, grade in [
        (90, "A+"), (85, "A"), (80, "A-"), (75, "B+"), (70, "B"),
        (65, "B-"), (60, "C+"), (55, "C"), (50, "C-"), (40, "D"),
    ]:
        if score >= threshold:
            return grade
    return "F"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="Repository path (default: cwd)")
    ap.add_argument("--sessions-dir", help="Direct path to ~/.claude/projects/<encoded>/")
    ap.add_argument("--out", default="/tmp/session_analysis.json", help="Output JSON path")
    args = ap.parse_args()

    sessions_dir = resolve_sessions_dir(args)

    if not os.path.isdir(sessions_dir):
        print(f"[error] sessions dir not found: {sessions_dir}", file=sys.stderr)
        print("        This repo may have never been opened with Claude Code.", file=sys.stderr)
        sys.exit(2)

    files = sorted(glob.glob(os.path.join(sessions_dir, "*.jsonl")))
    if not files:
        print(f"[error] no .jsonl files in {sessions_dir}", file=sys.stderr)
        sys.exit(2)

    print(f"[info] sessions dir: {sessions_dir}")
    print(f"[info] found {len(files)} session files")

    results = []
    for fp in files:
        s = analyze_session(fp)
        if s["total_input_tokens"] == 0 and s["output_tokens"] == 0:
            continue
        s["scores"] = score_session(s)
        results.append(s)

    if not results:
        print("[error] all sessions have empty usage (old CLI?), nothing to report", file=sys.stderr)
        sys.exit(2)

    totals = {
        "sessions_dir": sessions_dir,
        "sessions": len(results),
        "input_tokens": sum(r["input_tokens"] for r in results),
        "output_tokens": sum(r["output_tokens"] for r in results),
        "cache_create_5m": sum(r["cache_create_5m"] for r in results),
        "cache_create_1h": sum(r["cache_create_1h"] for r in results),
        "cache_read": sum(r["cache_read"] for r in results),
        "cost_usd": sum(r["cost_usd"] for r in results),
        "total_input_tokens": sum(r["total_input_tokens"] for r in results),
        "num_tool_calls": sum(r["num_tool_calls"] for r in results),
        "redundant_reads": sum(r["redundant_reads"] for r in results),
        "image_count": sum(r["image_count"] for r in results),
        "compact_count": sum(r["compact_count"] for r in results),
    }
    totals["cache_hit_ratio"] = (
        totals["cache_read"] / totals["total_input_tokens"] if totals["total_input_tokens"] else 0
    )

    results.sort(key=lambda r: r["cost_usd"], reverse=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"totals": totals, "sessions": results}, f, default=str, indent=2, ensure_ascii=False)

    print(f"[ok] wrote {args.out}")
    print(f"     {len(results)} sessions, ${totals['cost_usd']:.2f}, cache hit {totals['cache_hit_ratio']*100:.1f}%")


if __name__ == "__main__":
    main()
