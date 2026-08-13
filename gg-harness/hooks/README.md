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
