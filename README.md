# gg-harness

Claude Code plugin source. 이 레포는 **플러그인 자산만** 담는다.

## 포함하는 것

- `.claude-plugin/` — plugin/marketplace manifest
- `skills/` — 계획·진단·검증·행동 스킬 14개
- `commands/` — slash command 2개(`/harness`, `/review`)
- `hooks/tdd_guard.py` — TDD 가드 **엔진**(각 레포 shim이 호출)
- `README.md` — 설치와 운영 기준

## 포함하지 않는 것

- `install.ps1`, 전역 `CLAUDE.md`/`settings.json`/statusline
- PowerShell profile/dev launcher/worktree helper/`ai.ps1` 엔진
- 전역 hooks(그 외), token/cost/touch log scripts
- 프로젝트별 `.vscode`/git hook 배선 · `settings.json` 훅 목록
- **실행기** `execute.py` — 각 레포 `.dev/harness/execute.py`에 둔다(커밋/push 안 함)
- 프로젝트별 secret, MCP 인증, 운영 DB project ref
- 디자인/강의/문서변환/외부서비스용 실험 skill
- 얇은 래퍼 slash(`/기획`·`/plan`·`/운영준비` 등) — 스킬을 직접 쓴다

## 설치

```text
/plugin marketplace add gggmlduswjs/claude
/plugin install gg-harness@gg-harness
```

이미 설치되어 있으면:

```text
/plugin update gg-harness@gg-harness
```

## 역할 분리

| 층 | 자리 | 예 |
|---|---|---|
| 개인 기본 | `~/.claude/` | 개인 CLAUDE.md, 모니터 훅 |
| 회사 공용 | 이 플러그인 | `/harness` `/review`, grilling, code-review-7p, tdd 엔진 |
| 프로젝트 | 각 레포 | `CLAUDE.md`, `.dev/harness/execute.py`, 도메인 훅/스킬/agents |

bookmart와 Coupang_v2는 **같은 UX**(`/harness`·`/review`·얇은 execute)를 쓰고, 안전 규칙·도메인 가드만 레포에 남긴다.

## 공용 slash commands

- `/harness <작업>` — phase/step 설계. 승인 전 구현 금지. 실행은 `python .dev/harness/execute.py <task>`
- `/review [범위]` — 문서·운영 안전 관점 읽기 전용 리뷰. 프로젝트 전용 게이트는 그 레포 `CLAUDE.md`를 따른다

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
- `karpathy-guidelines` — [Andrej Karpathy](https://github.com/multica-ai/andrej-karpathy-skills) 행동 가이드 4원칙

운영 준비 5축은 slash 없이 `production-readiness-5axis` 스킬을 직접 호출한다.

## 개발 규칙

1. 스킬을 추가하거나 지우면 `skills/README.md`도 같이 갱신한다.
2. plugin에 넣을 수 없는 PC별 배선 파일은 루트에 만들지 않는다. `.gitignore`의 local machine wiring 목록에 둔다.
3. 변경 후 commit/push하고 Claude Code에서 `/plugin update gg-harness@gg-harness`를 실행한다.
