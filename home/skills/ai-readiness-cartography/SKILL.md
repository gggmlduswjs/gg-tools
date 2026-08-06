---
name: ai-readiness-cartography
description: Audits any repository against the v2 AI-Ready rubric (100 pts · 7 categories — Navigation, Context Quality, Tribal Knowledge, Dependency Mapping, Verification Gates, Freshness, Agent Outcomes) and produces a professional single-file HTML dashboard plus an ROI-ranked action list. The skill bundles a Python scorer (`scripts/score.py`) that auto-detects coverage, hallucinated paths, drift, and god files. Trigger whenever the user asks for an "AI-readiness 지도", "AI-ready 시각화", "repo cartography", "codebase audit 시각화", "ai-readiness-cartography", or anything that sounds like "score how agent-friendly this codebase is and visualize it", "check how AI-ready our repo is", "map the repo against the rubric", or "audit our codebase for agent readiness". Also trigger when the user points at a repo and asks whether it is ready for coding agents / LLM workflows — even without the exact keyword. The output is always a clean technical-dashboard HTML (Inter + JetBrains Mono, light surface, blue/green/amber/red accents), never a fantasy map.
---

# AI-Readiness Cartography

이 스킬은 임의 레포지토리를 **AI-Ready 코드베이스 v2 루브릭** (100점 · 7 카테고리 A-G) 으로 감사합니다. 산출물은 한 장의 전문 기술 대시보드 HTML + 자동 채점 JSON + ROI 순으로 정렬된 actionable 액션 리스트입니다. 이름은 "cartography" 지만 톤은 의사결정용 계기판 — 판타지 양피지 / 컴퍼스 로즈 같은 장식은 절대 쓰지 않습니다.

## When to use

- "AI-readiness 지도 / 시각화 / 점수 매겨줘"
- "이 레포가 얼마나 agent-friendly 한지 보여줘"
- "codebase audit", "repo cartography"
- "Claude Code 가 이 레포를 잘 다룰 수 있을까" 같은 우회 표현
- 트리거 키워드 없이도 LLM workflow 적합도 평가를 원하면 트리거

## What to produce

**3가지 결과물을 한 번에 만듭니다.**

1. **JSON 점수표** (raw 데이터, 다른 도구가 소비할 수 있음)
2. **단일 HTML 대시보드** (사람이 보고 의사결정)
3. **ROI 순 액션 리스트** (우선순위가 매겨진 다음 단계)

기본 저장 위치 우선순위:
- 레포에 `docs/` 가 있으면 → `docs/ai-readiness-map.html`, `docs/ai-readiness-score.json`
- `.claude/` 가 있으면 → `.claude/ai-readiness-{map.html,score.json}`
- 없으면 레포 루트
- 사용자가 명시적 경로를 지정하면 그 경로 우선

## Workflow

### 1. Python 스크립트로 자동 채점

```bash
python3 ~/.claude/skills/ai-readiness-cartography/scripts/score.py <repo-path> \
  --json <output-path>/ai-readiness-score.json
```

스크립트는 stdlib only (deps 없음, Python 3.10+). 출력:
- `--json` 으로 지정한 경로에 구조화된 점수표 (categories A-G, evidence, sub_scores, findings, ROI actions, large files)
- stdout 에 사람이 읽기 좋은 markdown 요약

채점이 자동으로 잡는 것:
- **A** 핵심 module navigation coverage (CLAUDE.md / AGENTS.md 보유 비율)
- **B1, B5** conciseness · cross-references
- **C Q1-Q4** Five-Question framework heuristic + Q5 MEMORY/ADR 존재
- **D** ARCHITECTURE.md / mermaid / workspace 파일 검출
- **E1** **hallucinated path 검증** (context의 모든 path 후보를 실제 존재 검증) — 이 항목이 가장 중요
- **E3** build/test infra 존재
- **F** context drift (mtime 비교) + CI / hook validation
- **G** evals/ benchmarks/ 디렉터리 + telemetry 단서

자동이 잡지 못하는 것 (Manual):
- B2-B4 quick commands / key files / non-obvious 의 깊이
- C 의 tribal knowledge depth
- E2 critic review 품질
- E4 prompt test 품질

LLM 이 JSON 을 받은 뒤 manual 항목을 보강하거나 그대로 차트에 반영합니다.

### 2. JSON 으로 HTML 대시보드 채우기

`assets/template.html` 을 복사 후 JSON 의 값을 끼워 넣습니다. **절대 처음부터 쓰지 말 것** — 디자인이 매번 바뀝니다.

바꿔야 할 블록:

**(a) 헤더**
- `<title>` · h1 의 `{{REPO_NAME}}`
- `header-meta` 의 날짜 (오늘) · git branch · `meta.modules_total` · `meta.context_files_total`

**(b) Score hero**
- `score-hero .num` ← `total`
- `grade-badge` 텍스트 ← grade (`AI-Native` / `AI-Ready` / `AI-Assisted` / `AI-Fragile` / `AI-Hostile`)
- `grade-badge` 배경/색 ← `grade_color` (green / amber / red)
- 등급 임계값:
  - 90-100 AI-Native (green)
  - 75-89  AI-Ready (green)
  - 60-74  AI-Assisted (amber)
  - 40-59  AI-Fragile (amber)
  - < 40   AI-Hostile (red)
- `.desc` 한 줄로 가장 약한 카테고리 2개 언급
- Mini stats 3개: modules · context_files · large_files_300plus (또는 ref_broken 강조)

**(c) 7 카테고리 막대차트**
10 rule 차트를 7 카테고리로 교체. 각 행:
- A 15 / B 20 / C 20 / D 15 / E 15 / F 10 / G 5
- 막대 width = `score / max * 100%`
- 색: score/max ≥ 0.75 → bar-good (green) · 0.5-0.74 → bar-warn (amber) · < 0.5 → bar-bad (red)
- `.sub` 에 evidence 1-2개를 짧게 (예: "coverage 75% · 1 module 누락")
- B 와 E 는 sub_scores 가 있으니 행 아래 작게 펼쳐서 5/4개 sub-item 의 점수도 보이게

**(d) Structural Map (SVG)**
대상 레포 구조에 맞게 컬럼 재설정. 카드 안에 `large_files` 의 상위 항목을 hot/warm 바로 표시. CLAUDE.md / AGENTS.md 보유 module 은 accent border + 점등. `ref_broken` 이 있는 module 은 빨간 점 표시.

**(e) Wins / Top ROI Actions 패널**
- 왼쪽 "Wins": evidence 에서 점수 높은 카테고리 위주, 핵심 강점 5개
- 오른쪽 "Top ROI Actions": JSON 의 `actions` 상위 5-7개. 각 행에:
  - Category 태그 (A-G)
  - Effort (S / M / L · 시간)
  - Impact (1줄)
  - Priority score (선택)

**(f) 푸터**
`{{REPO_NAME}} · AI-Readiness v2 · scored {{YYYY-MM-DD}}`

### 3. 브라우저에서 열기

```bash
open <output-path>/ai-readiness-map.html   # macOS
xdg-open <path>                            # Linux
```

사용자가 "열지 마라" 하면 경로만 알림.

### 4. 요약 보고

마지막으로 다음 4가지를 한 문단으로:
1. **총점 / 등급** (`32/100 · AI-Hostile`)
2. **최약점 카테고리 1-2개** + 한 줄 진단
3. **Top 3 ROI 액션** (Effort + Impact 짧게)
4. 생성된 **파일 경로**

## Style rules (non-negotiable)

이 스킬의 정체성. 어긋나면 스킬이 아닙니다.

- **폰트**: Inter (본문), JetBrains Mono (숫자/코드). 다른 폰트 금지.
- **색**: 템플릿의 CSS 변수 팔레트 고정.
- **배경**: `#fafafa` light. 다크 모드 만들지 않음.
- **장식 금지**: 컴퍼스 로즈, 양피지, 필기체, 이모지, 스탬프 — 전부 없이.
- **차트 라이브러리 금지**: 모든 시각화는 인라인 SVG + CSS.

## Common pitfalls

- **루브릭이 v2 임을 잊고 10-rule 로 채점** — 이전 버전 잔재. 현재는 **A-G 7 카테고리 / 100점**.
- **스크립트 출력을 무시하고 직접 점수 매기기** — 자동이 잡는 것은 자동이 더 정확. 스크립트 실행 후 그 위에 보강.
- **E1 hallucinated path 를 가볍게 다룸** — Meta 표준 "0 hallucinated paths". 1건이라도 있으면 즉시 fix 액션.
- **template 무시하고 처음부터 쓰기** — 매번 디자인 달라짐. 복사 → 수정.
- **판타지 회귀** — 이름이 cartography라고 지도 은유 강하게 쓰지 말 것.
- **ROI 정성적 형용사만** — "효율 ↑" 같은 모호한 임팩트 금지. "task당 ~3 min × ~5/일" 처럼 구체적 단위.

## ROI framing

각 액션의 effort/impact 표현 규약:

- **Effort**: S (<1h) / M (1-4h) / L (4h+)
- **Impact**: 정량 단위 우선 — "task당 N min × M task/주", "토큰 X% 절감", "회귀 Y건 catch"
- **Priority**: `impact_score / effort_hours` 로 자동 정렬됨

대표 액션 ROI 표는 `references/scoring-rubric.md` 끝 참조.

## Files

- `assets/template.html` — 복사 후 채울 원본 대시보드
- `references/scoring-rubric.md` — 7 카테고리 채점 기준 v2
- `scripts/score.py` — 자동 채점 + ROI 액션 생성 (Python 3.10+, stdlib only)
