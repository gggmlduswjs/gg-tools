# gg-skills skills

`gg-skills` plugin에 포함되는 핵심 스킬 목록이다. 이 폴더는 plugin package의 정본이며, 설치는 루트 README의 `/plugin marketplace add` + `/plugin install gg-skills@gg-tools` 흐름을 따른다.

이 plugin은 더 이상 디자인, 강의 변환, 회의록, 하네스 실행기, 로컬 PC 배선을 싣지 않는다. 프로젝트별 secret, MCP 인증, 운영 DB project ref는 plugin에 넣지 않고 각 repo/local 설정에 둔다.

## 계획 / 기존 시스템 현대화

| 스킬 | 뭘 하나 |
|---|---|
| **product-spec-kit** | PRD·기능명세서·유저플로우·와이어프레임 세트를 만든다. **외부 `artifact-design` 스킬 의존** — 현재 bootstrap의 자동 설치 대상이 아니므로 사용 전 확인 |
| **existing-system-modernization** | 이미 운영 중인 제품에서 Product Decision → Use Case → Current System Map → Legacy 분류 → Backend Impact → Architecture Escalation → Detox를 보존하고 Superpowers plan으로 넘긴다 |

⛔ **`grilling`·`domain-modeling` 은 여기 없다 — `mattpocock-skills` 플러그인이 정본이다.**
2026-08-30 에 뺐다. 둘 다 [mattpocock/skills](https://github.com/mattpocock/skills) 에서
복사해 온 것이었는데 업스트림이 갱신되는 동안 사본이 낡았다 — `domain-modeling` 은 74줄이
글자 몇 개만 다른 같은 문서였고(업스트림엔 `agents/` 가 더 있다), `grilling` 은 10줄짜리 옛
버전이라 업스트림의 design tree·frontier·라운드 포맷(28줄)을 못 받고 있었다.
`bootstrap.ps1` 이 그 플러그인을 같이 깐다. ⚠️2026-09-01 에 `gg-harness/` 플러그인을 통째로
지워서 그 사본도 같이 사라졌다 — 이제 정본은 `mattpocock-skills` 한 벌이다.

`existing-system-modernization`은 Superpowers를 대체하지 않는다. Superpowers는 brainstorming/planning/TDD/debugging/execution/verification을 담당하고, 이 스킬은 **기존 시스템에서 빠뜨리면 안 되는 조사·보존 항목**만 공통으로 정의한다. 프로젝트별 ERP/WING/DB/디자인 규칙은 각 repo의 얇은 adapter에 둔다.

## 진단

| 스킬 | 뭘 하나 | 산출물 |
|---|---|---|
| **ai-readiness-cartography** | 레포가 agent-friendly 한지 100점 채점 | HTML 대시보드 + ROI 액션 |
| **harness-audit** | 작업 환경 6축의 빈 칸과 썩은 자산을 찾는다 | 판정표 + 다음 액션 |
| **improve-token-efficiency** | Claude Code 세션 로그에서 토큰/컨텍스트 낭비를 찾는다 | HTML 대시보드 + 절감안 |

## Production readiness

| 스킬 | 뭘 하나 |
|---|---|
| **production-readiness-5axis** | 성능·보안·데이터 안전·관측성·하네스 품질 5축으로 현재 repo를 대조한다 |
| **supabase-db-advisor-readonly** | Supabase MCP `get_advisors`를 read-only로 진단하고 마이그레이션 경로만 제안한다 |
| **lighthouse-performance-loop** | Lighthouse/Core Web Vitals 측정 -> 병목 Top 3 -> 재측정 루프를 만든다 |
| **observability-posthog-seo** | PostHog error/analytics와 SEO 기본 자산을 점검한다 |
| **harness-eval** | 스킬·slash command·CLAUDE.md 회귀를 golden set으로 측정한다 |

## 검증

| 스킬 | 뭘 하나 |
|---|---|
| **owasp-security-scan** | 레포 전체를 OWASP Top 10 2025 기준으로 스캔한다 |

## 세컨드 브레인 위키 (LMN / agentic-eng 볼트)

`WIKI_SCHEMA.md` + `wiki/`가 있는 위키 레포에서만 쓴다. 출처: [jha0313/agentic-eng-plugin](https://github.com/jha0313/agentic-eng-plugin).

| 스킬 | 뭘 하나 | slash |
|---|---|---|
| **wiki-ingest** | raw 소스를 위키에 병합·교차링크·index/log 갱신 | `/wiki-ingest` |
| **wiki-lint** | 모순·고아·깨진 링크·방치 stub 건강검진 | `/wiki-lint` |
| **wiki-query** | 위키에 질문 → 인용 붙인 종합 답변 | `/wiki-query` |

## 원칙

1. 같은 일을 하는 스킬을 여러 개 두지 않는다.
2. `SKILL.md`는 대문자여야 인식된다.
3. description에는 사용자가 쓸 법한 트리거 표현을 넣는다.
4. 무거운 내용은 `references/`로 내리고 `SKILL.md`에는 절차만 남긴다.
5. 수정했으면 이 레포에 commit + push 후 `/plugin update gg-skills@gg-tools`로 반영한다.
