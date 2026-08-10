# gg-harness

Claude Code plugin source. 이 레포는 **플러그인 자산만** 담는다.

## 포함하는 것

- `.claude-plugin/` — plugin/marketplace manifest
- `skills/` — 계획·진단·검증 스킬 13개
- `commands/` — slash command 4개(`/기획`, `/plan`, `/운영준비`, `/production-readiness`)
- `README.md` — 설치와 운영 기준

## 포함하지 않는 것

다음은 PC별 개인 설정이거나 헷갈림이 큰 자동화라 이 레포와 GitHub plugin 패키지에서 뺐다.

- `install.ps1`
- 전역 `CLAUDE.md`, `settings.json`, statusline 파일
- PowerShell profile/dev launcher/worktree helper
- 전역 hooks, token/cost/touch log scripts
- 프로젝트별 `.vscode`/git hook 배선
- 하네스 실행/상태/review-loop slash command
- 프로젝트별 secret, MCP 인증, 운영 DB project ref
- 디자인/강의/문서변환/외부서비스용 실험 skill

필요하면 로컬 PC나 별도 plugin에서 따로 관리한다. `gg-harness`에는 매일 쓸 핵심만 둔다.

## 설치

Claude Code 안에서 한 줄씩 실행한다.

```text
/plugin marketplace add gggmlduswjs/claude
/plugin install gg-harness@gg-harness
```

이미 설치되어 있으면:

```text
/plugin update gg-harness@gg-harness
```

## 역할 분리

- 개인 기본값: `C:\Users\user\.claude\CLAUDE.md`
- 프로젝트 규칙: 각 프로젝트의 `CLAUDE.md` / `AGENTS.md`
- 재사용 자산: 이 레포의 공용 `skills/`와 slash `commands/`
- worktree/harness/PowerShell 런처: 사용자가 명시했을 때만 쓰는 로컬 고급 도구

## 남긴 skills

- `grilling`
- `domain-modeling`
- `product-spec-kit`
- `ai-readiness-cartography`
- `harness-audit`
- `improve-token-efficiency`
- `code-review-7p`
- `owasp-security-scan`
- `production-readiness-5axis`
- `supabase-db-advisor-readonly`
- `lighthouse-performance-loop`
- `observability-posthog-seo`
- `harness-eval`

## Production readiness

강의 Part 2 Ch03의 5축(성능·보안·데이터 안전·관측성·하네스 품질)은 plugin-level 공용 스킬로 제공한다.

- `/운영준비` 또는 `/production-readiness` — 현재 repo의 5축 자산/빈칸 대조
- `owasp-security-scan` — 코드 전체 OWASP 점검
- `supabase-db-advisor-readonly` — 프로젝트 MCP가 있을 때 read-only DB advisor 진단
- `lighthouse-performance-loop` — 측정 기반 성능 개선 루프
- `observability-posthog-seo` — PostHog/analytics/SEO 점검
- `harness-eval` — golden set 기반 하네스 회귀 측정

단, DB ref·OAuth·PostHog key·배포 secret·staging 주소는 각 프로젝트 repo/서비스 설정에 남긴다. 플러그인은 절차와 루브릭만 배포한다.

## 개발 규칙

1. 스킬을 추가하거나 지우면 `skills/README.md`도 같이 갱신한다.
2. plugin에 넣을 수 없는 PC별 배선 파일은 루트에 만들지 않는다. `.gitignore`의 local machine wiring 목록에 둔다.
3. 변경 후 commit/push하고 Claude Code에서 `/plugin update gg-harness@gg-harness`를 실행한다.
