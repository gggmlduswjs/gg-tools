# hooks — Claude Code 공용 훅 엔진

레포 shim(`.claude/hooks/*.py`)이 `runpy` 로 여기를 부른다. **로직은 여기 한 벌.**

⚠️★★★ **엔진의 자리는 여기(`gg-harness/hooks/`) 하나다.** 레포 루트의 `hooks/` 는
2026-08-11 플러그인 nest 이전 자리이고 지금은 gitignore 다 — 거기 파일을 두지 마라.

> **왜 이 경고가 있나 (2026-08-13):** 08-11 에 엔진이 `hooks/` → `gg-harness/hooks/` 로
> 순수 rename 됐는데, **로컬 디스크의 옛 폴더를 안 지웠다.** 북마트 shim 은 새 자리를
> 따라갔지만 쿠팡 shim 은 옛 경로를 계속 가리켰고, 거기 추적 안 되는 142줄짜리 옛
> 엔진이 남아 있어서 **조용히 옛 로직으로 돌았다**(이틀간 개선분 0). 파일이 아예
> 없었으면 shim 이 `exit 0` 해서 금방 티가 났을 것이다 — **잔재가 실패를 감췄다.**
> 그래서 shim 은 경로를 박지 말고 **후보 순서**(새 자리 먼저, 옛 자리 폴백)로 쓴다.

## tdd_guard.py

PreToolUse[Write|Edit] — 가드 범위 소스를 고칠 때 테스트 참조가 없으면 `ask`(기본).

환경변수 (shim 이 설정):
- `TDD_GUARDED` — 콤마 구분 path 토큰 (예: `/src/orders/services/`)
- `TDD_TESTS` — 테스트 루트 glob (예: `src/*/tests,tests`)
- `TDD_DECISION` — `ask`(기본) 또는 `deny` (데모 프로젝트식 하드 차단)

self-test: `python ~/claude/gg-harness/hooks/tdd_guard.py --selftest`

## commit_sentinel.py

post-commit — 방금 만든 커밋이 이상하면 **알린다**(막지 않는다). 크기·오염·세션교차·stale·머지를 본다.

환경변수 (shim 이 설정):
- `SENTINEL_FILES` — 파일 수 임계 (쿠팡 `post-commit` 은 50)
- `SENTINEL_DIRS` — 최상위 디렉터리 수 임계 (6)
- `SENTINEL_SESSIONS` — 세션 기록 경로 (`.claude/sessions`)

self-test: `python ~/claude/gg-harness/hooks/commit_sentinel.py --selftest` (20 cases)

> **왜 여기로 왔나 (2026-08-13):** 08-10 대청소(`d4e56c5`)가 로컬 배선과 함께 이 파일도
> git 에서 뺐다. 그 뒤 **추적이 안 되니 새 PC 에는 아예 없었고**, 훅은 `[ -f ] || exit 0`
> 로 조용히 통과했다. 북마트는 *"commit_sentinel 이 없어 호출이 전부 no-op 이었다"* 며
> 08-11 에 `post-commit` 자체를 지웠다 — **추적을 안 해서 자산이 죽고, 죽었으니 호출이
> 지워진** 것이다. 양쪽 레포가 부르는 공용 엔진이므로 플러그인이 나르는 게 맞다.
> (같이 있던 `touch_log.py` 는 **부르는 데가 없어** 승격하지 않았다 — 죽은 것을 공용으로
> 올리면 다음 사람이 살아 있는 줄 안다. ⚠️정확히는 *전역* `settings.json` 템플릿에만
> 남아 있고 **라이브 설정엔 `hooks` 키 자체가 없어** 08-09 이후 안 돈다. 소비자인
> `SENTINEL_SESSIONS` 도 두 레포 다 안 켜서, 지금 세션교차 판정은 꺼져 있는 상태다.)

## guardrail.py

PreToolUse[Bash|PowerShell] — 위험한 명령을 `deny`(금지) / `ask`(확인 강제)로 가른다.
**판정 로직 + 두 레포가 같이 지는 위험**이 여기 있고, 레포 고유 규칙은 shim 에 있다.

```python
engine = runpy.run_path(ENGINE, run_name="guardrail_engine")
RULES = REPO_DENY + engine["deny_common"](migration_hint="…") \
      + REPO_ASK  + engine["ask_common"]()
```

⚠️★★★ **순서가 곧 판정이다**(위→아래 첫 매치). shim 은 **deny 를 전부 앞에** 이어붙인다 —
안 그러면 `DB_ALLOW_WRITE=1 python manage.py migrate` 같은 게 ask 로 새 나간다.
★`check(RULES, REPO_CASES)` 는 **공용 케이스 57종을 반드시 같이 돌린다** — 레포가 순서를
잘못 이어붙여 공용 보호가 죽으면 **그 레포의 selftest 에서** 빨개진다.

self-test: `python ~/claude/gg-harness/hooks/guardrail.py --selftest` (공용 57 cases)

⚠️★★★ **DDL 규칙만 문맥을 본다** (2026-08-22). 그 전엔 명령 문자열 **어디에든**
DDL 단어가 있으면 막아서, DB 를 전혀 안 건드리는 작업을 하루에 네 번 막았다 —
alembic 마이그레이션 **파일** 작성(가드가 자기가 권하는 행동을 막았다) · 훅 자신을
`grep` · `gh pr --body` · 파일 작성 재시도. 지금은 `_ddl_gate` 가 **DB 에 아무것도 안
보내는 게 확실한 문맥만 도려낸 뒤** 검사한다 — 검색(grep·rg·ack·findstr·Select-String) ·
`git commit` · `gh pr|issue|…` · **파일로** 리다이렉트되는 heredoc 넷뿐이다.
⛔"DB 클라이언트가 있을 때만 막는다"로 좁히지 마라 — 파이썬으로 커넥션에 DDL 을 던지는
진짜 위험을 놓친다. `psql <<EOF`·`python <<EOF`·`cat <<EOF | psql` 은 계속 막힌다.
도려내기는 **DDL 규칙에만** 걸린다 — 시크릿·`git add -A`·`rm -rf` 는 원본 명령 전체를 본다.
★`decide()` 의 `pat` 은 정규식 문자열 **또는 판정 함수**(`cmd -> bool`)를 받는다.

> **왜 갈랐나 (2026-08-13):** 쿠팡 95줄 / 북마트 199줄이 **`decide()`·`main()` 은 글자까지
> 같은데 규칙만 갈려** 있었다. 그래서 **한쪽이 겪은 사고를 반대편이 그대로 안고 있었다.**
> 북마트만 알던 것 셋을 쿠팡이 못 받고 있었다 — 명령줄 인라인 시크릿(`sk-…` 를 승인하면
> `settings.local.json` allow 에 **평문**으로 박힌다) · `git rm --pathspec-from-file`
> (대상이 안 보이는 일괄삭제) · `git checkout/restore .`. 반대로 쿠팡만 알던
> `git add .env` 를 북마트가 못 받고 있었다.
> ⚠️ `deny` 보다 `ask` 를 넉넉히 쓴다 — **오탐 한 번이면 사람이 가드를 통째로 끈다.**

## stale_worktrees.py

SessionStart 보조 — main 에서 너무 멀어진 워크트리를 **알린다**(지우지 않는다).

환경변수 (shim 이 설정):
- `WORKTREE_BEHIND_LIMIT` — 이만큼 뒤처지면 폐기물로 본다 (기본 100 ≈ 이틀치)
- `WORKTREE_REPORT_MAX` — 화면에 띄울 최대 개수 (기본 5)
- `WORKTREE_BASE` — 비교 기준 (기본 `origin/main`)

self-test: `python ~/claude/gg-harness/hooks/stale_worktrees.py --selftest` (9 cases · git 없이 돈다)
직접 보기: `python ~/claude/gg-harness/hooks/stale_worktrees.py <레포경로>`

> **왜 나이가 아니라 커밋 수인가:** main 이 하루 50~72커밋으로 움직인다. 실측 대응은
> 1일≈34~69 · 2일≈92~124 · 4일≈195 · **6일=416커밋**. 416커밋 뒤처진 워크트리에서
> 다시 시작하는 것보다 새로 따는 게 언제나 싸다.
>
> **왜 생겼나 (2026-08-13):** 쿠팡에 워크트리 22개가 쌓였는데 `wt.ps1 prune` 은 정리 대상 0을
> 반환했다 — dirty 미커밋이 대부분 **하네스 자신의 phase 산출물**이라 안전가드에 전부 걸린 것이다.
> **도구는 멀쩡했고 아무도 안 봤을 뿐**이라, 발견을 사람에서 훅으로 옮겼다. 같은 날 북마트도
> 8개가 쌓여 있었는데 거긴 경고 자체가 없었다 — 그래서 공용 엔진이다.
> ⚠️ 파싱을 순수 함수로 갈라놨다(`parse_worktrees`·`parse_refs`·`select_stale`·`format_lines`) —
> git 없이 selftest 가 돈다. ⚠️`--porcelain` 을 쓰는 건 **한글 경로를 escape 하지 않아서**다.

## memory_link.py

SessionStart — 프로젝트 메모리(`~/.claude/projects/<슬러그>/memory`)를 Drive 공용 폴더로 잇는다.

환경변수 (shim 이 설정):
- `MEMORY_DRIVE_NAME` — Drive 쪽 폴더 이름 (예: `coupang-v2-memory`). **없으면 아무것도 안 한다**
- `MEMORY_DRIVE_ROOT` — 공용 루트 (기본 `G:\내 드라이브\claude-sync`)

self-test: `python ~/claude/gg-harness/hooks/memory_link.py --selftest` (8 cases)

> **왜 생겼나 (2026-08-13):** 슬러그는 **작업 폴더 절대경로**에서 나온다. 그래서 레포를
> 옮기면 슬러그가 바뀌고 새 자리에 **빈 memory 폴더**가 생긴다 — 그날부터 그 레포
> 세션은 메모리를 0개로 보는데 **에러가 안 난다.** 북마트가 `Desktop\bookmart` →
> `Desktop\북마트\bookmart` 로 옮긴 08-10 이후 **사흘간 447건을 못 보고 돌았다.**
> 이걸 만들던 전역 훅은 라이브 `settings.json` 에서 사라진 지 오래였고 아무도 몰랐다.
> 그래서 배선을 **레포 안**(`.claude/settings.json` + shim)으로 내렸다 — 레포가 옮겨가도
> 워크트리를 따도 배선이 따라온다.
>
> ⚠️ **내용이 든 실폴더는 절대 안 건드린다**(경고만). 지우고 잇는 순간 그 레포가
> 로컬에만 쌓아둔 메모리가 사라진다. 빈 폴더일 때만 링크로 바꾼다.
> ⚠️ 옛 전역 훅은 `if(Test-Path $m){exit}` 라 **빈 폴더가 있으면 영영 안 이었다** —
> 링크가 끊긴 바로 그 상태를 통과시키는 조건이었다.
