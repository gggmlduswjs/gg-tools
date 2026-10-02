# gg-skills skills

`gg-skills` plugin에 포함되는 핵심 스킬 목록이다. 이 폴더는 plugin package의 정본이며, 설치는 루트 README의 `/plugin marketplace add` + `/plugin install gg-skills@gg-tools` 흐름을 따른다.

이 plugin은 더 이상 디자인, 강의 변환, 회의록, 하네스 실행기, 로컬 PC 배선을 싣지 않는다. 프로젝트별 secret, MCP 인증, 운영 DB project ref는 plugin에 넣지 않고 각 repo/local 설정에 둔다.

## 폴더 분류

스킬은 분류 폴더 아래에 둔다. 플러그인에 실리는 것은 `.claude-plugin/plugin.json`의 `skills` 배열에 적힌 스킬뿐이다. 새 스킬은 `in-progress/`에서 시작하고, 쓸 만해지면 분류 폴더로 옮겨 배열에 등록한다.

| 폴더 | 담는 것 | 플러그인에 실림 |
|---|---|---|
| `engineering/` | 코드·제품 작업 | 예 |
| `diagnostics/` | 진단·점수 | 예 |
| `second-brain/` | 위키(세컨드 브레인) 운영 | 예 |

| `misc/` | 드물게 쓰는 것 | 아니오 |
| `in-progress/` | 시험 중 | 아니오 |
| `deprecated/` | 더 안 쓰는 것 | 아니오 |

## 스킬 선택 기준 — 한 요청에 기본 한 종류만

| 사용자가 원하는 일 | 우선 선택 | 중복 호출 방지 |
|---|---|---|
| 기능을 설계·구현·테스트·디버깅 | 외부 **Superpowers** | gg-skills에서 같은 범용 개발 과정을 다시 구현하지 않음 |
| 운영 중 제품의 기존 기능 변경 | **existing-system-modernization + 프로젝트 규칙** | Superpowers를 대체하지 않고 기존 시스템 조사 항목만 추가 |
| PRD·기능 명세·유저플로우·와이어프레임 **4종 묶음 HTML** | **product-spec-kit** | 일반 구현 계획은 Superpowers. 단순 PRD를 위해 4종 산출물 강제하지 않음 |
| 운영 레포 전체 보안 진단 | 해당 레포의 **전용 보안 스킬** 우선. 없을 때 **owasp-security-scan** | 로컬 스킬이 있으면 공통 스킬 자동 중복 실행 금지 |
| Supabase Advisor 진단 | 해당 레포의 **전용 DB 스킬** 우선. 없을 때 **supabase-db-advisor-readonly** | 인증·DB ref는 프로젝트가 소유; 둘 다 중복 호출하지 않음 |
| 보안·성능·관측성·데이터 안전의 광범위 종합 점검 | **production-readiness-5axis** | 전문 스킬의 결과를 재사용, 필요할 때만 미측정 축 실행 |
| 개인 지식 위키 작업 | **wiki-ingest/lint/query** | `WIKI_SCHEMA.md`가 있는 위키 레포에서만 |

> 프로젝트 전용 스킬 우선 규칙은 **라우팅 계약**이다. 프롬프트 문구만 고쳤다고 AI 자동 선택이 실제로 보장되는 것은 아니다. 사용 중인 Claude 세션에서 스킬 노출·선택과 테스트를 별도로 확인한다.

### 설치·호출 검증 (새 PC·설정 변경 후)

`bootstrap.ps1` 설치 대상은 루트 `plugins.json`에 적혀 있다.

로컬 상태 확인은 루트에서 `pwsh ./scripts/check_skill_wiring.ps1`을 실행한다. Bookmart/Coupang 경로를 제공하면 전용 Hook selftest도 확인한다. 이 검사는 설치 등록과 파일·지정 selftest만 확인하며 **실제 Claude/Codex 세션의 Skill 자동 호출까지 검증하는 것은 아니다.**

`product-spec-kit`은 플러그인 내 HTML 에셋만으로 작성할 수 있게 되어 있으며 `artifact-design`은 **선택적**이다. 설치되지 않은 외부 스킬이 필수인 것처럼 호출하지 않는다.

## 라우터

| 스킬 | 뭘 하나 |
|---|---|
| **onboard** | 새 PC·새 프로젝트의 개발 환경(도구·플러그인·차단 엔진·프로젝트 틀·위키·저장소)을 `sources.yaml` 기준으로 점검하고 빠진 것을 안내한다. 읽기 전용, 설치는 승인 후 |
| **ask-gg** | 어떤 스킬을 언제 쓰는지 안내한다. 스킬을 추가·삭제하면 이 스킬의 표도 같이 고친다 |

## 계획 / 기존 시스템 현대화

| 스킬 | 뭘 하나 |
|---|---|
| **product-spec-kit** | PRD·기능명세·유저플로우·와이어프레임 4종 묶음 HTML을 만든다. 자체 에셋 사용; `artifact-design`은 선택 사항 |
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
| **owasp-security-scan** | 레포 전용 보안 스킬이 없을 때 OWASP Top 10 2025 기준으로 점검. 일반 레포에 특정 프로젝트의 확장 기준을 강요하지 않는다 |

## 세컨드 브레인 위키

`WIKI_SCHEMA.md`가 있는 위키 폴더에서만 쓴다. 빈 틀은 [wiki-template](https://github.com/gggmlduswjs/wiki-template). 패턴의 출처는 Karpathy의 LLM Wiki 아이디어 문서이고, 스킬은 우리 스키마에 맞춰 새로 썼다.

| 스킬 | 뭘 하나 |
|---|---|
| **wiki-ingest** | raw 원본을 읽어 출처 요약·개념·인물·도구 페이지로 통합하고 index/log를 갱신한다 |
| **wiki-query** | 위키에 물어 `[[페이지]]` 인용이 달린 답을 받고, 가치 있는 답은 새 페이지로 저장할지 묻는다 |
| **wiki-lint** | 깨진 링크·고아·모순·낡은 주장·빠진 개념·죽은 노드 후보를 점검해 보고한다(승인 후에만 수정) |

## 원칙

1. 같은 일을 하는 스킬을 여러 개 두지 않는다.
2. `SKILL.md`는 대문자여야 인식된다.
3. description에는 사용자가 쓸 법한 트리거 표현을 넣는다.
4. 무거운 내용은 `references/`로 내리고 `SKILL.md`에는 절차만 남긴다.
5. 수정했으면 이 레포에 commit + push 후 `/plugin update gg-skills@gg-tools`로 반영한다.
