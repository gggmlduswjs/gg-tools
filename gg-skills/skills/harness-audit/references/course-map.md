# 강의 지도 — 13챕터 ↔ 이미 있는 스킬

강의: **실리콘밸리 엔지니어의 Claude Code** (하재상 · 4 Parts / 13 Chapters / 20+h)
인덱스: https://app.notion.com/p/3f045b2b66b3825cbf390198861601f7

**이 표의 진짜 용도는 오른쪽 열이다** — 새로 만들려는 게 이미 있는지 먼저 본다.
(오른쪽 열은 2026-07-28 실측. 스킬이 늘거나 줄면 갱신할 것.)

| Part·Ch | 주제 | 핵심 | 이미 스킬로 구현됨 |
|---|---|---|---|
| **0·01** | 강사 소개 & 개요 | Vibe / Agentic / Harness 3키워드. 도구보다 방법론이 본질 | — (프레임 소개만) |
| **0·02** | AI-Native 일하기 | **수집=AI / 판단=사람 / 실행=AI**. 5습관 · 계획검토 4체크 · 팀 하네스 3요소 | — |
| **1·01** | Claude Code 딥다이브 | 확장 7계층 · 컨텍스트 로트 50/80 · 권한모드 5종 · Subagent vs Team · Hook/Loop/Routine · **CLI 기본, MCP 예외** | — |
| **1·02** | Vibe Coding 한계 | 핵심은 **"코드를 안 읽는 것"**. 온램프이지 목적지 아님. 배포 전 체크리스트 5문 | — |
| **1·03** | Agentic Engineering | **5 Pillars** Context·Validation·Tooling·Codebases·Compound. **50% 룰** · Consistency over DRY | — |
| **1·04** ⭐ | **Harness Engineering** | **6축**(구조·맥락·계획·실행·검증·개선) · 경계 3종 · Generator≠Evaluator · 빈도 트리거 | **이 스킬의 프레임 원본** |
| **1·05** | 실전 테크닉 11자산 | CLAUDE.md · AI-Ready · Second Brain · Team Plugin · TDD/SDD · 토큰 · 코드리뷰 · Guardrails · Oncall | `ai-readiness-cartography` · `improve-token-efficiency` · 내장 `/code-review` |
| **2·01** | Full-Stack SaaS | SDD 5단계 · **Grill-me**(설계 단계 adversarial) · PRD/Arch/ADR · `execute.py` 루프 | **`harness`** · `grilling`·`grill-me`·`grill-with-docs` · `product-spec-kit` · `domain-modeling` |
| **2·02** | Autonomous PR Reviewer | 심각도 4단계=**자동화의 계약서** · 차원별 병렬 · 게이트 · **오탐 1건=신뢰 10건** | 내장 `/code-review` (+ `/review` 프로젝트 축) |
| **2·03** ⭐ | Production Scalability | 프로덕션 **5축**(성능·보안·데이터안전·관측성·**품질**). **품질 = 하네스 Eval** · read-only 원칙 | `owasp-security-scan` · `supabase-db-advisor` · **Eval 은 스킬 없음** |
| **2·04** | CI/CD 통합 에이전트 | **Alert as Code** — 클릭에서 코드로. 노이즈/신호 판정 · **빈손으로 깨우지 않는다** | — |
| **3·01** ⭐ | AX 마인드셋 | in the loop → **on the loop**. 못 맡기겠다 = 툴·컨텍스트 신호. **자산도 썩는다(staleness)** · 지속개선 루프 | **없음 — 이 스킬이 담당** |
| **3·02** | AX 프로세스 전환 | JIT 로드맵 · **Ask Claude, not the author** · Trust but verify · 커리어 5 tiers | — (조직용, 1인 운영엔 대부분 N/A) |
| **4·01** | 24/7 Hermes | on the loop → **always-on**. SOUL/USER/AGENTS 3파일 · Cron·이벤트·대화 3트리거 | — |

## 챕터 URL

```
0·01 e6445b2b66b38267adcd01c0f0ef0948   0·02 a1445b2b66b383f08102013c6c652b3e
1·01 69045b2b66b382eca69f018a04f53e8a   1·02 a0945b2b66b382d3aa02815a8129e241
1·03 9a245b2b66b3831da30d012d0de1a412   1·04 30345b2b66b38274a6ef818f0c36a2ac
1·05 ccd45b2b66b3832982b28114c74d86c3   2·01 ec345b2b66b3820c9f2d81e3cc56580a
2·02 4c745b2b66b382b8b21181d9f01e11bc   2·03 ea345b2b66b3839c92aa012d4d24fd4a
2·04 4b445b2b66b382a4b71a815c50173465   3·01 a6745b2b66b38261995081b4648ea297
3·02 17645b2b66b3837e8cb301ebc9a03e8c   4·01 af145b2b66b3833ab2ea018840012fc6
```

원문이 필요하면 Notion MCP `notion-fetch` 에 위 ID. **평소엔 fetch 하지 말 것** — 여기 압축본으로 충분하고,
헤드리스·cron 환경엔 Notion MCP 가 아예 없다.

## 실습 repo (강의 §8)

```
github.com/jha0313/harness_framework   6축이 깔린 환경에서 앱 하나 (= `harness` 스킬의 원본)
github.com/revfactory/harness          하네스로 하네스를 짓는 메타 실습
github.com/obra/superpowers            잘 만들어진 실전 스킬 모음 — 읽고 분석용
```

## 남은 빈 칸 (2026-07-28 기준)

스킬이 없는 축 3개. **필요할 때 만들되, 없다는 이유만으로 만들지 말 것.**

1. **하네스 Eval** (2·03 §5 · 3·01 §6) — golden set → LLM-as-judge → 실패 분류 → fixer → a/b(0 regression) → human review → golden 피드백.
   bookmart 는 `.dev/harness/evals/` 로 손수 구현돼 있다 — 스킬화 전에 그걸 먼저 볼 것.
2. **Alert as Code** (2·04 §6) — 클릭으로 만든 alert·설정은 에이전트가 못 고친다. 코드로 옮기면 PR 로 줄일 수 있다.
3. **always-on** (4·01) — Cron·이벤트 트리거. Claude Code 의 `/loop`·`/routine` 이 일부 대체.
