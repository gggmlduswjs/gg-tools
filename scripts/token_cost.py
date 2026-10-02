#!/usr/bin/env python3
"""Claude Code 토큰 소비 집계 — 어디서 새는지 본다. stdlib only.

왜 있나 (2026-08-06): 세션 로그(`~/.claude/projects/**/*.jsonl`)에 요청별 usage 가
전부 남아 있는데 **아무도 집계하지 않고 있었다.** 처음 재보니 7일에 cache_read
191억 토큰 · 요청당 26만이었다. 숫자를 모르면 줄일 수도 없다.

무엇을 보나:
  · output          가장 비싼 항목. 실제로 '일한 양'에 가깝다.
  · cache_read      컨텍스트를 다시 읽는 양. 싸지만 **양이 압도적**이라 총액을 지배한다.
  · cache_creation  캐시를 새로 만든 양. 이게 크면 컨텍스트가 자꾸 갈아엎힌다는 뜻.
  · input           캐시 미적중분. 0 에 가까워야 정상.

경고(gate) 두 가지 — 임계는 실측에서 왔다:
  ① 캐시 적중률 < 90%    현재 정상치는 96~100%. 떨어지면 같은 컨텍스트를 매번 새로
                         만든다는 뜻이고, cache_creation 은 cache_read 보다 훨씬 비싸다.
  ② cache_creation 비중   전체 입력의 5% 를 넘으면 컨텍스트가 불안정하다.

가격은 넣지 않았다 — 하드코딩하면 반드시 낡고, 낡은 금액은 없느니만 못하다.
토큰으로 재고 비교는 상대치로 한다.

    python token_cost.py               최근 7일
    python token_cost.py --days 30
    python token_cost.py --json        기계용
    python token_cost.py --selftest
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

CACHE_HIT_WARN = 90.0     # % 미만이면 경고
CREATION_SHARE_WARN = 5.0  # 전체 입력 중 cache_creation 비중 % 초과면 경고


def collect(root, days):
    """(프로젝트별, 모델별, 세션수, 요청수). mtime 으로 거른다 — 로그에 종료시각이 없다."""
    cutoff = time.time() - days * 86400
    proj = defaultdict(lambda: defaultdict(int))
    models = defaultdict(lambda: defaultdict(int))
    sessions = reqs = 0
    for p in Path(root).rglob("*.jsonl"):
        try:
            if p.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        sessions += 1
        name = p.parent.name
        for line in p.open(encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get("message") or {}
            u = msg.get("usage")
            if not u:
                continue
            reqs += 1
            model = msg.get("model") or "?"
            for k in KEYS:
                v = u.get(k, 0) or 0
                proj[name][k] += v
                models[model][k] += v
    return proj, models, sessions, reqs


def totals(buckets):
    t = defaultdict(int)
    for v in buckets.values():
        for k in KEYS:
            t[k] += v[k]
    return t


def cache_hit(v):
    """입력 중 캐시로 해결된 비율(%). 입력이 없으면 100(=문제 없음)."""
    total_in = v["input_tokens"] + v["cache_creation_input_tokens"] + v["cache_read_input_tokens"]
    return 100.0 * v["cache_read_input_tokens"] / total_in if total_in else 100.0


def warnings_for(v, label):
    out = []
    total_in = v["input_tokens"] + v["cache_creation_input_tokens"] + v["cache_read_input_tokens"]
    if not total_in:
        return out
    hit = cache_hit(v)
    if hit < CACHE_HIT_WARN:
        out.append(f"{label}: 캐시 적중 {hit:.1f}% (< {CACHE_HIT_WARN:g}%) — "
                   f"같은 컨텍스트를 매번 새로 만들고 있다")
    share = 100.0 * v["cache_creation_input_tokens"] / total_in
    if share > CREATION_SHARE_WARN:
        out.append(f"{label}: cache_creation 이 입력의 {share:.1f}% (> {CREATION_SHARE_WARN:.0f}%) — "
                   f"컨텍스트가 자꾸 갈아엎히고 있다")
    return out


def human(n):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n / div:.1f}{unit}"
    return str(n)


GATE_STAMP = Path.home() / ".claude" / "cache" / "token_gate.json"


def gate(argv):
    """SessionStart 용 — 하루 1회만 재고, 임계를 넘을 때만 말한다.

    측정만 있고 자동이 아니면 안 불린다(오늘 하루에만 같은 패턴을 여덟 번 봤다).
    그렇다고 매 세션 300개 파일을 파싱하면 세션 시작이 느려지므로 날짜로 잠근다.
    조용한 게 정상이다 — 임계를 넘을 때만 한 줄 뜬다.
    """
    today = time.strftime("%Y-%m-%d")
    try:
        if json.loads(GATE_STAMP.read_text(encoding="utf-8")).get("date") == today:
            return 0                     # 오늘 이미 쟀다
    except Exception:
        pass

    proj, _, sessions, reqs = collect(ROOT, 7)
    tot = totals(proj)
    warns = warnings_for(tot, "전체")
    for name, v in proj.items():
        if v["cache_read_input_tokens"] > tot["cache_read_input_tokens"] * 0.05:
            warns += warnings_for(v, name[:40])

    try:
        GATE_STAMP.parent.mkdir(parents=True, exist_ok=True)
        GATE_STAMP.write_text(json.dumps({
            "date": today, "sessions": sessions, "requests": reqs,
            "cache_hit_pct": round(cache_hit(tot), 2),
            "output_tokens": tot["output_tokens"],
            "cache_read_input_tokens": tot["cache_read_input_tokens"],
        }, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass

    if warns:
        sys.stderr.write("\n[token_gate] 최근 7일 토큰 효율이 임계를 벗어났다:\n")
        for w in warns:
            sys.stderr.write(f"  · {w}\n")
        sys.stderr.write("  자세히: python ~/claude/scripts/token_cost.py\n\n")
    return 0


def main(argv):
    if "--gate" in argv:
        return gate(argv)
    days = 7
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])
    proj, models, sessions, reqs = collect(ROOT, days)
    tot = totals(proj)

    if "--json" in argv:
        print(json.dumps({
            "days": days, "sessions": sessions, "requests": reqs,
            "totals": dict(tot), "cache_hit_pct": round(cache_hit(tot), 2),
            "projects": {k: dict(v) for k, v in proj.items()},
            "models": {k: dict(v) for k, v in models.items()},
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"최근 {days}일 · 세션 {sessions}개 · 요청 {reqs:,}건")
    if not reqs:
        print("  (기록 없음)")
        return 0
    print(f"  output          {human(tot['output_tokens']):>8}   ← 가장 비싼 항목")
    print(f"  cache_read      {human(tot['cache_read_input_tokens']):>8}   "
          f"(요청당 {tot['cache_read_input_tokens'] // reqs:,})")
    print(f"  cache_creation  {human(tot['cache_creation_input_tokens']):>8}")
    print(f"  input           {human(tot['input_tokens']):>8}   ← 0 에 가까워야 정상")
    print(f"  캐시 적중률      {cache_hit(tot):.1f}%")

    print("\n프로젝트별 (output 순):")
    for name, v in sorted(proj.items(), key=lambda kv: -kv[1]["output_tokens"])[:8]:
        print(f"  {name[:44]:46} out {human(v['output_tokens']):>7}  "
              f"cache_read {human(v['cache_read_input_tokens']):>7}  적중 {cache_hit(v):.0f}%")

    print("\n모델별 (output 순):")
    for name, v in sorted(models.items(), key=lambda kv: -kv[1]["output_tokens"])[:6]:
        share = 100.0 * v["output_tokens"] / max(tot["output_tokens"], 1)
        print(f"  {name[:36]:38} out {human(v['output_tokens']):>7}  ({share:.0f}%)")

    warns = warnings_for(tot, "전체")
    for name, v in sorted(proj.items(), key=lambda kv: -kv[1]["cache_read_input_tokens"])[:8]:
        if v["cache_read_input_tokens"] > tot["cache_read_input_tokens"] * 0.02:  # 미미한 건 제외
            warns += warnings_for(v, name[:40])
    if warns:
        print("\n⚠️ 경고:")
        for w in warns:
            print("  ·", w)
    else:
        print("\n✅ 캐시 효율 정상 — 임계 넘는 항목 없음")
    return 0


def _selftest():
    import tempfile
    root = Path(tempfile.mkdtemp())
    (root / "projA").mkdir()
    (root / "projB").mkdir()

    def write(p, rows):
        with p.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"message": {"model": r.pop("model", "m1"), "usage": r}}) + "\n")
            f.write('{"type":"user","message":{"role":"user"}}\n')   # usage 없는 줄
            f.write("not json\n")                                    # 깨진 줄

    write(root / "projA" / "s1.jsonl", [
        {"input_tokens": 0, "output_tokens": 100,
         "cache_creation_input_tokens": 10, "cache_read_input_tokens": 990},
    ])
    write(root / "projB" / "s2.jsonl", [
        {"model": "m2", "input_tokens": 500, "output_tokens": 50,
         "cache_creation_input_tokens": 400, "cache_read_input_tokens": 100},
    ])

    proj, models, sessions, reqs = collect(root, 7)
    assert sessions == 2 and reqs == 2, (sessions, reqs)
    assert set(models) == {"m1", "m2"}, models
    t = totals(proj)
    assert t["output_tokens"] == 150 and t["cache_read_input_tokens"] == 1090, dict(t)

    # 깨진 줄·usage 없는 줄이 개수를 부풀리면 안 된다
    assert reqs == 2

    # 적중률: projA 990/1000 = 99% · projB 100/1000 = 10%
    assert round(cache_hit(proj["projA"])) == 99, cache_hit(proj["projA"])
    assert round(cache_hit(proj["projB"])) == 10, cache_hit(proj["projB"])

    # 경고는 나쁜 쪽에만 붙는다
    assert warnings_for(proj["projA"], "A") == [], warnings_for(proj["projA"], "A")
    wb = warnings_for(proj["projB"], "B")
    assert any("캐시 적중" in w for w in wb) and any("cache_creation" in w for w in wb), wb

    # 입력이 0 이면 0 으로 나누지 않고 '문제 없음'으로 본다
    assert cache_hit(defaultdict(int)) == 100.0
    assert warnings_for(defaultdict(int), "빈") == []

    # 기간 밖 파일은 세지 않는다
    import os
    old = root / "projA" / "old.jsonl"
    write(old, [{"input_tokens": 1, "output_tokens": 1,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}])
    os.utime(old, (time.time() - 30 * 86400,) * 2)
    assert collect(root, 7)[3] == 2, "30일 전 파일이 7일 집계에 들어왔다"
    assert collect(root, 60)[3] == 3

    print("token_cost selftest OK (12 cases · 집계·적중률·경고·기간필터·깨진줄)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main(sys.argv[1:]))
