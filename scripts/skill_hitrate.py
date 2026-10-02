#!/usr/bin/env python
"""스킬·에이전트 Hit Rate — 세션 로그에서 '실제로 불린 것'을 센다.

보유 자산은 description 만으로도 매 세션 비용을 낸다. 안 불리는 자산은
0 이 아니라 음수다. 그 판정에 쓸 숫자를 낸다.

    python skill_hitrate.py [--days N]
"""
import json, os, re, sys
from collections import Counter, defaultdict

HOME = os.path.expanduser("~")
LOGS = os.path.join(HOME, ".claude", "projects")
SKILLS_DIR = os.path.join(HOME, ".claude", "skills")

RE_SKILL = re.compile(r'"name":"Skill","input":\{"skill":"([^"]+)"')
RE_AGENT = re.compile(r'"subagent_type":"([^"]+)"')
RE_CMD = re.compile(r"<command-name>/?([A-Za-z0-9_\-가-힣]+)</command-name>")
RE_DATE = re.compile(r'"timestamp":"(\d{4}-\d\d-\d\d)')

days = None
if "--days" in sys.argv:
    days = int(sys.argv[sys.argv.index("--days") + 1])

skill_hits, agent_hits, cmd_hits = Counter(), Counter(), Counter()
by_project = defaultdict(Counter)
dates, files, lines = set(), 0, 0

for root, _, names in os.walk(LOGS):
    proj = os.path.basename(root)
    for n in names:
        if not n.endswith(".jsonl"):
            continue
        files += 1
        with open(os.path.join(root, n), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                lines += 1
                d = RE_DATE.search(line)
                if d:
                    dates.add(d.group(1))
                for s in RE_SKILL.findall(line):
                    skill_hits[s] += 1
                    by_project[proj][s] += 1
                for a in RE_AGENT.findall(line):
                    agent_hits[a] += 1
                for c in RE_CMD.findall(line):
                    cmd_hits[c] += 1

# 보유 스킬 = ~/.claude/skills 의 폴더
owned = sorted(d for d in os.listdir(SKILLS_DIR)
               if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md")))


def desc_bytes(name):
    """description 길이 = 매 세션 상시 비용"""
    p = os.path.join(SKILLS_DIR, name, "SKILL.md")
    t = open(p, encoding="utf-8").read()
    m = re.search(r"^---\n(.*?)\n---", t, re.S)
    if not m:
        return 0
    dm = re.search(r"^description:\s*(.*?)(?=\n[a-z-]+:|\Z)", m.group(1), re.S | re.M)
    return len(dm.group(1).strip().encode()) if dm else 0


called = {s: skill_hits[s] + cmd_hits[s] for s in owned}
cost = {s: desc_bytes(s) for s in owned}
dead = [s for s in owned if called[s] == 0]

span = f"{min(dates)} ~ {max(dates)}" if dates else "?"
print(f"세션 로그 {files}개 · {lines:,}줄 · {span}\n")

print(f"{'스킬':<28} {'호출':>4}  {'상시비용':>7}")
print("-" * 45)
for s in sorted(owned, key=lambda x: (-called[x], -cost[x])):
    mark = "" if called[s] else "  ← 0회"
    print(f"{s:<28} {called[s]:>4}  {cost[s]:>6}B{mark}")

print(f"\n미호출 {len(dead)}/{len(owned)}개 · 그 설명만 매 세션 "
      f"{sum(cost[s] for s in dead):,}B (전체 {sum(cost.values()):,}B 중)")

if agent_hits:
    print("\n에이전트 위임")
    for a, c in agent_hits.most_common():
        print(f"  {a:<26} {c:>4}회")

ext = {k: v for k, v in (skill_hits + cmd_hits).items() if k not in called}
if ext:
    print("\n내장·플러그인 스킬 (보유 목록 밖)")
    for k, v in Counter(ext).most_common(12):
        print(f"  {k:<26} {v:>4}회")
