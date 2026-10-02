---
name: production-readiness-5axis
description: 레포를 프로덕션 준비 5축(성능·보안·데이터 안전·관측성·하네스 품질)으로 점검하고, 이미 있는 프로젝트 자산과 빠진 축을 대조한다. "프로덕션 레벨", "production readiness", "운영 준비", "5축 점검", "성능 보안 데이터 안전 관측성 품질", "강의 Ch03 기준으로 봐줘" 같은 요청에 트리거. 실행보다 진단이 기본이며, 위험한 변경은 제안만 한다.
---

# Production Readiness 5-Axis

이 스킬은 "프로덕션 레벨 = 측정 가능한 5축"을 플러그인 수준의 공용 체크로 만든다.

중요: 이 스킬은 **프로젝트별 설정을 대신하지 않는다.** DB project ref, MCP 인증, PostHog key, 배포 secret, staging 주소는 각 repo에 있어야 한다. 플러그인은 점검 절차와 판단 기준만 제공한다.

## 5축

| 축 | 통과 질문 | 대표 근거 |
|---|---|---|
| 성능 | 유저가 기다리지 않는가 | Lighthouse/Core Web Vitals, 느린 뷰/쿼리 근거 |
| 보안 | 알려진 취약 패턴이 없는가 | OWASP 전체 스캔, PR diff 리뷰 |
| 데이터 안전 | 운영 데이터를 실수로 망가뜨리지 않는가 | read-only 연결, staging, migration-only 변경 경로 |
| 관측성 | 장애와 사용 흐름이 보이는가 | error tracking, product analytics, uptime, alert |
| 하네스 품질 | 에이전트/스킬/룰이 회귀하지 않는가 | golden set, eval, false-positive 케이스 |

## 절차

### 1. 현재 자산 대조

먼저 프로젝트 안의 자산을 읽는다. 없으면 없다고 표시한다.

```bash
ls .claude/skills .claude/commands .claude/hooks 2>/dev/null
cat .claude/settings.json 2>/dev/null
cat .mcp.json 2>/dev/null
ls .github/workflows 2>/dev/null
ls .dev/harness/evals 2>/dev/null
```

읽을 문서:

- `CLAUDE.md`, `AGENTS.md`
- `docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/PRODUCT.md`
- `.github/workflows/*.yml`
- `.claude/skills/README.md`가 있으면 우선 읽기

### 2. 축별 판정

각 축을 `있음 / 부분 / 없음 / 썩음` 중 하나로 판정한다.

- **있음**: 실행 경로와 검증 경로가 모두 있다.
- **부분**: 문서나 스킬은 있으나 CI/인증/실행 루프가 없다.
- **없음**: 자산이 없다.
- **썩음**: 파일은 있지만 경로·명령·전제가 현재 repo와 맞지 않는다.

반드시 경로 근거를 붙인다. "있을 것 같다"는 실패다.

### 3. 필요한 스킬로 라우팅

- 보안 코드 전체 스캔: `owasp-security-scan`
- Supabase live DB advisor: `supabase-db-advisor-readonly`
- 성능 측정 루프: `lighthouse-performance-loop`
- 관측성/PostHog/SEO: `observability-posthog-seo`
- 하네스 회귀 측정: `harness-eval`

프로젝트에 더 구체적인 로컬 스킬이 있으면 로컬 스킬을 우선한다. 예: `.claude/skills/bookmart-db-advisor`가 있으면 공용 `supabase-db-advisor-readonly`보다 그쪽이 우선이다.

### 4. 출력 형식

```markdown
## Production Readiness

| 축 | 판정 | 근거 | 다음 액션 |
|---|---|---|---|
| 성능 | 부분 | ... | ... |

## 바로 할 일
1. ...
2. ...
3. ...

## 플러그인으로 해결되는 것 / 프로젝트에 남아야 하는 것
- 플러그인: 공용 절차, 루브릭, 스킬
- 프로젝트: DB ref, MCP 인증, 배포 secret, 서비스별 운영 규칙
```

## 금지

- 운영 DB 쓰기, `execute_sql`, `apply_migration`, 수동 migrate를 실행하지 않는다.
- PostHog/Supabase/Vercel 등의 secret을 플러그인 파일에 넣자고 제안하지 않는다.
- Lighthouse 점수 100점을 목표로 만들지 않는다. 목표는 병목 상위 1~3개와 전후 측정이다.
- 보안 발견을 자동 수정하지 않는다. critical/high는 사람 승인 후 고친다.
