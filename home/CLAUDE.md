# Global — Claude Code (모든 프로젝트)

> **상속:** 각 레포의 `CLAUDE.md`·`AGENTS.md`·`.claude/agents/` 가 **이 파일보다 우선**한다.
> 여기는 PC·습관·위임 방식만. 운영 DB·배포·도메인 규칙은 프로젝트 쪽 정본을 따른다.

## 0.5 일하는 방식 — **대화는 계획, 실행은 서브에이전트** (2026-08-04)

> **왜:** 대화창은 **무엇을 왜 할지 정하는 자리**다. 파일 수정·테스트·커밋·PR 이 대화를 채우면
> 판단할 것이 안 보이고 사장님이 기다리게 된다.

**기본값 = 넘긴다.** 코드·스크립트·테스트·커밋·PR 이 필요하면 프로젝트 `.claude/agents/` 의
서브에이전트로 **백그라운드 실행**한다. 물어보지 말고 넘겨라.

⚠️ **예외 — Bookmart.** 거기는 실행 정본이 **Codex + Superpowers** 다(`bookmart/CLAUDE.md` 참조).
Claude 는 설계·리뷰만 하고 승인된 plan 을 `.dev/plans/` 에 남긴다. `executor` 는 기본값이 아니라
**사장님이 "Claude 로 고쳐라"라고 지목했을 때만** 쓴다. `investigator` 는 그냥 써도 된다.

| 에이전트 | 언제 |
|---|---|
| **`executor`** | 파일을 고치고 검증·커밋·PR 까지 — 규칙은 에이전트 정의 파일에 있다 |
| **`investigator`** | 읽기 전용 조사·측정·호출처 추적 — **고치지 않는다** |

★ **긴 프롬프트를 매번 다시 쓰지 마라.** 함정·경로·검증 명령은 **에이전트 정의 파일**에 박아라.
넘길 때는 **무엇을 · 왜 · 무엇으로 검증**만 적는다. 규칙이 낡았으면 정의 파일을 고쳐라.

**독립적인 일은 동시에 띄운다** — 서로 다른 worktree·브랜치를 쓰면 안 부딪힌다.

**대화창에서 직접 할 것은 이것뿐:**
1. 계획·설계 판단, 트레이드오프, 결론 하나로 수렴
2. 에이전트 결과 **검증**(낡은 체크아웃·오탐 — 특히 `origin/main` 대조)
3. 되돌리기 어려운 것: 운영 DB 마이그 **적용** · WING `--apply` · **머지** · 서버 systemd/cron 직접 변경
4. 5초짜리 확인 한 줄

⛔ 에이전트에게 **머지·운영 DB 쓰기·WING `--apply`·마이그레이션 적용**을 시키지 마라.

### 위임 단위 — **요청 하나 = 에이전트 하나**

⛔ 한 에이전트에 여러 건을 얹지 마라. 급한 것과 느린 것을 묶으면 **급한 것이 늦어진다.**
⛔ 띄운 뒤 범위를 늘리지 마라. 새 요청 → **새 에이전트.**
⛔ **에이전트에게 내 워크트리를 물려주지 마라** — 각자 worktree를 따게 한다.

⚠️ **`SendMessage` 는 즉시 도착하지 않는다.** 방향 전환은 비싸다. 멈출 땐 **무엇을 멈추고 무엇을 하라**만 적는다.

⚠️ 「왜 이렇게 오래 걸리냐」= 재촉이 아니라 **진단 요청**. 경과 시간·커밋 수·지금 만지는 파일을 숫자로 대고, 쪼개서 다시 띄워라.

⚠️ 본업은 **`TaskCreate` 로 박아라** — 완료 기준이 "말로 끝"이 아니라 **남은 건수 0**인 작업은 태스크 없이 시작하지 마라.

## 1. Git·커밋 (공통)

⛔ **`git add -A` / `git add .` 금지** — 고친 파일만 이름으로 add. 커밋 전 `git status --short` 로 섞임 확인.
⛔ **커밋은 사용자가 요청했을 때만.** push·force push·`--no-verify` 는 명시 승인 없이 하지 마라.
워크트리 규칙·브랜치 정리는 **각 레포 `CLAUDE.md`** 를 따른다 (`bmwt.ps1` / `wt.ps1`).

## 2. 프로세스·안전 (공통)

⛔ **프로세스를 이름·패턴으로 훑어 죽이지 마라** — `Stop-Process -Id <숫자>` 로 pid 를 **하나씩** 지목.
`Get-Process python | Stop-Process` · `-match runserver` 일괄 kill 금지 (남의 세션·하네스 감독이 같이 죽는다).
포트가 겹치면 **빈 포트를 고른다.** 남의 것을 죽여 자리를 만들지 마라.

## 3. 언어·커뮤니케이션

- **한국어**로 대화. 코드·경로·커밋 메시지는 레포 관례를 따른다.
- 구현 전 **plain 한국어로 무엇을 할지 먼저 설명** — 프로젝트가 「ㄱㄱ」 승인을 요구하면 그때 코드.
- 숫자·판정은 **재현 가능하게** — "N건"만 던지지 말고 조건·출처를 적는다.

## 4. 이 PC (MSI) — 경로

| 무엇 | 어디 |
|---|---|
| Bookmart | `C:\Users\MSI\Desktop\bookmart` · worktree `...\bookmart-wt\` |
| Coupang v2 | `C:\Users\MSI\Desktop\Coupang_v2` · worktree `...\Coupang_v2-wt\` |
| Obsidian (bookmart) | `G:\내 드라이브\Obsidian\30. Workspace\bookmart\` |
| 전역 스킬 | `~/.claude/skills/` — 지도는 `skills/README.md` |
| Agent Monitor | `C:\Users\MSI\Desktop\tools\Claude-Code-Agent-Monitor` |
| 통합 검색 (있을 때) | `python ~/claude/scripts/ci_index.py --search <낱말>` |

⚠️ 옛 경로 `C:\Users\user\...` 가 문서·junction 에 남아 있으면 **MSI 경로로 고친다.**

## 5. 전역 스킬 — 언제 무엇

| 하려는 것 | 스킬 |
|---|---|
| 레포 agent-ready 점수 | `ai-readiness-cartography` |
| 하네스·환경 빈칸 | `harness-audit` |
| 계획 구멍 찾기 | `grill-me` |
| 코드 리뷰 | `code-review-7p` |
| 보안 전체 스캔 | `owasp-security-scan` |
| Supabase DB 진단 | `supabase-db-advisor` |
| 토큰·비용 | `improve-token-efficiency` |
| HTML 보고서 | `report` |

forge(`arch-forge`·`backend-forge`·`frontend-forge`)는 **필요할 때만** — bookmart `_scripts/install_forge.ps1`.

## 6. Cursor

Karpathy 행동 가이드는 각 프로젝트 `.cursor/rules/karpathy-guidelines.mdc` (`alwaysApply`).
Cursor는 `.claude/` 를 기본으로 읽지 않는다 — **Claude Code 세션**이 이 파일의 정본 사용자다.
