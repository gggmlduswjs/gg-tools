# claude

Claude Code 설정 **정본**. 여러 PC(회사·집)에서 공유한다 — 한 PC에서 고치고 push → 다른 PC에서 pull.

> 예전엔 설정이 네 곳에 흩어져 같은 파일이 서로 다른 버전으로 갈렸다(`CLAUDE.md` 가 3,543B / 7,217B 두 벌).
> 지금은 **여기가 유일한 정본**이고, `install.ps1` 이 각 자리에 꽂는다.

## 새 PC

```powershell
gh auth login                                              # private 레포라 인증 먼저
gh repo clone gggmlduswjs/claude $env:USERPROFILE\claude
pwsh $env:USERPROFILE\claude\install.ps1                   # CLAUDE.md·프로필·훅·메모리·forge
# 그다음 dev bm 반품
```

Claude Code 안에서 **한 줄씩 따로** 친다. 먼저 marketplace 등록:

```
/plugin marketplace add gggmlduswjs/claude
```

그게 끝난 뒤에 설치:

```
/plugin install gg-harness@gg-harness
```

⚠️ **두 줄을 한 번에 붙여넣지 마라.** `marketplace add` 는 입력 프롬프트를 띄우는데,
거기에 두 줄이 통째로 들어가면 `... is not a valid GitHub owner/repo shorthand` 로
튕긴다(2026-08-06 실제로 겪었다).

⚠️ `/plugin install gggmlduswjs/claude` 도 **안 된다** — `Marketplace not found`.
이 레포는 marketplace 이자 plugin 이라(`marketplace.json` 의 `source: "./"`),
등록과 설치가 별개 단계다.

⚠️⚠️ **설치 스코프가 `user` 인지 확인할 것.** 명령 인자로 한 번에 치면 그때 cwd 의
`project` 스코프로 깔린다 — **그 폴더에서만 스킬이 뜨고 다른 레포에선 통째로 없다.**
화면은 조용하다(2026-08-06 실제로 그렇게 깔렸다). `install.ps1` 이 이걸 노란 △ 로 잡는다.
이미 project 로 깔렸다면 `~/.claude/plugins/installed_plugins.json` 에서 해당 항목의
`scope` 를 `user` 로 바꾸고 `projectPath` 를 지우면 된다(형식은 ponytail 항목 참고).

`install.ps1` 은 마지막에 plugin 설치 여부까지 검증한다 — 빨간 X 가 뜨면 위 두 줄을 안 친 것이다.

그다음 **[새PC.md](새PC.md)** — 여기까진 5분이고, 진짜 시간은 `.env` 값과 CDP 로그인 6계정에서 든다.

## 무엇이 어디에

| | 무엇 | 왜 |
|---|---|---|
| **이 레포** | `skills/`(plugin 이 나름) · `home/CLAUDE.md` · `home/agents/` · `home/settings.json` · `powershell/` | git 이 다루는 것 — diff 나오고 되돌릴 수 있다 |
| **`Desktop/forge`** (별도 레포) | forge 스킬 4종 실물 | 활발히 개발 중이라 plugin 에 안 싣는다. `install.ps1` 이 `~/.claude/skills/` 로 junction |
| **G드라이브 `claude-sync`** | 프로젝트별 `*-memory/` 5종 | **누적물**. 두 PC 가 각자 append 하므로 git 이면 파일마다 충돌한다 |
| **각 프로젝트 `.claude/`** | `hooks/` · `rules/` · `CLAUDE.md` | 코드와 **같은 커밋**에 버전이 매겨져야 한다. 훅은 `.dev/plans/be/` 같은 프로젝트 경로를 직접 참조하는 코드다 |

### 심링크 vs 복사 — `install.ps1` 이 나누는 기준

Claude Code 는 `~/.claude/CLAUDE.md` 같은 **정해진 자리만** 보고, 거기 진짜 파일이 있든 링크가 있든 구분하지 않는다. 그래서 실물은 여기 한 벌만 두고 링크로 꽂는다.

- **심링크** — `CLAUDE.md` · `agents/`. 한 벌만 존재해야 하는 것. 어느 PC에서 고쳐도 같은 파일.
- **junction** — `~/.claude/skills/*-forge` → `Desktop/forge/skills/*`. **디렉터리는 junction 을 쓴다** — `New-Item -ItemType SymbolicLink` 는 개발자 모드/관리자가 아니면 **에러 없이 조용히 실패한다**(2026-08-06 실측). junction 은 권한이 필요 없다.
- **복사** — `settings.json` · `statusline.ps1` · `understand-any.ps1`. Claude Code 가 자주 덮어쓰고, `permissions.allow` 는 PC 경로별로 달라야 한다. 심링크면 레포가 늘 dirty 하고 PC 끼리 충돌한다.

`install.ps1` 은 **멱등**이다. 두 번 돌려도 안전하고, 기존 파일은 `-Force` 없이는 안 건드린다.

### plugin 과 install.ps1 의 분담 ★

**스킬은 plugin 이, 나머지는 `install.ps1` 이 나른다**(2026-08-06 전환). 둘 중 하나로 다 되지 않는다.

| | plugin | install.ps1 |
|---|---|---|
| 스킬 22종 | ✅ `/plugin install gg-harness@gg-harness` | — |
| 커맨드 8종(`기획`·`실행`·`상태`·`검토루프` + 영문 별칭) | ✅ 같이 실린다 | — |
| forge 스킬 4종 | ✕ (별도 레포·gitignore) | ✅ junction |
| `CLAUDE.md` · `agents/` | ✕ | ✅ 심링크 |
| `settings.json` · `statusline.ps1` | ✕ | ✅ 복사 |
| PowerShell 프로필 · `.vscode` | ✕ | ✅ |
| Drive 메모리 · `core.hooksPath` | ✕ | ✅ |

plugin 규약은 `skills/`·`commands/` 가 **레포 루트**에 있어야 하고 경로 지정 필드가 없다(설치된 plugin 3개 실물 확인). 그래서 `home/skills/` 를 루트로 올렸다. `hooks/*.py` 는 그대로 둬도 된다 — plugin 은 `plugin.json` 에 `"hooks": "..."` 로 **명시 선언한 것만** 읽는다. 우리는 선언하지 않으므로 무시된다.

**전환의 대가:** 스킬을 고치면 이제 commit → push → `/plugin update` 를 거쳐야 반영된다. 심링크 시절의 즉시 반영을 잃는 대신, 남에게 줄 때 한 줄이 되고 버전이 찍힌다. forge 4종만 예외로 심링크를 남긴 이유가 이것이다 — 아직 활발히 고치는 중이라.

⚠️ **`harness` 를 `harness-steps` 로 개명했다.** 설치된 `harness@harness-marketplace`(revfactory, 에이전트 팀 구성)와 우리 것(jha0313 step 분해 프레임워크)은 **이름만 같고 다른 스킬**이라, plugin 으로 올리면 정면 충돌한다.

**전역 `commands/` 는 8개만 둔다**(2026-08-08 전환). 원래는 "만들지 않는다"였다 — 세션 로그 473개(2026-07-23~08-06)를 세니 프로젝트별 slash command 10개(bookmart 8 · Coupang 2)가 **한 번도 안 불렸다**(같은 기간 스킬은 54회). **호출 빈도가 아니라 복본이 문제라서 뒤집었다**: `기획`·`실행`·`상태`·`검토루프` + 영문 별칭 넷이 bookmart 와 Coupang_v2 에 **글자 하나까지 같게** 복붙돼 있어, 한쪽에서 고친 걸 반대편이 못 받았다(08-07 bookmart 가 찾은 수정을 08-08 Coupang 이 처음부터 다시 찾음). 안 불리는 나머지 커맨드는 그대로 각 레포에 남는다 — 여기 올리는 기준은 **"자주 쓰나"가 아니라 "두 레포에 같은 게 있나"** 다.

## 내용

- `install.ps1` — 프로필 배선 + `~/.claude` 배치 + 메모리 심링크 + 검증
- `powershell/dev-profile.ps1` — `dev bm|cp <이름>`(격리 워크트리에서 claude) · `dev r`(세션 이어하기) · `dev clean` · `dev harvest` · `현황`
- `powershell/wt-engine.ps1` — worktree lifecycle **공용 엔진**. bookmart `bmwt.ps1` · Coupang `wt.ps1` · `devclean` 이 전부 이걸 부른다(2026-07-28 3벌 → 1벌 통합)
- `hooks/tdd_guard.py` — TDD 가드 **공용 엔진**(2026-08-06). 각 레포 `.claude/hooks/tdd_guard.py` 는 환경변수 둘(`TDD_GUARDED`·`TDD_TESTS`)만 정하는 shim 이다. wt-engine 과 같은 배선 — 로직이 한 벌이라 한쪽에서 고친 오탐이 반대편에도 간다. 엔진이 없는 PC 에서는 조용히 통과한다(가드가 작업을 막으면 안 된다)
- `commands/` — **plugin 이 나르는 slash command 8종.** 두 레포에 동일 복본이던 것만 올린다(위 「전역 `commands/`」 참고). 루트에 있어야 plugin 규약이 인식한다
- `skills/` — **plugin 이 나르는 스킬 22종.** 루트에 있어야 plugin 규약이 인식한다. 등록 대조는 `skills/README.md` ↔ 폴더 이름을 pre-commit 이 본다
- `.claude-plugin/plugin.json` — plugin 메타데이터. `name` 은 `gg-harness`
- `.claude-plugin/marketplace.json` — **이 레포를 marketplace 로도 등록**한다(`source: "./"`). 이게 없으면 `/plugin install` 이 `Marketplace not found` 로 튕긴다 — 2026-08-06 실제로 튕겼다
- `home/` — plugin 이 못 나르는 것들(`CLAUDE.md` · `settings.json` · `agents/`). `install.ps1` 이 `~/.claude` 로 꽂는다
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
