# claude

Claude Code 설정 **정본**. 여러 PC(회사·집)에서 공유한다 — 한 PC에서 고치고 push → 다른 PC에서 pull.

> 예전엔 설정이 네 곳에 흩어져 같은 파일이 서로 다른 버전으로 갈렸다(`CLAUDE.md` 가 3,543B / 7,217B 두 벌).
> 지금은 **여기가 유일한 정본**이고, `install.ps1` 이 각 자리에 꽂는다.

## 새 PC (2줄)

```powershell
gh auth login                                              # private 레포라 인증 먼저
gh repo clone gggmlduswjs/claude $env:USERPROFILE\claude
pwsh $env:USERPROFILE\claude\install.ps1                   # 나머지 전부
# 새 터미널 → dev bm 반품
```

그다음 **[새PC.md](새PC.md)** — 여기까진 5분이고, 진짜 시간은 `.env` 값과 CDP 로그인 6계정에서 든다.

## 무엇이 어디에

| | 무엇 | 왜 |
|---|---|---|
| **이 레포** | `home/CLAUDE.md` · `home/skills/` · `home/agents/` · `home/settings.json` · `powershell/` | git 이 다루는 것 — diff 나오고 되돌릴 수 있다 |
| **`Desktop/forge`** (별도 레포) | forge 스킬 4종 실물 | 활발히 개발 중. `home/skills/` 에서 심링크로 당겨 쓴다 |
| **G드라이브 `claude-sync`** | 프로젝트별 `*-memory/` 5종 | **누적물**. 두 PC 가 각자 append 하므로 git 이면 파일마다 충돌한다 |
| **각 프로젝트 `.claude/`** | `hooks/` · `rules/` · `CLAUDE.md` | 코드와 **같은 커밋**에 버전이 매겨져야 한다. 훅은 `.dev/plans/be/` 같은 프로젝트 경로를 직접 참조하는 코드다 |

### 심링크 vs 복사 — `install.ps1` 이 나누는 기준

Claude Code 는 `~/.claude/skills/` 같은 **정해진 자리만** 보고, 거기 진짜 폴더가 있든 심링크가 있든 구분하지 않는다. 그래서 실물은 여기 한 벌만 두고 심링크로 꽂는다.

- **심링크** — `CLAUDE.md` · `skills/` · `agents/`. 한 벌만 존재해야 하는 것. 어느 PC에서 고쳐도 같은 파일.
- **복사** — `settings.json` · `statusline.ps1` · `understand-any.ps1`. Claude Code 가 자주 덮어쓰고, `permissions.allow` 는 PC 경로별로 달라야 한다. 심링크면 레포가 늘 dirty 하고 PC 끼리 충돌한다.

`install.ps1` 은 **멱등**이다. 두 번 돌려도 안전하고, 기존 파일은 `-Force` 없이는 안 건드린다.

### 왜 plugin 이 아닌가 ★

`/plugin install` 형태를 **두 번 검토하고 두 번 접었다**(2026-08-06). 세 번째로 재검토하지 않게 근거를 적는다.

- **구조가 안 맞고, 맞출 값이 없다.** plugin 규약은 `skills/`·`commands/` 가 **레포 루트**에 있어야 하고 경로를 지정하는 필드가 없다(설치된 plugin 3개 실물 확인). 우리는 `home/skills/` 다 — 옮기면 `install.ps1` 심링크·`.gitignore` 의 forge 4종·pre-commit 훅이 전부 같이 깨진다.
- **`hooks/` 는 이름만 같다.** 여기 `hooks/*.py` 는 세 레포가 공유하는 파이썬 엔진이지 Claude Code hooks 규약이 아니다. plugin 으로 인식되면 오히려 오작동한다.
- **`install.ps1` 이 plugin 보다 많이 한다.** 5단계 중 plugin 이 대신할 수 있는 건 「`~/.claude` 배치」 하나뿐이다. PowerShell 프로필 · `.vscode` · Drive 메모리 심링크 · `core.hooksPath` 는 plugin 이 못 한다. 새 PC 는 어차피 `install.ps1` 을 돌려야 한다.
- 지난번 `plugin.json`·`marketplace.json` 은 `installed_plugins.json` 에 한 번도 오른 적 없이 archived 레포를 가리키고 있었다. **아무도 안 쓰는 메타데이터는 낡는 것조차 안 보인다.**

동료에게 나눠 줄 일이 생기면 그때 다시 판단한다. 그전까진 `gh repo clone` + `install.ps1` 두 줄이 같은 일을 더 한다.

**전역 `commands/` 도 만들지 않는다.** 세션 로그 473개(2026-07-23~08-06)를 세니 프로젝트별 slash command 10개(bookmart 8 · Coupang 2)가 **한 번도 안 불렸다** — 같은 기간 스킬은 54회 불렸다. 스킬은 description 이 상황에 맞으면 에이전트가 알아서 부르고, command 는 사람이 타이핑해야 한다. 1인 체제에서 진입점을 늘릴 자리는 command 가 아니라 스킬(또는 `CLAUDE.md` 한 줄)이다.

## 내용

- `install.ps1` — 프로필 배선 + `~/.claude` 배치 + 메모리 심링크 + 검증
- `powershell/dev-profile.ps1` — `dev bm|cp <이름>`(격리 워크트리에서 claude) · `dev r`(세션 이어하기) · `dev clean` · `dev harvest` · `현황`
- `powershell/wt-engine.ps1` — worktree lifecycle **공용 엔진**. bookmart `bmwt.ps1` · Coupang `wt.ps1` · `devclean` 이 전부 이걸 부른다(2026-07-28 3벌 → 1벌 통합)
- `hooks/tdd_guard.py` — TDD 가드 **공용 엔진**(2026-08-06). 각 레포 `.claude/hooks/tdd_guard.py` 는 환경변수 둘(`TDD_GUARDED`·`TDD_TESTS`)만 정하는 shim 이다. wt-engine 과 같은 배선 — 로직이 한 벌이라 한쪽에서 고친 오탐이 반대편에도 간다. 엔진이 없는 PC 에서는 조용히 통과한다(가드가 작업을 막으면 안 된다)
- `home/` — `~/.claude` 로 꽂히는 것들
- `projects/<레포>/` — 그 레포 폴더로 배치되는 것. 지금은 `.vscode/settings.json`(탐색기 `files.exclude`)뿐이다. **`.vscode/` 는 두 레포 다 gitignore 라 PC 를 옮기면 사라지는데**, 캐시·빌드·생성물을 숨기는 설정은 PC 마다 다시 만들 이유가 없어서 정본을 여기 둔다
- `scripts/skill_hitrate.py` — 세션 로그에서 스킬·에이전트 실제 호출 횟수를 센다. 보유 자산이 매 세션 내는 비용(description) 대비 얼마나 불리는지 재는 용도
- `scripts/ci_index.py` — 3레포(`.dev/` · `docs/`)와 Obsidian 을 가로지르는 문서 인덱스·통합 검색(2026-08-06). `--search <낱말>` 이 넷을 한 번에 본다 — "운송장" 은 실제로 4소스 전부에 흩어져 있었다. 한 레포만 grep 하면 나머지 셋을 못 본다. 결과(`_ci/index.md`)는 gitignore — 파생물이고 Obsidian 갱신일이 PC 마다 달라 커밋하면 매번 충돌한다
- `새PC.md` — git 이 못 옮기는 것(`.env` · `.venv` · CDP 로그인 크롬) 체크리스트
- `북마크_레포.md` — 포크 대신 Star 로 돌린 남의 레포 색인

## 규칙 둘 ★

1. **두 PC 에서 동시에 세션을 돌리지 않는다.** 둘 다 메모리에 쓰면 구글드라이브가 «충돌 사본»을 만들어 나중에 어느 게 진짜인지 꼬인다.
2. **세션 시작 전 구글드라이브 초록불(동기화 완료) 확인.** 안 그러면 옛 메모리로 시작한다.

## 외부 도구 — 새 PC 에서 1회 재연결

인증 토큰은 PC 별로 저장되므로 옮기지 않는다(옮기면 사고). 재로그인이 정답이며, **코딩·대화 품질과는 무관**하다.

- [ ] Chrome 확장 «Claude in Chrome» (브라우저 자동화 쓸 때만)
- [ ] Gmail / Google Drive / Google Calendar MCP — 첫 사용 때 재로그인
- [ ] PostHog · Supabase MCP — 재연결
- [ ] `.env` — `새PC.md` 참조. ※ 비밀번호를 채팅에 붙여넣지 말 것

## 전제

- bookmart / Coupang_v2 가 **같은 상위 폴더에 나란히**(기본 `<사용자>\Desktop`)
- 다른 경로면 그 PC 프로필에 `$env:DEV_PROJECTS = '<상위폴더>'`

## 개명 이력 — `dotfiles` → `claude` (2026-08-06)

각 레포의 shim 이 `$HOME\dotfiles\powershell\wt-engine.ps1` 을 **하드코딩**해 불렀다. 개명 즉시 워크트리 도구가 죽으므로 양쪽을 같이 고쳤다(bookmart `568ef27f2` · Coupang `1590279c`).

두 shim 은 **옛 경로를 폴백으로 본다** — 아직 개명을 안 받은 PC 에 `~/dotfiles` 실폴더가 있고, 그쪽이 shim 커밋을 먼저 pull 하면 폴백 없이는 깨진다. 모든 PC 가 이 레포를 새 이름으로 받은 뒤 폴백 줄을 지우면 된다.
