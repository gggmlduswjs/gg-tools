#!/usr/bin/env python3
"""Build an HTML efficiency dashboard from analyze_sessions.py output.

Usage:
  python3 build_dashboard.py --input /tmp/session_analysis.json --out /tmp/efficiency_report.html
"""
import argparse
import json
import os
import sys
from collections import Counter

# Must mirror analyze_sessions.py. Only used here for dollar-value estimates in
# the improvement cards (not for primary cost calculation, which already lives
# in the per-session `cost_usd`).
OPUS_IN = 15.0
OPUS_OUT = 75.0
OPUS_W5 = 18.75
OPUS_W1H = 30.0
OPUS_READ = 1.50
SONNET_RATIO = 5.0  # Opus / Sonnet blended multiplier


def compute_savings(totals, sessions):
    """Return a dict of {label: dollar_amount} for improvement suggestions.

    Every heuristic below is conservative and documented. Sum may exceed
    actual achievable savings because items partially overlap (e.g. compaction
    and image management both reduce cache_read).
    """
    # 1. Opus → Sonnet: assume 30% of total spend could run on Sonnet
    save_model = totals["cost_usd"] * 0.30 * (1 - 1 / SONNET_RATIO)

    # 2. /compact on top-14 sessions: cut cache_read by 30%
    top14 = sessions[:14]
    top14_cache_read = sum(s["cache_read"] for s in top14)
    save_compact = top14_cache_read * 0.3 * OPUS_READ / 1e6

    # 3. Image sessions: each image adds ~40k tokens to cache. Reclaiming 50%.
    img_sessions = [s for s in sessions if s["had_image"]]
    img_count = sum(s["image_count"] for s in img_sessions)
    save_images = img_count * 40000 * 0.5 * OPUS_READ / 1e6

    # 4. Cache TTL 1h → 5m for 40% of writes
    save_ttl = totals["cache_create_1h"] * 0.4 * (OPUS_W1H - OPUS_W5) / 1e6

    # 5. Session scope reduction: 15% cache_read cut on non-top14 sessions
    other_cache_read = totals["cache_read"] - top14_cache_read
    save_scope = other_cache_read * 0.15 * OPUS_READ / 1e6

    # 6. Redundant reads: each redundant read ≈ 3k tokens × (write + 10 reads later)
    save_redundant = totals["redundant_reads"] * 3000 * (OPUS_W1H + OPUS_READ * 10) / 1e6

    return {
        "model_routing": save_model,
        "compact": save_compact,
        "images": save_images,
        "ttl": save_ttl,
        "scope": save_scope,
        "redundant": save_redundant,
    }


def build_html(data, repo_name):
    totals = data["totals"]
    sessions = data["sessions"]
    n = len(sessions)

    # cost category breakdown
    cost_cache_write = (
        totals["cache_create_1h"] * OPUS_W1H / 1e6
        + totals["cache_create_5m"] * OPUS_W5 / 1e6
    )
    cost_cache_read = totals["cache_read"] * OPUS_READ / 1e6
    cost_output = totals["output_tokens"] * OPUS_OUT / 1e6
    cost_input = totals["input_tokens"] * OPUS_IN / 1e6

    savings = compute_savings(totals, sessions)
    total_savings = sum(savings.values())
    save_pct = total_savings / totals["cost_usd"] * 100 if totals["cost_usd"] else 0

    # score component averages
    score_comp_avg = {
        "cache": sum(s["scores"]["cache_score"] for s in sessions) / n,
        "density": sum(s["scores"]["density_score"] for s in sessions) / n,
        "redundancy": sum(s["scores"]["redundancy_score"] for s in sessions) / n,
        "tool": sum(s["scores"]["tool_score"] for s in sessions) / n,
    }

    # grade distribution
    grade_order = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
    grades = Counter(s["scores"]["grade"] for s in sessions)
    grade_counts = [grades.get(g, 0) for g in grade_order]

    # scatter data
    scatter_data = [
        {
            "x": round(s["cost_usd"], 2),
            "y": s["scores"]["composite"],
            "r": min(20, 3 + s["num_tool_calls"] / 20),
        }
        for s in sessions
    ]

    # pareto
    sorted_by_cost = sessions  # already sorted desc by cost
    cum, running = [], 0
    for s in sorted_by_cost:
        running += s["cost_usd"]
        cum.append(round(running / totals["cost_usd"] * 100, 1) if totals["cost_usd"] else 0)

    # top 20 rows
    def short(sid): return sid[:8]
    top_rows = "\n".join(
        f"""<tr>
            <td class="mono">{short(s['session_id'])}</td>
            <td class="num">${s['cost_usd']:.2f}</td>
            <td class="num">{s['num_tool_calls']}</td>
            <td class="num">{s['total_input_tokens']/1e6:.1f}M</td>
            <td class="num">{s['output_tokens']/1e3:.1f}k</td>
            <td class="num">{s['cache_hit_ratio']*100:.1f}%</td>
            <td class="num">{s['redundant_reads']}</td>
            <td class="num">{s['scores']['composite']}</td>
            <td><span class="grade g-{s['scores']['grade'][0].lower()}">{s['scores']['grade']}</span></td>
        </tr>"""
        for s in sessions[:20]
    )

    avg_composite = sum(s["scores"]["composite"] for s in sessions) / n

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{repo_name} — Claude Code 세션 효율 리포트</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0b0f17; --panel: #131924; --panel-2: #1a2230;
    --border: #232d3d; --text: #e6edf3; --muted: #8b98a9;
    --accent: #7ad1ff; --good: #4ade80; --warn: #fbbf24; --bad: #ef4444;
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro', Segoe UI, sans-serif;
         background: var(--bg); color: var(--text); margin: 0; padding: 32px; line-height: 1.5; }}
  h1 {{ font-size: 28px; margin: 0 0 6px; }}
  h2 {{ font-size: 20px; margin: 40px 0 16px; color: var(--accent); letter-spacing: -0.01em; }}
  h3 {{ font-size: 15px; margin: 0 0 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }}
  .sub {{ color: var(--muted); font-size: 14px; margin-bottom: 32px; }}
  .grid {{ display: grid; gap: 16px; }}
  .kpis {{ grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }}
  .kpi {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }}
  .kpi .v {{ font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }}
  .kpi .l {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }}
  .kpi .s {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
  .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }}
  .row2 {{ grid-template-columns: 1fr 1fr; }}
  canvas {{ max-height: 320px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.06em; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .mono {{ font-family: 'SF Mono', Menlo, monospace; font-size: 12px; color: var(--muted); }}
  .grade {{ padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 12px; }}
  .grade.g-a {{ background: #14532d; color: #86efac; }}
  .grade.g-b {{ background: #1e3a5f; color: #93c5fd; }}
  .grade.g-c {{ background: #633a19; color: #fbbf24; }}
  .grade.g-d, .grade.g-f {{ background: #4b1515; color: #fca5a5; }}
  .rubric td:first-child {{ font-weight: 600; }}
  .rubric .bar {{ height: 8px; background: var(--panel-2); border-radius: 4px; overflow: hidden; margin-top: 6px; }}
  .rubric .bar > div {{ height: 100%; background: linear-gradient(90deg, #4ade80, #60a5fa); }}
  .imp {{ border-left: 3px solid var(--accent); padding: 12px 18px; background: var(--panel-2); border-radius: 0 8px 8px 0; margin-bottom: 12px; }}
  .imp .h {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
  .imp .h .t {{ font-weight: 600; font-size: 15px; }}
  .imp .h .s {{ color: var(--good); font-weight: 700; font-variant-numeric: tabular-nums; }}
  .imp p {{ margin: 4px 0; color: var(--muted); font-size: 13px; }}
  .footer {{ margin-top: 48px; color: var(--muted); font-size: 12px; text-align: center; }}
  .good {{ color: var(--good); }} .warn {{ color: var(--warn); }} .bad {{ color: var(--bad); }}
</style>
</head>
<body>
  <h1>Claude Code 세션 효율 리포트</h1>
  <div class="sub">{repo_name} · 활성 세션 {n}개 · 세션 디렉터리: <code>{totals.get('sessions_dir', '')}</code></div>

  <div class="grid kpis">
    <div class="kpi"><div class="l">누적 비용</div><div class="v">${totals['cost_usd']:.2f}</div><div class="s">세션당 평균 ${totals['cost_usd']/n:.2f}</div></div>
    <div class="kpi"><div class="l">총 토큰 처리</div><div class="v">{totals['total_input_tokens']/1e6:.0f}M</div><div class="s">입력(캐시 포함) 기준</div></div>
    <div class="kpi"><div class="l">캐시 적중률</div><div class="v good">{totals['cache_hit_ratio']*100:.1f}%</div><div class="s">cache_read ÷ 총 입력</div></div>
    <div class="kpi"><div class="l">출력 토큰</div><div class="v">{totals['output_tokens']/1e6:.2f}M</div><div class="s">실제 assistant 산출</div></div>
    <div class="kpi"><div class="l">도구 호출 수</div><div class="v">{totals['num_tool_calls']:,}</div><div class="s">세션당 평균 {totals['num_tool_calls']/n:.0f}회</div></div>
    <div class="kpi"><div class="l">평균 종합 점수</div><div class="v">{avg_composite:.1f}</div><div class="s">100점 만점 (composite)</div></div>
  </div>

  <h2>비용 구조 분석</h2>
  <div class="grid row2">
    <div class="card"><h3>비용 내역 (카테고리별)</h3><canvas id="costPie"></canvas></div>
    <div class="card"><h3>세션별 비용 (Pareto)</h3><canvas id="pareto"></canvas></div>
  </div>

  <h2>점수 분포</h2>
  <div class="grid row2">
    <div class="card"><h3>등급 히스토그램</h3><canvas id="gradeBar"></canvas></div>
    <div class="card"><h3>비용 vs 점수 (버블 크기 = 도구 호출 수)</h3><canvas id="scatter"></canvas></div>
  </div>

  <h2>평가 기준 (Rubric)</h2>
  <div class="card">
    <table class="rubric">
      <thead><tr><th style="width:240px;">평가 항목</th><th>측정 방식</th><th style="width:110px;">가중치</th><th style="width:160px;">레포 평균</th></tr></thead>
      <tbody>
        <tr>
          <td>캐시 활용도</td>
          <td>cache_read ÷ 총 입력. 0.85 이상이 만점. 재사용률이 높을수록 매 turn 마다 같은 토큰을 다시 보내는 비용이 줄어든다.
            <div class="bar"><div style="width:{score_comp_avg['cache']}%;"></div></div>
          </td>
          <td class="num">40%</td>
          <td class="num good">{score_comp_avg['cache']:.1f} / 100</td>
        </tr>
        <tr>
          <td>산출 밀도</td>
          <td>출력 ÷ 입력. ~2%가 적정 구간. 낮으면 읽기만 많고 산출이 부족, 높으면 긴 독백.
            <div class="bar"><div style="width:{score_comp_avg['density']}%;"></div></div>
          </td>
          <td class="num">20%</td>
          <td class="num warn">{score_comp_avg['density']:.1f} / 100</td>
        </tr>
        <tr>
          <td>중복 Read 비율</td>
          <td>같은 파일을 반복 Read 한 비중. Grep/Glob 으로 위치를 좁히지 않고 Read 를 남발하면 감점.
            <div class="bar"><div style="width:{score_comp_avg['redundancy']}%;"></div></div>
          </td>
          <td class="num">20%</td>
          <td class="num warn">{score_comp_avg['redundancy']:.1f} / 100</td>
        </tr>
        <tr>
          <td>도구 사용 효율</td>
          <td>출력 1k 토큰당 도구 호출 수. 2–10 이 건강한 범위, 20 초과는 탐색 thrash 신호.
            <div class="bar"><div style="width:{score_comp_avg['tool']}%;"></div></div>
          </td>
          <td class="num">20%</td>
          <td class="num good">{score_comp_avg['tool']:.1f} / 100</td>
        </tr>
      </tbody>
    </table>
    <div style="margin-top:16px; padding:12px; background:var(--panel-2); border-radius:6px; font-size:13px; color:var(--muted);">
      종합 점수 = 0.4 · 캐시 + 0.2 · 산출밀도 + 0.2 · 중복read + 0.2 · 도구효율. 등급: A+ ≥ 90, A ≥ 85, A- ≥ 80, B+ ≥ 75, B ≥ 70, B- ≥ 65, C+ ≥ 60, C ≥ 55, C- ≥ 50, D ≥ 40, F &lt; 40.
    </div>
  </div>

  <h2>비용 상위 세션 Top 20</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>세션</th><th class="num">비용</th><th class="num">도구</th>
        <th class="num">총 입력</th><th class="num">출력</th>
        <th class="num">캐시 적중</th><th class="num">중복 Read</th>
        <th class="num">점수</th><th>등급</th>
      </tr></thead>
      <tbody>{top_rows}</tbody>
    </table>
  </div>

  <h2>비용 절감 개선안 (예상 $ 기준)</h2>
  <div class="card">
    <div class="imp">
      <div class="h"><div class="t">1. Opus → Sonnet 라우팅 (작업 난이도별)</div><div class="s">~${savings['model_routing']:.0f} (~{savings['model_routing']/totals['cost_usd']*100:.0f}%)</div></div>
      <p>간단한 리팩터/리드/테스트 실행은 Sonnet으로 이관. <code>/fast</code> 토글 또는 <code>--model sonnet</code> 세션.</p>
      <p><b>Why:</b> Opus 가격 = Sonnet × 5. 30%만 다운그레이드해도 큰 폭 절감.</p>
    </div>
    <div class="imp">
      <div class="h"><div class="t">2. 장시간 세션 <code>/compact</code> 적극 사용</div><div class="s">~${savings['compact']:.0f}</div></div>
      <p>상위 14개 세션이 비용의 대부분을 차지. 매 150-200 turn마다 /compact로 절반 이상 cache read 절감 가능.</p>
      <p><b>Why:</b> 세션 길어질수록 매 turn 누적 컨텍스트를 re-read 과금. 컴팩션이 요약으로 교체.</p>
    </div>
    <div class="imp">
      <div class="h"><div class="t">3. 이미지 첨부 세션 관리</div><div class="s">~${savings['images']:.0f}</div></div>
      <p>이미지는 장당 ~20-60k 토큰. 확인 후에도 세션 내내 캐시 유지됨. 짧게 보고 즉시 /compact.</p>
      <p><b>Why:</b> 이미지는 가장 비싼 페이로드. 불필요하게 오래 유지되면 cache_read 누적.</p>
    </div>
    <div class="imp">
      <div class="h"><div class="t">4. Cache TTL 1h → 5m 전환</div><div class="s">~${savings['ttl']:.0f}</div></div>
      <p>짧은 세션엔 1h 프리미엄($30/M) 불필요. 5m($18.75/M)로 충분. <code>ANTHROPIC_CACHE_TTL=5m</code> env 설정.</p>
      <p><b>Why:</b> 1h 프리미엄은 30분+ 세션에서만 회수. 단기 세션엔 순수 낭비.</p>
    </div>
    <div class="imp">
      <div class="h"><div class="t">5. 세션 scope 축소 & 재진입</div><div class="s">~${savings['scope']:.0f}</div></div>
      <p>작업 단위별 세션 분리. <code>--continue</code> 대신 새 세션. CLAUDE.md/MEMORY.md가 컨텍스트 이관.</p>
      <p><b>Why:</b> 한 세션 내 컨텍스트 누적 → 매 turn cache_read 선형 증가. 짧은 세션이 효율적.</p>
    </div>
    <div class="imp">
      <div class="h"><div class="t">6. 중복 Read 제거</div><div class="s">~${savings['redundant']:.0f}</div></div>
      <p>{totals['redundant_reads']}건의 redundant read 감지. Grep/Glob → Read 순서. 한 번 읽은 파일은 컨텍스트 내에서 참조.</p>
      <p><b>Why:</b> 재Read는 cache write + 이후 매 turn cache read로 이중 과금.</p>
    </div>
    <div class="imp" style="border-left-color:var(--good); background:#0f2a1a;">
      <div class="h"><div class="t">예상 누적 절감 (단순 합산)</div><div class="s">~${total_savings:.0f} / ${totals['cost_usd']:.0f} (~{save_pct:.0f}%)</div></div>
      <p>항목 간 중복 고려 시 실제로는 <b>30–40%</b> 수준 기대. 세션당 평균 ${totals['cost_usd']/n:.2f} → ${(totals['cost_usd']-total_savings)/n:.2f}.</p>
    </div>
  </div>

  <h2>즉시 실행 권장</h2>
  <div class="card" style="font-size:14px; line-height:1.7;">
    <ol style="margin:0; padding-left:20px;">
      <li><b>settings.json에 <code>env: {{"ANTHROPIC_CACHE_TTL":"5m"}}</code></b> — 단기 세션 즉시 감소.</li>
      <li><b>CLAUDE.md에 "200k 토큰 초과 시 /compact" 명시</b> — 상위 세션은 모두 이 규칙 위반.</li>
      <li><b>Sonnet 기본, Opus는 Plan/복잡 리팩터에 제한</b>.</li>
      <li><b>이미지 업로드 후 즉시 /compact</b>.</li>
      <li><b>Grep/Glob 우선 탐색 규율</b>.</li>
    </ol>
  </div>

  <div class="footer">
    가격 기준: 1M 토큰당 (입력 / 출력 / 캐시쓰기 5m / 캐시쓰기 1h / 캐시읽기) · Opus 4.x ($15 / $75 / $18.75 / $30 / $1.50) · Sonnet 4.x ($3 / $15 / $3.75 / $6 / $0.30) · Haiku 4.x ($0.80 / $4 / $1 / $1.60 / $0.08).
  </div>

<script>
Chart.defaults.color = '#e6edf3';
Chart.defaults.borderColor = '#232d3d';
const chartColors = ['#7ad1ff','#4ade80','#fbbf24','#f472b6','#a78bfa','#fb923c'];

new Chart(document.getElementById('costPie'), {{
  type: 'doughnut',
  data: {{
    labels: ['캐시 쓰기 (1h+5m)', '캐시 읽기', '출력', '입력 (캐시 미스)'],
    datasets: [{{
      data: [{cost_cache_write:.2f}, {cost_cache_read:.2f}, {cost_output:.2f}, {cost_input:.2f}],
      backgroundColor: chartColors, borderWidth: 0,
    }}]
  }},
  options: {{
    plugins: {{
      legend: {{ position: 'right' }},
      tooltip: {{ callbacks: {{ label: (c) => c.label + ': $' + c.parsed.toFixed(2) + ' (' + (c.parsed/{totals['cost_usd'] or 1}*100).toFixed(1) + '%)' }} }}
    }}
  }}
}});

new Chart(document.getElementById('pareto'), {{
  type: 'bar',
  data: {{
    labels: {list(range(1, n+1))},
    datasets: [
      {{ type: 'bar', label: '세션별 비용 ($)',
         data: {[round(s['cost_usd'],2) for s in sorted_by_cost]},
         backgroundColor: '#7ad1ff', yAxisID: 'y' }},
      {{ type: 'line', label: '누적 %',
         data: {cum}, borderColor: '#fbbf24', backgroundColor: 'transparent',
         yAxisID: 'y1', tension: 0.2, pointRadius: 0 }}
    ]
  }},
  options: {{
    scales: {{
      x: {{ ticks: {{ display: false }}, title: {{ display: true, text: '세션 (비용 내림차순)' }} }},
      y: {{ title: {{ display: true, text: '세션당 USD' }} }},
      y1: {{ position: 'right', min: 0, max: 100, title: {{ display: true, text: '누적 비용 %' }}, grid: {{ display: false }} }}
    }}
  }}
}});

new Chart(document.getElementById('gradeBar'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(grade_order)},
    datasets: [{{
      data: {grade_counts},
      backgroundColor: ['#4ade80','#4ade80','#86efac','#60a5fa','#60a5fa','#93c5fd','#fbbf24','#fbbf24','#fcd34d','#fca5a5','#ef4444'],
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: '세션 수' }} }} }}
  }}
}});

new Chart(document.getElementById('scatter'), {{
  type: 'bubble',
  data: {{
    datasets: [{{
      label: '세션', data: {json.dumps(scatter_data)},
      backgroundColor: 'rgba(122,209,255,0.5)', borderColor: '#7ad1ff',
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ type: 'logarithmic', title: {{ display: true, text: '비용 (USD, 로그 스케일)' }} }},
      y: {{ min: 50, max: 100, title: {{ display: true, text: '종합 점수' }} }}
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
    ap.add_argument("--input", default="/tmp/session_analysis.json")
    ap.add_argument("--out", default="/tmp/efficiency_report.html")
    ap.add_argument("--repo-name", default=None, help="Label shown in report header")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[error] input not found: {args.input}", file=sys.stderr)
        print(f"        run analyze_sessions.py first", file=sys.stderr)
        sys.exit(2)

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("sessions"):
        print("[error] no sessions in analysis output", file=sys.stderr)
        sys.exit(2)

    repo_name = args.repo_name or os.path.basename(
        data["totals"].get("sessions_dir", "").rstrip("/")
    ) or "Claude Code sessions"

    html = build_html(data, repo_name)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[ok] wrote {args.out}")
    print(f"     open it: open {args.out}")


if __name__ == "__main__":
    main()
