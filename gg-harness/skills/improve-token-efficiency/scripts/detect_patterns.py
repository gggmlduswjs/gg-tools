#!/usr/bin/env python3
"""Detect 5 inefficiency patterns in Claude Code sessions with $ waste estimates.

Each detector follows an exact formula from the spec — no fuzzy heuristics.

Detectors:
  1. context-bloat       : context > 100k for 20+ consecutive turns without a >50% drop (no compact).
                           Waste = Σ max(0, context - 80k) per affected turn × cache_read price.
  2. giant-tool-outputs  : tool_result ≥ 50k chars (~12.5k tokens).
                           Waste = result_tokens × remaining_turns_in_session × cache_read price.
  3. poor-cache-util     : per-turn cache_hit < 50% AND context > 30k.
                           Waste = cache_create × (write_price − read_price).
  4. duplicate-tools     : SHA-256 of (tool_name, input). Repeats are pure waste.
                           Waste = result_tokens (re-paid + sitting in context) × cache_write price.
  5. subagent-overuse    : ≥5 Agent calls AND avg subagent result ≤ 2k tokens (proxy for ≤3 turns).
                           Waste = num_calls × ~3k overhead per call × cache_write price.

Usage:
  python3 detect_patterns.py --repo /path/to/repo --out /tmp/pattern_analysis.json
"""
import argparse
import glob
import hashlib
import json
import os
import sys
from collections import defaultdict

# Pricing (USD per 1M tokens). We price waste at Opus rates; if the actual
# session was Sonnet, the dollar number is overstated by ~5x — but Sonnet
# sessions are also cheap so the overall % impact is roughly right.
OPUS_READ = 1.50
OPUS_W1H = 30.00
OPUS_OUT = 75.00

# Thresholds (from the user's spec)
CONTEXT_HIGH_TOKENS = 100_000          # P1: "context exceeds 100k"
CONTEXT_BASELINE = 80_000              # P1: "tokens above 80k per turn"
CONSEC_TURNS_REQUIRED = 20             # P1: "over 20+ turns"
COMPACT_DROP_RATIO = 0.50              # P1: ">50% drop signals compact"

GIANT_TOOL_CHARS = 50_000              # P2: ≥ 50k chars
CHARS_PER_TOKEN = 4                    # ~12.5k tokens for 50k chars

CACHE_HIT_FLOOR = 0.50                 # P3: hit ratio < 50%
CONTEXT_FLOOR_FOR_CACHE = 30_000       # P3: context > 30k

SUBAGENT_MIN_CALLS = 5                 # P5: ≥ 5 Task calls
TRIVIAL_RESULT_TOKENS = 2000           # P5: avg result ≤ 2k → ≤3 turns proxy
SUBAGENT_OVERHEAD_TOKENS = 3000        # P5: per-call system prompt + framing


def encode_repo_path(p):
    return os.path.abspath(os.path.expanduser(p)).replace("/", "-")


def stringify(obj):
    """Stable string for hashing tool inputs."""
    return json.dumps(obj, sort_keys=True, default=str)


def sha256_short(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def estimate_tokens_from_content(content):
    """Approximate token count for arbitrary tool result content (str or list)."""
    if isinstance(content, str):
        return len(content) // CHARS_PER_TOKEN
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    total += len(item.get("text", "")) // CHARS_PER_TOKEN
                elif item.get("type") == "image":
                    total += 1500  # rough per-image token estimate
        return total
    return 0


def chars_of_content(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(
            len(item.get("text", "")) if isinstance(item, dict) and item.get("type") == "text" else 0
            for item in content
        )
    return 0


def analyze_session(path):
    """Walk one session JSONL, build per-turn trajectories, run all 5 detectors."""
    sid = os.path.basename(path).replace(".jsonl", "")
    try:
        with open(path) as f:
            records = [json.loads(line) for line in f if line.strip()]
    except Exception:
        return None

    # Index assistant turns and capture per-turn metrics in order.
    assistant_turns = []           # list of dicts: {idx, input, cache_read, cache_create, output, tool_uses}
    pending_tool_uses = {}         # tool_use_id → {name, input, turn_idx}

    # Map tool_use_id → result content (chars + token estimate). Walk records
    # in order; user records come AFTER the corresponding assistant tool_use.
    tool_results = {}              # tool_use_id → {chars, tokens, content_kind}

    for rec in records:
        rtype = rec.get("type")
        if rtype == "assistant":
            msg = rec.get("message", {})
            usage = msg.get("usage", {})
            cw_detail = usage.get("cache_creation", {}) or {}
            cw_total = (
                cw_detail.get("ephemeral_5m_input_tokens", 0)
                + cw_detail.get("ephemeral_1h_input_tokens", 0)
            )
            if cw_total == 0:
                cw_total = usage.get("cache_creation_input_tokens", 0)

            inp = usage.get("input_tokens", 0)
            cr = usage.get("cache_read_input_tokens", 0)
            out = usage.get("output_tokens", 0)
            context_size = inp + cr + cw_total

            tool_uses = []
            content = msg.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        tu = {
                            "id": c.get("id"),
                            "name": c.get("name", "unknown"),
                            "input": c.get("input", {}),
                        }
                        tool_uses.append(tu)
                        pending_tool_uses[tu["id"]] = {
                            "name": tu["name"],
                            "input": tu["input"],
                            "turn_idx": len(assistant_turns),
                        }

            assistant_turns.append({
                "idx": len(assistant_turns),
                "input_tokens": inp,
                "cache_read": cr,
                "cache_create": cw_total,
                "output_tokens": out,
                "context_size": context_size,
                "tool_uses": tool_uses,
            })

        elif rtype == "user":
            # Tool results come back as user messages with tool_result blocks.
            msg = rec.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        tu_id = c.get("tool_use_id")
                        result_content = c.get("content")
                        chars = chars_of_content(result_content)
                        tokens = estimate_tokens_from_content(result_content)
                        tool_results[tu_id] = {"chars": chars, "tokens": tokens}

    n_turns = len(assistant_turns)
    if n_turns == 0:
        return None

    # Run each detector.
    findings = {}

    # --- P1: context-bloat ---
    p1 = detect_context_bloat(assistant_turns)
    if p1["triggered"]:
        findings["context_bloat"] = p1

    # --- P2: giant-tool-outputs ---
    p2 = detect_giant_tool_outputs(assistant_turns, tool_results, n_turns)
    if p2["triggered"]:
        findings["giant_tool_outputs"] = p2

    # --- P3: poor-cache-util ---
    p3 = detect_poor_cache_util(assistant_turns)
    if p3["triggered"]:
        findings["poor_cache_util"] = p3

    # --- P4: duplicate-tools ---
    p4 = detect_duplicate_tools(assistant_turns, tool_results)
    if p4["triggered"]:
        findings["duplicate_tools"] = p4

    # --- P5: subagent-overuse ---
    p5 = detect_subagent_overuse(assistant_turns, tool_results)
    if p5["triggered"]:
        findings["subagent_overuse"] = p5

    return {
        "session_id": sid,
        "n_turns": n_turns,
        "peak_context": max((t["context_size"] for t in assistant_turns), default=0),
        "findings": findings,
    }


# ----------------- detectors -----------------

def detect_context_bloat(turns):
    """P1: context > 100k for 20+ consecutive turns, no >50% drop."""
    n = len(turns)
    # Find longest run of consecutive turns where context_size > CONTEXT_HIGH_TOKENS
    # AND no consecutive turn has a > COMPACT_DROP_RATIO drop within that run.
    best_run = []
    current_run = []
    for i, t in enumerate(turns):
        if t["context_size"] > CONTEXT_HIGH_TOKENS:
            # Check if previous turn (if any) had a big drop FROM here — actually
            # "drop by >50%" between consecutive turns signals compact, breaks the run.
            if current_run:
                prev_ctx = turns[current_run[-1]]["context_size"]
                this_ctx = t["context_size"]
                if prev_ctx > 0 and (prev_ctx - this_ctx) / prev_ctx > COMPACT_DROP_RATIO:
                    # compact happened — break run
                    if len(current_run) > len(best_run):
                        best_run = current_run
                    current_run = [i]
                    continue
            current_run.append(i)
        else:
            if len(current_run) > len(best_run):
                best_run = current_run
            current_run = []
    if len(current_run) > len(best_run):
        best_run = current_run

    if len(best_run) < CONSEC_TURNS_REQUIRED:
        return {"triggered": False}

    # Waste: sum of (context - 80k) for those turns × cache_read price
    waste_tokens = sum(max(0, turns[i]["context_size"] - CONTEXT_BASELINE) for i in best_run)
    waste_usd = waste_tokens * OPUS_READ / 1e6

    return {
        "triggered": True,
        "evidence": f"{len(best_run)} consecutive turns above 100k context, no >50% drop",
        "consec_turns": len(best_run),
        "peak_context": max(turns[i]["context_size"] for i in best_run),
        "waste_tokens": int(waste_tokens),
        "waste_usd": round(waste_usd, 2),
        "fix": "Run /compact when cumulative input passes 200k. Branch new sessions for unrelated tasks.",
    }


def detect_giant_tool_outputs(turns, tool_results, n_turns):
    """P2: any tool_result ≥ 50k chars. Waste = tokens × remaining_turns × cache_read."""
    giants = []
    for turn in turns:
        for tu in turn["tool_uses"]:
            res = tool_results.get(tu["id"])
            if not res:
                continue
            if res["chars"] >= GIANT_TOOL_CHARS:
                remaining = n_turns - turn["idx"] - 1
                waste_tokens = res["tokens"] * remaining
                giants.append({
                    "tool": tu["name"],
                    "turn_idx": turn["idx"],
                    "chars": res["chars"],
                    "tokens": res["tokens"],
                    "remaining_turns": remaining,
                    "waste_tokens": waste_tokens,
                })

    if not giants:
        return {"triggered": False}

    total_waste_tokens = sum(g["waste_tokens"] for g in giants)
    waste_usd = total_waste_tokens * OPUS_READ / 1e6

    return {
        "triggered": True,
        "evidence": f"{len(giants)} tool result(s) ≥ 50k chars, persisting in context",
        "count": len(giants),
        "biggest_chars": max(g["chars"] for g in giants),
        "waste_tokens": int(total_waste_tokens),
        "waste_usd": round(waste_usd, 2),
        "samples": giants[:3],
        "fix": "Pipe through head/grep/wc before reading. Truncate Bash dumps. /compact after big reads.",
    }


def detect_poor_cache_util(turns):
    """P3: per-turn cache_hit < 50% AND context > 30k. Waste = cache_create × (write − read)."""
    bad_turns = []
    for t in turns:
        if t["context_size"] < CONTEXT_FLOOR_FOR_CACHE:
            continue
        cr, cw = t["cache_read"], t["cache_create"]
        if cr + cw == 0:
            continue
        hit = cr / (cr + cw + t["input_tokens"])
        if hit < CACHE_HIT_FLOOR:
            bad_turns.append({"idx": t["idx"], "hit": round(hit, 3), "cache_create": cw})

    if not bad_turns:
        return {"triggered": False}

    waste_tokens = sum(b["cache_create"] for b in bad_turns)
    # Spread between paying for a write vs a read
    waste_usd = waste_tokens * (OPUS_W1H - OPUS_READ) / 1e6

    return {
        "triggered": True,
        "evidence": f"{len(bad_turns)} turns with cache hit < 50% at context > 30k",
        "bad_turns_count": len(bad_turns),
        "waste_tokens": int(waste_tokens),
        "waste_usd": round(waste_usd, 2),
        "fix": "Stop mutating prompt prefix mid-session. Settle CLAUDE.md before long runs. Avoid late additions.",
    }


def detect_duplicate_tools(turns, tool_results):
    """P4: SHA-256 of (tool_name, input). Duplicates → entire result is waste."""
    seen = {}
    duplicates = []
    for turn in turns:
        for tu in turn["tool_uses"]:
            key = sha256_short(stringify((tu["name"], tu["input"])))
            if key in seen:
                first_idx = seen[key]
                res = tool_results.get(tu["id"], {"tokens": 0, "chars": 0})
                duplicates.append({
                    "tool": tu["name"],
                    "first_turn": first_idx,
                    "dup_turn": turn["idx"],
                    "result_tokens": res["tokens"],
                })
            else:
                seen[key] = turn["idx"]

    if not duplicates:
        return {"triggered": False}

    waste_tokens = sum(d["result_tokens"] for d in duplicates)
    # The duplicate's result re-enters context and gets cached again.
    waste_usd = waste_tokens * OPUS_W1H / 1e6

    # Tool breakdown
    by_tool = defaultdict(int)
    for d in duplicates:
        by_tool[d["tool"]] += 1

    return {
        "triggered": True,
        "evidence": f"{len(duplicates)} exact-duplicate tool calls (same name+input)",
        "duplicate_count": len(duplicates),
        "by_tool": dict(by_tool),
        "waste_tokens": int(waste_tokens),
        "waste_usd": round(waste_usd, 2),
        "samples": duplicates[:3],
        "fix": "Reference earlier results from context instead of re-calling. Especially for Read/Grep/Bash status.",
    }


def detect_subagent_overuse(turns, tool_results):
    """P5: ≥5 Agent calls AND avg result ≤ 2k tokens → trivial farming."""
    agent_calls = []
    for turn in turns:
        for tu in turn["tool_uses"]:
            if tu["name"] in ("Agent", "Task"):
                res = tool_results.get(tu["id"], {"tokens": 0})
                agent_calls.append({"turn_idx": turn["idx"], "result_tokens": res["tokens"]})

    if len(agent_calls) < SUBAGENT_MIN_CALLS:
        return {"triggered": False}

    avg_result = sum(c["result_tokens"] for c in agent_calls) / len(agent_calls)
    if avg_result > TRIVIAL_RESULT_TOKENS:
        return {"triggered": False}

    waste_tokens = len(agent_calls) * SUBAGENT_OVERHEAD_TOKENS
    waste_usd = waste_tokens * OPUS_W1H / 1e6

    return {
        "triggered": True,
        "evidence": f"{len(agent_calls)} Agent calls, avg result {avg_result:.0f} tokens (trivial)",
        "agent_calls": len(agent_calls),
        "avg_result_tokens": round(avg_result, 0),
        "waste_tokens": int(waste_tokens),
        "waste_usd": round(waste_usd, 2),
        "fix": "Inline trivial lookups. Reserve subagents for >5-turn explorations or long parallel work.",
    }


# ----------------- main -----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="Repo path (default cwd)")
    ap.add_argument("--sessions-dir")
    ap.add_argument("--out", default="/tmp/pattern_analysis.json")
    args = ap.parse_args()

    if args.sessions_dir:
        sessions_dir = os.path.expanduser(args.sessions_dir)
    else:
        repo = args.repo or os.getcwd()
        sessions_dir = os.path.expanduser(f"~/.claude/projects/{encode_repo_path(repo)}")

    if not os.path.isdir(sessions_dir):
        print(f"[error] sessions dir not found: {sessions_dir}", file=sys.stderr)
        sys.exit(2)

    files = sorted(glob.glob(os.path.join(sessions_dir, "*.jsonl")))
    print(f"[info] scanning {len(files)} sessions ...")

    sessions = []
    for fp in files:
        s = analyze_session(fp)
        if s:
            sessions.append(s)

    # Aggregate per pattern
    pattern_keys = ["context_bloat", "giant_tool_outputs", "poor_cache_util",
                    "duplicate_tools", "subagent_overuse"]
    pattern_totals = {}
    for key in pattern_keys:
        affected = [s for s in sessions if key in s["findings"]]
        affected.sort(key=lambda s: s["findings"][key]["waste_usd"], reverse=True)
        pattern_totals[key] = {
            "affected_sessions": len(affected),
            "total_waste_usd": round(sum(s["findings"][key]["waste_usd"] for s in affected), 2),
            "total_waste_tokens": sum(s["findings"][key]["waste_tokens"] for s in affected),
            "top_offenders": [
                {
                    "session_id": s["session_id"][:8],
                    "evidence": s["findings"][key]["evidence"],
                    "waste_usd": s["findings"][key]["waste_usd"],
                }
                for s in affected[:5]
            ],
        }

    totals = {
        "sessions_dir": sessions_dir,
        "sessions_total": len(sessions),
        "sessions_with_any_pattern": sum(1 for s in sessions if s["findings"]),
        "patterns": pattern_totals,
        "total_waste_usd": round(sum(p["total_waste_usd"] for p in pattern_totals.values()), 2),
    }

    sessions.sort(
        key=lambda s: sum(f["waste_usd"] for f in s["findings"].values()),
        reverse=True,
    )

    with open(args.out, "w") as f:
        json.dump({"totals": totals, "sessions": sessions}, f, default=str, indent=2)

    print(f"[ok] wrote {args.out}")
    print(f"     {totals['sessions_total']} sessions, {totals['sessions_with_any_pattern']} flagged")
    print(f"     total estimated waste: ${totals['total_waste_usd']:.2f}")
    for k in pattern_keys:
        v = pattern_totals[k]
        print(f"       {k:22s}  {v['affected_sessions']:3d} sessions  ${v['total_waste_usd']:.2f}")


if __name__ == "__main__":
    main()
