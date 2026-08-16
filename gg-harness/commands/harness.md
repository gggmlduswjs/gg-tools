---
description: 작업을 self-contained step으로 설계하고 승인 후 순차 실행
---

`$ARGUMENTS` 작업을 이 레포 하네스 phase로 준비한다.

1. `CLAUDE.md`, `AGENTS.md`, 관련 `.dev/research/`·`.dev/plans/`와 기존 코드를 먼저 읽는다.
2. 목표, 수정 파일, 재사용 경로, 금지사항, 실행 가능한 Acceptance Criteria를 사용자와 합의한다.
3. 승인 전에는 코드와 phase 파일을 만들지 않는다.
4. 승인 후 `.dev/harness/phases/<task>/index.json`과 `step<N>.md`를 만든다.
5. step 하나는 한 흐름만 담당하고 독립 세션에서도 이해되게 작성한다.
6. 실행은 격리된 깨끗한 작업 브랜치에서만 아래 명령으로 한다.
   워크트리 위치 정본: bookmart=`pwsh _scripts/bmwt.ps1 start <이름>` → `../bookmart-wt/<이름>`,
   Coupang=`.\wt.ps1 new <이름>` → `../Coupang_v2-wt/<이름>`.
   ⛔ `git worktree add` 직접 호출·`.claude/worktrees/`에 작업 워크트리 생성 금지.
   이미 `*-wt` 안이면 `--no-branch`.

```powershell
python .dev/harness/execute.py <task> --no-branch --dry-run
python .dev/harness/execute.py <task> --no-branch
```

7. ⛔ **`Phase completed` 로 세션을 끝내지 않는다.** phase 는 상위 계획의 한 조각일 뿐이다.
   마지막 step 이 끝나면 phase `index.json` 의 `source_plan` 을 열어 **① 이 phase 로 닫힌 항목을
   진행판에 체크하고 ② 남은 항목 수를 보고하고 ③ 다음 phase 후보를 사용자에게 제시**한다.
   완료 기준은 「step 을 다 돌았다」가 아니라 **「상위 계획에 남은 건수 0」**이다.
   `source_plan` 이 비어 있으면 그것부터 채운다 — 상위를 모르는 phase 는 끝나는 순간 맥락이 증발한다.

`execute.py`는 각 레포 `.dev/harness/`에 둔다. commit, push, worktree 생성, 운영 DB 쓰기를 하지 않는다.
