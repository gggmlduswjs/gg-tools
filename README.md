# gg-harness

Claude Code **marketplace + plugin** 레포.
[agentic-eng-plugin](https://github.com/jha0313/agentic-eng-plugin)과 같이 루트는 마켓플레이스만, 플러그인 본체는 하위 폴더에 둔다.

```
claude/                          ← marketplace repo (gggmlduswjs/claude)
├── .claude-plugin/marketplace.json
├── README.md
└── gg-harness/                  ← plugin package
    ├── .claude-plugin/plugin.json
    ├── commands/                ← /harness /review /wiki-*
    ├── skills/                  ← 17 skills
    └── hooks/tdd_guard.py       ← TDD 엔진 (레포 shim이 ~/claude/gg-harness/hooks 를 호출)
```

## 설치

```text
/plugin marketplace add gggmlduswjs/claude
/plugin install gg-harness@gg-harness
```

이미 설치돼 있으면:

```text
/plugin marketplace update gg-harness
/plugin update gg-harness@gg-harness
```

로컬 클론(TDD 엔진·개발용):

```powershell
gh repo clone gggmlduswjs/claude ~/claude
```

## 일상 워크플로 (한 사이클)

```
dev cp <이름>       시작 — 워크트리 만들고 claude 를 띄운다 (이름 안 주면 물어본다)
   ↓                이 이름이 워크트리 = 브랜치 = PR 이름
계획                plan 모드로 합의 → .dev/plans/{be,fe,arch}/*_plan.md
   ↓
/harness <작업>     계획을 phase/step 으로 (승인 전엔 파일을 안 만든다)
python .dev/harness/execute.py <작업> --no-branch
   ↓                끝나면 상위 계획의 「남은 N건」을 찍는다
dev harvest         커밋 → rebase → push → PR → 머지 → 자동배포
   ↓                담기 전에 파일 목록을 보여주고 한 번 세운다
터미널 그냥 끄기      워크트리 정리는 다음 `dev cp` 가 한다
```

`dev cp` 는 **폴더를 복사하지 않는다** — git worktree 다. 본체와 커밋 이력을 공유하는 또 하나의 작업 자리를 연다.

```
Coupang_v2/                  본체(main) — 여기서 작업하지 않는다
  .git/  .venv/              진짜 저장소 + 파이썬 환경 (한 벌뿐)
Coupang_v2-wt/<이름>/         dev cp 가 만드는 자리
  .git                       파일 한 줄 → gitdir: ../Coupang_v2/.git/worktrees/<이름>
  .env                       유일하게 복사되는 것
  .dev/ src/ docs/           origin/main 시점의 파일 (.venv 는 없다 — 본체 걸 쓴다)
    └ plans/{be,fe,arch}/<이름>_plan.md      ← 계획이 여기 앉는다
    └ harness/phases/<이름>/step*.md         ← /harness 가 여기에 쪼갠다
    └ _archive/harness_phases/               ← 끝나면 자동으로 여기로 빠진다
```

| 명령 | 하는 일 |
|---|---|
| `dev cp <이름>` / `dev bm <이름>` | 워크트리 생성 + claude 시작. 이름 생략 시 물어본다(엔터=시각 도장) |
| `dev r` | 열린 세션 목록에서 골라 이어하기 |
| `dev harvest ["메시지"]` | 커밋→rebase→push→PR→머지→배포. 실패하면 즉시 멈추고 아무것도 안 민다 |
| `dev clean [bm\|cp]` | 머지된 워크트리 정리(`dev cp` 가 시작할 때 자동으로 돈다) |

⛔ `cd` + `claude` 로 직접 시작하지 마라 — `dev cp` 안의 자동 정리를 통째로 건너뛴다.
⚠️ `Phase completed` 는 끝이 아니다. 남은 건수가 0 이 되면 계획 문서를 `> 상태: 완료` 로 **사람이** 닫는다.

상세 규칙·함정(worktree 정리 기준·codex 샌드박스·공용 자산 위치)은 **[운영_워크플로우.md](운영_워크플로우.md)** 가 정본이다.

## 역할 분리

| 층 | 자리 | 예 |
|---|---|---|
| 개인 기본 | `~/.claude/` | 개인 CLAUDE.md |
| 회사 공용 | 이 플러그인 `gg-harness/` | `/harness` `/review` wiki-* · grilling · tdd 엔진 |
| 프로젝트 | 각 레포 | `CLAUDE.md`, `.dev/harness/execute.py`, 도메인 훅/스킬 |

## Slash commands

| 커맨드 | 하는 일 |
|---|---|
| `/harness <작업>` | phase/step 설계. 실행은 `python .dev/harness/execute.py <task>`. 끝나면 상위 계획의 남은 건수까지 보고한다 |
| `/review [범위]` | 문서·운영 안전 읽기 전용 리뷰 |
| `/wiki-ingest` | raw → 세컨드 브레인 위키 통합 |
| `/wiki-lint` | 위키 건강검진 |
| `/wiki-query` | 위키에 질문·인용 답변 |

`wiki-*`는 레포 루트에 `WIKI_SCHEMA.md` + `wiki/`가 있는 **위키 볼트 안**에서 쓴다(북마트/쿠팡 업무 레포가 아님). LMN·에이전틱 엔지니어링 세컨드 브레인 볼트가 그 자리.

## 포함하지 않는 것

- 전역 `CLAUDE.md` / `settings.json` / PowerShell `ai.ps1` 엔진
- 프로젝트별 secret · MCP · 운영 DB ref
- 실행기 `execute.py` (각 레포 `.dev/harness/`)

## 출처

- wiki-ingest / wiki-lint / wiki-query: [jha0313/agentic-eng-plugin](https://github.com/jha0313/agentic-eng-plugin) 구조를 맞춰 들여옴
- karpathy-guidelines: [Andrej Karpathy skills](https://github.com/multica-ai/andrej-karpathy-skills)

## 개발 규칙

1. 스킬 추가/삭제는 `gg-harness/skills/README.md`도 같이 갱신
2. PC별 배선 파일은 루트에 만들지 않음
3. 변경 후 commit/push → `/plugin update gg-harness@gg-harness`
