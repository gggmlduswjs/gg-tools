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

## 역할 분리

| 층 | 자리 | 예 |
|---|---|---|
| 개인 기본 | `~/.claude/` | 개인 CLAUDE.md |
| 회사 공용 | 이 플러그인 `gg-harness/` | `/harness` `/review` wiki-* · grilling · tdd 엔진 |
| 프로젝트 | 각 레포 | `CLAUDE.md`, `.dev/harness/execute.py`, 도메인 훅/스킬 |

## Slash commands

| 커맨드 | 하는 일 |
|---|---|
| `/harness <작업>` | phase/step 설계. 실행은 `python .dev/harness/execute.py <task>` |
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
