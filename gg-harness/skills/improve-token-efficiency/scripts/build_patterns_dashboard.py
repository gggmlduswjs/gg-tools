#!/usr/bin/env python3
"""Render the 5-pattern detector output as an HTML dashboard.

Usage:
  python3 build_patterns_dashboard.py \
    --input /tmp/pattern_analysis.json \
    --out /tmp/patterns_report.html
"""
import argparse
import json
import os
import sys

PATTERN_KO_NAME = {
    "context_bloat": "컨텍스트 부풀림",
    "giant_tool_outputs": "거대 도구 출력",
    "poor_cache_util": "캐시 활용 저조",
    "duplicate_tools": "도구 중복 호출",
    "subagent_overuse": "서브에이전트 과다",
}

PATTERN_META = {
    "context_bloat": {
        "title": "1. 컨텍스트 창이 무한정 부풀어 오름",
        "rule": "컨텍스트 100k 토큰 초과가 연속 20+ turn 이어지고, 그 사이 50% 이상 감소(=compact)가 없음.",
        "formula": "낭비 = Σ max(0, 컨텍스트 − 80k) × cache_read 단가 ($1.50/M).",
        "fix_code": """# CLAUDE.md 에 명시
누적 입력이 200k 를 넘으면 진행 전에 /compact 실행.
주제가 바뀌면 새 세션 시작 — CLAUDE.md 와 MEMORY.md 가
세션 간 컨텍스트를 유지해 주므로 손실 없음.""",
        "fix_summary": "200k 도달 시 /compact, 주제 전환 시 새 세션.",
    },
    "giant_tool_outputs": {
        "title": "2. 거대한 도구 출력이 컨텍스트를 부풀림",
        "rule": "tool_result 가 50k chars(약 12.5k 토큰) 이상 — 이후 모든 turn 의 컨텍스트에 그대로 잔존.",
        "formula": "낭비 = 결과_토큰 × 세션 남은 turn 수 × cache_read 단가.",
        "fix_code": """# Bash: 시끄러운 출력 캐핑
git log --oneline | head -50          # git log 통째로 X
find . -name '*.ts' | wc -l           # 개수 먼저, 목록은 필요할 때만
psql -c 'SELECT count(*) FROM x'      # SELECT * 지양

# 큰 출력이 불가피했다면 즉시:
/compact""",
        "fix_summary": "읽기 전에 head/grep/wc/limit. 큰 출력 후 즉시 /compact.",
    },
    "poor_cache_util": {
        "title": "3. 프롬프트 캐시 활용 저조",
        "rule": "한 turn 의 cache 적중률 < 50% 이면서 컨텍스트 > 30k (= prompt prefix 가 흔들리는 중).",
        "formula": "낭비 = cache_create × (쓰기 단가 − 읽기 단가) = × $28.50/M.",
        "fix_code": """# prefix 무효화의 흔한 원인
- 세션 도중 CLAUDE.md 수정 → 그 아래 전부 무효화
- system reminder 추가/변경 → cache miss
- 세션 도중 모델 전환 → cache miss
- 뒤늦게 이미지/스크린샷 첨부 → prefix 흔들림

# 규칙: 긴 작업 시작 전에 prefix 재료를 모두 확정해 둘 것.""",
        "fix_summary": "긴 세션 전 CLAUDE.md 동결. 도중 prefix 변경 금지.",
    },
    "duplicate_tools": {
        "title": "4. 동일한 도구 호출이 그대로 반복됨",
        "rule": "SHA-256(tool_name, input) 가 동일한 호출 — 같은 호출을 또 함.",
        "formula": "낭비 = 결과_토큰 × cache_write 단가 ($30/M, 결과가 컨텍스트에 재진입하므로).",
        "fix_code": """# Read/Grep/Bash 를 다시 부르기 전에 자문
- 이 답이 대화 위쪽에 이미 있지 않나?
- 마지막 Read 이후 파일이 정말 바뀌었나?

# 이 레포에서 흔한 중복
- 매 turn 마다 `git status` / `git diff` 재호출
- 인접 파일 편집 후 같은 소스를 또 Read
- 직전 결과 캐싱 없이 `gh pr view` 폴링""",
        "fix_summary": "이미 컨텍스트에 있는 결과 참조. 변경 없는 파일 재Read 금지.",
    },
    "subagent_overuse": {
        "title": "5. Task / 서브에이전트 과다 위임",
        "rule": "Agent 호출 5회 이상 + 평균 결과 ≤ 2k 토큰 (= 각 작업이 ≤3 turn 수준의 사소한 작업).",
        "formula": "낭비 = 호출 수 × 서브에이전트당 약 3k 오버헤드 × write 단가 ($30/M).",
        "fix_code": """# 서브에이전트 사용 기준
- 인라인으로: 단일 파일 조회, 단순 Grep, "package.json 안 보기"
- 서브에이전트로: 다단계 리서치, 병렬 작업, 대용량 컨텍스트 탐색

# 각 서브에이전트는 system prompt 셋업에 약 3k 오버헤드,
# 거기에 작업 프롬프트와 결과 래핑이 더해진다. 3 turn 미만 작업은
# 거의 항상 인라인이 더 저렴하다.""",
        "fix_summary": "사소한 조회는 인라인. 5+ turn 탐색에만 Agent.",
    },
}


def fmt_usd(x):
    return f"${x:,.2f}"


def fmt_int(x):
    return f"{x:,}" if x else "0"


def build_html(data):
    totals = data["totals"]
    sessions = data["sessions"]
    pt = totals["patterns"]

    # KPIs
    kpi_html = f"""
    <div class="grid kpis">
      <div class="kpi"><div class="l">분석된 세션</div><div class="v">{totals['sessions_total']}</div><div class="s">{totals['sessions_with_any_pattern']}개에서 1개 이상 패턴 검출</div></div>
      <div class="kpi"><div class="l">예상 누적 낭비</div><div class="v bad">{fmt_usd(totals['total_waste_usd'])}</div><div class="s">5개 검출기 합산 (Opus 가격 기준)</div></div>
      <div class="kpi"><div class="l">최대 단일 패턴</div><div class="v warn">{fmt_usd(max(p['total_waste_usd'] for p in pt.values()))}</div><div class="s">{PATTERN_KO_NAME[max(pt, key=lambda k: pt[k]['total_waste_usd'])]}</div></div>
      <div class="kpi"><div class="l">활성 패턴 수</div><div class="v">{sum(1 for p in pt.values() if p['affected_sessions']>0)} / 5</div><div class="s">검출된 비효율 종류</div></div>
    </div>
    """

    # Per-pattern bar chart data
    chart_labels = []
    chart_data = []
    chart_sessions = []
    for key, meta in PATTERN_META.items():
        chart_labels.append(PATTERN_KO_NAME[key])
        chart_data.append(round(pt[key]["total_waste_usd"], 2))
        chart_sessions.append(pt[key]["affected_sessions"])

    # Pattern detail cards
    pattern_cards = []
    for key, meta in PATTERN_META.items():
        info = pt[key]
        offenders = info["top_offenders"]
        offender_rows = "\n".join(
            f"""<tr>
                <td class="mono">{o['session_id']}</td>
                <td>{o['evidence']}</td>
                <td class="num bad">{fmt_usd(o['waste_usd'])}</td>
            </tr>"""
            for o in offenders
        ) or '<tr><td colspan="3" class="muted">검출된 세션 없음 ✓</td></tr>'

        status = "good" if info["affected_sessions"] == 0 else "warn"
        status_text = "이상 없음" if info["affected_sessions"] == 0 else f"{info['affected_sessions']}개 세션"

        pattern_cards.append(f"""
        <div class="card pattern">
          <div class="phead">
            <h2 style="margin: 0;">{meta['title']}</h2>
            <div class="pmetrics">
              <span class="badge {status}">{status_text}</span>
              <span class="badge waste">{fmt_usd(info['total_waste_usd'])}</span>
            </div>
          </div>

          <div class="rule"><b>탐지 조건:</b> {meta['rule']}</div>
          <div class="rule"><b>낭비 계산식:</b> <code>{meta['formula']}</code></div>

          <h3>가장 심한 세션</h3>
          <table>
            <thead><tr><th>세션</th><th>근거</th><th class="num">낭비액</th></tr></thead>
            <tbody>{offender_rows}</tbody>
          </table>

          <h3>해결책</h3>
          <pre class="code">{meta['fix_code']}</pre>
          <div class="quick"><b>한 줄 요약:</b> {meta['fix_summary']}</div>
        </div>
        """)

    # Per-session waste table (top 15)
    def waste_of(s):
        return sum(f["waste_usd"] for f in s["findings"].values())

    top_sessions = [s for s in sessions if waste_of(s) > 0][:15]
    session_rows = []
    for s in top_sessions:
        flags = list(s["findings"].keys())
        flag_html = "".join(
            f'<span class="tag t-{k}" title="{PATTERN_KO_NAME[k]}">{PATTERN_KO_NAME[k]}</span>'
            for k in flags
        )
        session_rows.append(f"""<tr>
            <td class="mono">{s['session_id'][:8]}</td>
            <td class="num">{s['n_turns']}</td>
            <td class="num">{s['peak_context']/1000:.0f}k</td>
            <td>{flag_html}</td>
            <td class="num bad">{fmt_usd(waste_of(s))}</td>
        </tr>""")
    session_rows_html = "\n".join(session_rows) or '<tr><td colspan="5" class="muted">검출된 세션이 없습니다</td></tr>'

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>Claude Code — 5대 비효율 패턴 리포트</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0b0f17; --panel:#131924; --panel-2:#1a2230; --border:#232d3d;
    --text:#e6edf3; --muted:#8b98a9; --accent:#7ad1ff;
    --good:#4ade80; --warn:#fbbf24; --bad:#ef4444;
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Inter', 'SF Pro', Segoe UI, sans-serif;
         background: var(--bg); color: var(--text); margin: 0; padding: 32px; line-height: 1.5; }}
  h1 {{ font-size: 28px; margin: 0 0 6px; }}
  h2 {{ font-size: 18px; margin: 0; letter-spacing: -0.01em; }}
  h3 {{ font-size: 13px; margin: 20px 0 8px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }}
  .sub {{ color: var(--muted); font-size: 14px; margin-bottom: 32px; }}
  .grid {{ display: grid; gap: 16px; }}
  .kpis {{ grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-bottom: 24px; }}
  .kpi {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }}
  .kpi .v {{ font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }}
  .kpi .l {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }}
  .kpi .s {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
  .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 22px; margin-bottom: 16px; }}
  .pattern .phead {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; }}
  .pmetrics {{ display: flex; gap: 8px; }}
  .badge {{ padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
  .badge.good {{ background: #14532d; color: #86efac; }}
  .badge.warn {{ background: #633a19; color: #fbbf24; }}
  .badge.waste {{ background: #4b1515; color: #fca5a5; font-variant-numeric: tabular-nums; }}
  .rule {{ font-size: 13px; color: var(--muted); margin: 4px 0; }}
  .rule code {{ color: var(--text); background: var(--panel-2); padding: 1px 5px; border-radius: 3px; }}
  .quick {{ margin-top: 12px; padding: 10px 14px; background: var(--panel-2); border-left: 3px solid var(--good); border-radius: 0 6px 6px 0; font-size: 13px; }}
  pre.code {{ background: #0a0e15; border: 1px solid var(--border); border-radius: 6px;
              padding: 14px; font-family: 'SF Mono', Menlo, monospace; font-size: 12.5px;
              line-height: 1.55; overflow-x: auto; white-space: pre; color: #cbd5e1; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.06em; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.muted {{ color: var(--muted); text-align: center; padding: 18px 0; }}
  .mono {{ font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: var(--muted); }}
  .bad {{ color: var(--bad); font-weight: 600; }}
  .warn {{ color: var(--warn); }}
  .good {{ color: var(--good); }}
  .tag {{ display: inline-block; padding: 2px 8px; margin: 1px 3px 1px 0; border-radius: 4px;
          font-size: 11px; font-weight: 600; letter-spacing: 0; white-space: nowrap; }}
  .tag.t-context_bloat {{ background: #4b1515; color: #fca5a5; }}
  .tag.t-giant_tool_outputs {{ background: #633a19; color: #fbbf24; }}
  .tag.t-poor_cache_util {{ background: #1e3a5f; color: #93c5fd; }}
  .tag.t-duplicate_tools {{ background: #14532d; color: #86efac; }}
  .tag.t-subagent_overuse {{ background: #4c1d95; color: #c4b5fd; }}
  canvas {{ max-height: 260px; }}
  .footer {{ margin-top: 48px; color: var(--muted); font-size: 12px; text-align: center; }}
</style>
</head>
<body>
  <h1>Claude Code — 5대 비효율 패턴 리포트</h1>
  <div class="sub">{totals['sessions_dir']}</div>

  {kpi_html}

  <div class="card">
    <h3>패턴별 누적 낭비 ($)</h3>
    <canvas id="patternBar"></canvas>
  </div>

  {''.join(pattern_cards)}

  <div class="card">
    <h2 style="margin: 0 0 14px;">개별 세션 — 패턴 검출 결과 (top 15)</h2>
    <table>
      <thead><tr>
        <th>세션</th><th class="num">Turn 수</th><th class="num">최대 컨텍스트</th>
        <th>검출 패턴</th><th class="num">총 낭비액</th>
      </tr></thead>
      <tbody>{session_rows_html}</tbody>
    </table>
  </div>

  <div class="card">
    <h2 style="margin: 0 0 12px;">즉시 적용할 단일 변경</h2>
    <ol style="font-size: 14px; line-height: 1.8; margin: 0; padding-left: 20px;">
      <li><b>CLAUDE.md 에 컨텍스트 룰 추가</b> — "200k 토큰 초과 시 /compact, 50k 글자 초과 도구 출력 시 /compact" 명시. (패턴 1 + 2)</li>
      <li><b>긴 세션 시작 전 prompt prefix 동결</b> — CLAUDE.md, system reminder, 모델 선택을 미리 확정. (패턴 3)</li>
      <li><b>Bash 출력 캐핑 습관화</b> — <code>| head -50</code>, <code>| wc -l</code> 같은 제한부터 붙이기. (패턴 2)</li>
      <li><b>Read 직전 자기 확인</b> — "이 파일 이미 읽지 않았나?" → 컨텍스트 위쪽 확인 후 호출. (패턴 4)</li>
      <li><b>Agent 호출 임계 룰</b> — 단일 grep · 단일 파일 조회는 인라인, 다중 검색 · 병렬 조사만 Agent. (패턴 5)</li>
    </ol>
  </div>

  <div class="footer">
    위 탐지 규칙과 계산식은 결정론적입니다 — 같은 입력에 대해 항상 같은 낭비액이 산출됩니다.<br>
    가격 기준: Opus 4.x (1M 토큰당 read $1.50 / write 1h $30 / output $75).
  </div>

<script>
Chart.defaults.color = '#e6edf3';
Chart.defaults.borderColor = '#232d3d';
new Chart(document.getElementById('patternBar'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(chart_labels)},
    datasets: [{{
      label: '낭비액 (USD)',
      data: {json.dumps(chart_data)},
      backgroundColor: ['#ef4444','#fbbf24','#60a5fa','#4ade80','#a78bfa'],
      borderWidth: 0,
    }}]
  }},
  options: {{
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{
        afterLabel: (c) => '검출된 세션: ' + ({json.dumps(chart_sessions)})[c.dataIndex] + '개'
      }} }}
    }},
    scales: {{
      y: {{ beginAtZero: true, title: {{ display: true, text: '낭비액 (USD)' }} }}
    }}
  }}
}});
</script>
</body>
</html>
"""
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/tmp/pattern_analysis.json")
    ap.add_argument("--out", default="/tmp/patterns_report.html")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[error] missing {args.input}. Run detect_patterns.py first.", file=sys.stderr)
        sys.exit(2)

    with open(args.input) as f:
        data = json.load(f)

    html = build_html(data)
    with open(args.out, "w") as f:
        f.write(html)
    print(f"[ok] wrote {args.out}")
    print(f"     open: open {args.out}")


if __name__ == "__main__":
    main()
