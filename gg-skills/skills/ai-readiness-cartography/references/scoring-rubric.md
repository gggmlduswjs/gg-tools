# AI-Ready Codebase Rubric · v2 (100 pt · 7 categories)

이 문서는 자동/수동 채점 모두에 쓰는 단일 진실 기준입니다. `scripts/score.py` 가 자동으로 잡지 못하는 항목은 사람이 보강합니다 — 각 항목 끝의 **Auto / Heuristic / Manual** 태그가 신뢰도를 알려줍니다.

| Cat | Name | Points |
|-----|------|--------|
| A | AI Navigation & Coverage | 15 |
| B | Context Document Quality | 20 |
| C | Tribal Knowledge Externalization | 20 |
| D | Cross-Module Dependency & Data Flow Mapping | 15 |
| E | Verification & Quality Gates | 15 |
| F | Freshness & Self-Maintenance | 10 |
| G | Agent Performance Outcomes | 5 |

**Total = 100**

---

## A. AI Navigation & Coverage · /15

> AI가 전체 codebase / module / workflow를 빠르게 찾을 수 있는가.

| Score | Criteria |
|-------|----------|
| 0     | repo를 grep / search로 추측해야 함 |
| 5     | 일부 module에 README / context 존재 |
| 10    | 대부분 핵심 module에 역할·entry point·related files 정리 |
| 15    | 모든 핵심 module / workflow에 navigation guide 존재. "어디를 봐야 하는가"를 1-2 hops 안에 도달 |

**Measurement** *(Auto)*

```
Navigation Coverage = (AI-context로 안내 가능한 핵심 module 수) / (전체 핵심 module 수)
```

- "핵심 module" = repo 루트의 코드 디렉터리 + `apps/*` / `packages/*` / `services/*` 의 각 자식
- 점수 = `round(coverage × 15)` 후 cap
- 파일 개수가 아니라 module / workflow coverage로 평가

---

## B. Context Document Quality · /20

> Context files가 "compass, not encyclopedia" 원칙을 따르는가.

| Sub | Item | Points | Full-Score Criteria |
|-----|------|--------|---------------------|
| B1 | Conciseness *(Auto)*       | 4 | 모든 CLAUDE.md가 25-35 lines 또는 ~1,000 tokens 이하 |
| B2 | Quick Commands *(Heuristic)* | 4 | copy-paste 가능한 명령어 + 사용 시점 명시 (`~~~bash` 블록 + 주변 설명) |
| B3 | Key Files *(Heuristic)*    | 4 | 실제 수정에 필요한 3-5개 핵심 파일 경로 제시 |
| B4 | Non-Obvious Patterns *(Heuristic)* | 4 | 실패 유발 hidden rule + 예외가 명시 (`Why:`, `Note:`, `Gotcha`, `Warning`) |
| B5 | See Also / Cross References *(Auto)* | 4 | 관련 module / context file / dependency map 연결 (relative links) |

각 sub-item 은 module 평균 또는 최댓값을 4점 만점으로 환산. **문서가 많은 게 아니라 task-relevant context만 담는 것이 핵심.**

---

## C. Tribal Knowledge Externalization · /20

> 숨은 규칙, 실패 패턴, human-only knowledge가 구조화되었는가.

### Five-Question Framework *(Heuristic + Manual)*

각 핵심 module에 대해 다음 5개 질문에 답할 수 있으면 4점씩, 총 20점:

1. **What does this module configure / own?** — `## Purpose`, "configures", "owns" 표현
2. **What are common modification patterns?** — `## Patterns`, "common changes", "## How to"
3. **What non-obvious patterns cause failures?** — `Why:`, `Note:`, `Gotcha`, `Don't`
4. **What are the cross-module dependencies?** — "depends on", "imports", `## Cross-module`
5. **What tribal knowledge is hidden in comments / history / human memory?** — `MEMORY.md` / `ADR` / `docs/decisions` 존재

### Score band

| Score | Criteria |
|-------|----------|
| 0     | senior engineer / Slack / 과거 PR에만 지식 존재 |
| 5     | 일부 gotcha가 README / comment에 흩어짐 |
| 10    | 반복 작업의 암묵지 일부 문서화 |
| 15    | compatibility rule / naming / generated code rule / deprecated-but-required rule 정리 |
| 20    | 식별된 tribal knowledge 대부분이 context file / checklist / playbook에 반영 + AI가 질의로 회수 가능 |

자동 점수 = (5질문 통과 평균 × 20). 실제 깊이는 사람이 검증.

---

## D. Cross-Module Dependency & Data Flow Mapping · /15

> 변경 영향 범위를 AI가 추적할 수 있는가.

| Score | Criteria |
|-------|----------|
| 0     | 변경 영향을 사람이 수동으로 추적 |
| 5     | 일부 architecture diagram 또는 dependency note |
| 10    | 주요 module 간 dependency / ownership 문서화 |
| 15    | "What depends on X?" 에 graph / index / map으로 답 가능. repo / service / test / data flow ripple 추적 가능 |

**Auto checks:**
- `docs/architecture.md`, `ARCHITECTURE.md`, `docs/dependency-graph*` 존재
- `mermaid` / `graphviz` 다이어그램 fence 존재
- CLAUDE.md 안에 `## Dependencies` / `Cross-module` 섹션
- monorepo 의 `pnpm-workspace.yaml` / `turbo.json` / `nx.json` 으로 graph 도출 가능 여부

**Why important.** 한 field change가 6개 subsystem에 ripple 되는 대규모 codebase에서 결정적. 이게 약하면 D를 깎는 것이 옳음.

---

## E. Verification & Quality Gates · /15

> AI-generated context와 code change를 검증하는 체계가 있는가.

| Sub | Item | Points | Full-Score Criteria |
|-----|------|--------|---------------------|
| E1 | Reference Accuracy *(Auto)*        | 5 | CLAUDE.md / context file이 언급한 file path · API · command 의 hallucination 0건 |
| E2 | Independent Critic Review *(Manual)* | 4 | 최소 2-3 round 독립 review 또는 checklist (CODEOWNERS / review template / agent critic) |
| E3 | Task Validation *(Auto)*           | 4 | 변경 유형별 build / test / lint / typecheck / e2e 검증 명령 제공 + 실제 실행 가능 |
| E4 | Prompt / Workflow Tests *(Heuristic)* | 2 | 대표 AI task query를 실제 테스트 (`evals/`, agent test) |

**E1 자동 채점 알고리즘:**
1. 모든 context file에서 `[A-Za-z0-9_./-]+\.(py|ts|tsx|js|md|sql|json|yaml|yml|toml)` 후보를 추출
2. 각 후보를 repo 루트 기준으로 존재 검증
3. `valid / total` 비율 → `round(ratio × 5)`

> Meta 표현으로 "zero hallucinated paths"가 5점의 조건. 이것이 AI-ready의 핵심 — 검증되지 않은 context는 없는 것보다 **위험하다**.

---

## F. Freshness & Self-Maintenance · /10

> Context가 stale 해지지 않도록 자동 유지되는가.

| Score | Criteria |
|-------|----------|
| 0     | 수동 관리 + stale 여부 불명 |
| 3     | owner 있음 + 가끔 update |
| 6     | CI / script로 broken path / reference 일부 검출 |
| 10    | 주기적 file path validation, coverage gap detection, critic review, stale reference repair 자동 실행 |

**Auto checks:**
- 각 CLAUDE.md mtime vs 같은 module 내부 코드 파일 latest mtime 비교 — drift 비율
- `.github/workflows/*` 에 context / docs validation step 존재
- pre-commit / husky 에 path validation hook 존재
- `MEMORY.md` Session Notes 의 가장 최근 entry 날짜

**왜 강조되는가.** Stale context는 hallucination을 augmented retrieval로 정당화한다. 없는 것보다 **나쁘다**.

---

## G. Agent Performance Outcomes · /5

> 실제 AI task 성공률 / 효율 개선이 측정되는가.

| Score | Criteria |
|-------|----------|
| 0     | AI 성능 측정 없음 |
| 2     | 정성적으로 "도움 된다" 수준 |
| 3     | 대표 task success rate 또는 human intervention rate 측정 |
| 5     | tool calls, token usage, task completion time, correctness, prompt pass rate를 before / after로 측정 |

**Tracked metrics (예시):**
- AI task pass rate
- 평균 tool calls per task
- 평균 tokens per task
- human clarification count
- failed PR / rework rate
- hallucinated file path count
- time-to-first-correct-change

**Auto checks:**
- `evals/`, `benchmarks/`, `agent-metrics/` 디렉터리 존재
- `.skill-eval.json`, `agent-results.json` 같은 결과 파일
- AI usage telemetry 설정 (Claude Code session log, OpenTelemetry)

---

## Final Grade

| Score | Level | Meaning | Badge color |
|-------|-------|---------|-------------|
| 90-100 | **AI-Native / Agentic-Ready** | Agent가 대부분 반복 작업을 자율 수행 + context layer self-maintaining | green |
| 75-89  | **AI-Ready** | 대부분 작업에서 AI가 안정적으로 navigation, edit, verify | green |
| 60-74  | **AI-Assisted** | AI 유용하지만 complex / domain task에는 human context 필요 | amber |
| 40-59  | **AI-Fragile** | 단순 task는 가능, hidden rule / dependency로 오류 위험 높음 | amber |
| < 40   | **AI-Hostile** | tribal knowledge 의존도 높음 + AI는 추측 기반 | red |

---

## ROI Heuristics for Recommendations

각 갭에 대해 다음 형식으로 액션을 제시:

```
Effort: S (<1h) / M (1-4h) / L (4h+)
Impact: time saved per AI task × estimated tasks/period
Priority = Impact / Effort
```

대표 액션 ROI 표:

| Action | Effort | Impact (typical) |
|--------|--------|------------------|
| 핵심 module에 CLAUDE.md 추가 | S (30-60 min) | task당 2-5 min × 주 N task |
| god file (>500 lines) 분할 | M (1-3 hr/file) | 토큰 30-50% 절감 + 정확도 ↑ |
| `## Cross-module deps` 섹션 추가 | S (30 min) | cascade bug 방지 |
| MEMORY.md / ADR 도입 | M (2-4 hr 초기) | tribal knowledge 보존 (외부화) |
| path validation CI 추가 | S (1 hr) | stale reference 자동 차단 |
| agent eval test 추가 | L (4-8 hr) | AI 회귀 catch |
| naming refactor | M-L | 일관성 향상 (낮은 우선순위) |

상위 5개를 Priority 내림차순으로 정렬해 제시.
