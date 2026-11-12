---
name: ask-gg
description: gg-skills 에 어떤 스킬이 있고 언제 무엇을 쓰는지 안내하는 라우터. "어떤 스킬 써야 해", "gg 스킬 뭐 있어", "점검 도구 추천" 같은 질문에 쓴다.
---

# ask-gg — 어떤 스킬을 쓸까

사용자 요청을 아래 표에 대응해 **스킬 하나**를 고르고, 이유를 한 줄로 말한 뒤 그 스킬을 호출한다. 표에 없으면 없다고 말한다.

호출 전에 현재 환경의 설치된 스킬 목록을 확인한다. Codex에서는 `gg-skills:<이름>`을 사용하고 프로젝트 규칙 리뷰는 `project-review`로 연결한다. 외부 스킬은 설치된 경우에만 연결한다. 아래 내장 `/code-review`·`/security-review`는 Claude 전용 명령이며 Codex에서는 실제 제공되는 리뷰 기능·보안 스킬을 사용한다.

| 하려는 일 | 스킬 |
|---|---|
| 새 PC·새 프로젝트 환경 점검, 온보딩 | `onboard` |
| 운영 중인 제품의 기존 기능 변경 | `existing-system-modernization` (구현은 Superpowers) |
| PRD·기능명세·유저플로우·와이어프레임 묶음 | `product-spec-kit` |
| 레포 보안 점검 | `owasp-security-scan` (레포 전용 보안 스킬이 있으면 그것 먼저) |
| Supabase DB 진단 | `supabase-db-advisor-readonly` |
| 성능·보안·데이터 안전·관측성 종합 점검 | `production-readiness-5axis` |
| Core Web Vitals 측정과 개선 | `lighthouse-performance-loop` |
| 에러 추적·분석·SEO | `observability-posthog-seo` |
| 레포가 AI에게 읽기 좋은지 점수 | `ai-readiness-cartography` (외부 `skills_repo`) |
| 토큰·비용 낭비 | `improve-token-efficiency` (외부 `skills_repo`) |
| 스킬 평가 사례 작성·실행 | `eval-writer` · `skill-evaluator` (외부 `skills_repo`) |
| 여러 작업자에게 나눠 맡기기 | `workflow-orchestrator` (외부 `skills_repo`) |
| 스킬·CLAUDE.md 회귀 측정 | `harness-eval` |
| 위키에 넣기 / 묻기 / 점검 | `wiki-ingest` / `wiki-query` / `wiki-lint` (`WIKI_SCHEMA.md`가 있는 위키에서만) |

다른 플러그인이 정본인 일: 설계·계획·TDD·디버깅은 Superpowers, 질문으로 계획 구멍 찾기와 도메인 모델링은 mattpocock-skills, 코드 리뷰는 내장 `/code-review`, 변경분 보안 리뷰는 내장 `/security-review`.

**유지 규칙:** 스킬을 추가·삭제·이름 변경하면 이 표도 같이 고친다. 표에 없는 스킬은 존재를 모르는 것과 같다.
