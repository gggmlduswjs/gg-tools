# gg-tools

여러 프로젝트에서 공통으로 사용하는 **Claude Code 전문 플러그인·공통 Hook 엔진·PC 설치 도구**의 정본이다. 프로젝트 문서 템플릿이나 개발 방법론은 이 저장소에 복제하지 않는다.

## 자산 소유권 — 먼저 여기서 확인

| 자산 | 유일한 관리 위치 | 이 저장소에서 할 일 |
|---|---|---|
| 개발 방법론(TDD·계획·디버깅·검증) | 외부 **Superpowers** 플러그인 | 설치·업데이트 및 프로젝트 연결 |
| 프로젝트 표준·문서 양식 | [ai-dev-harness](https://github.com/gggmlduswjs/ai-dev-harness) | 링크만 제공, 양식/실행기 복제 금지 |
| 공통 전문 스킬·공통 Hook 엔진·Eval 도구 | 이 저장소 `gg-skills/` | 공통 코드와 버전 관리 |
| 개인 PC 설치·PowerShell·전역 설정 | 이 저장소 `bootstrap.ps1`·`install.ps1`·`home/` | 실제 설치 및 경로 확인 |
| 북마트·쿠팡 고유 정책·전용 스킬·Hook shim | 각 제품 레포 | 여기에는 공통 동작만 둔다 |
| 실행 상태·일정·우선순위 | Linear | 중복 진행판을 만들지 않는다 |

> **역할 분리:** `ai-dev-harness`는 새 프로젝트의 템플릿, `gg-tools`는 공통 도구 배포, Superpowers는 개발 방법론이다. 이름이 비슷하다고 파일을 세 곳에 복사하지 않는다.

## 역할

범용 개발 workflow의 정본은 **Superpowers**다.

- brainstorming / planning / worktree / TDD / execution / debugging / verification → Superpowers
- 기존 시스템 현대화, 보안·성능·AI-readiness·위키 → **gg-skills**
- 코드 리뷰는 내장 `/code-review`(범용) + `/review`(프로젝트 축) 두 벌이다 — 2026-09-01 에 `code-review-7p` 를 걷었다
- grilling, domain-modeling, handoff, tdd 등 범용 엔지니어링 스킬 → **mattpocock-skills** (업스트림 정본. gg-skills 가 갖고 있던 사본 2개는 2026-08-30 에 뺐다)
- 집요한 요구사항 인터뷰 → **RobMitt/grill-me-skill**
- 프로젝트 고유 DB/배포/worktree/UI 규칙 → 각 프로젝트의 `CLAUDE.md`, `AGENTS.md`, `.claude/rules/`

```text
Claude Code
├─ Superpowers        # 개발 workflow
├─ gg-skills          # 공용 전문 스킬
├─ grill-me           # 요구사항 인터뷰
└─ project rules      # Bookmart/Coupang 고유 규칙
```

## 한 번에 설치/업데이트

Claude Code가 설치된 PC에서는 이 repo를 clone/pull한 뒤 아래 한 줄만 실행한다.

```powershell
pwsh ./bootstrap.ps1
```

`bootstrap.ps1`은 멱등으로 다음을 처리한다.

1. `superpowers@claude-plugins-official` 설치 또는 업데이트
2. `gg-tools` marketplace 등록/갱신 후 `gg-skills@gg-tools` 설치 또는 업데이트
3. `mattpocock-skills@mattpocock` 설치 또는 업데이트
4. `RobMitt/grill-me-skill`의 최신 `SKILL.md`를 `~/.claude/skills/grill-me/`에 동기화
5. 기존 `install.ps1`을 실행해 PowerShell/profile/Claude 개인 설정 등 PC 배선

옵션:

```powershell
pwsh ./bootstrap.ps1 -Force          # PC별 복사 설정도 덮어쓰기
pwsh ./bootstrap.ps1 -InstallForge   # 보류 중인 forge 스킬 배선 포함
pwsh ./bootstrap.ps1 -SkipPcWiring   # plugin/skill만 갱신
```

열려 있는 Claude Code 세션은 실행 후 `/reload-plugins`를 하거나 새 세션을 연다.

## 새 PC

GitHub 레포의 현재 이름은 `gg-tools`지만 **로컬 클론 경로는 `~/claude`**로 유지한다. 두 프로젝트의 Hook shim이 이 경로에서 공통 엔진을 찾기 때문이다.

```powershell
gh repo clone gggmlduswjs/gg-tools ~/claude
pwsh ~/claude/bootstrap.ps1
```

기존 PC에서 이미 `~/claude`에 클론했다면 새로 복제하지 말고 해당 위치에서 pull한 후 `bootstrap.ps1`을 실행한다. 이전 GitHub 레포명 `claude`는 호환용 이력일 뿐 신규 설치 지침으로 사용하지 않는다.

## Plugin 구조

```text
gg-tools/
├─ .claude-plugin/marketplace.json   # marketplace name: gg-tools
├─ bootstrap.ps1                     # 한 번에 설치/업데이트
├─ install.ps1                       # PC 배선
├─ gg-skills/                        # 현재 공용 전문 plugin
│  ├─ .claude-plugin/plugin.json
│  ├─ commands/
│  ├─ hooks/
│  └─ skills/
```

`gg-skills`는 명시적 version을 고정하지 않는다. Git-hosted marketplace의 commit SHA를 버전으로 사용하므로 새 변경이 merge되면 `bootstrap.ps1`의 `claude plugin update`가 최신 커밋을 받는다.

## 설치 확인과 알려진 의존성

- `bootstrap.ps1`은 **Claude Code 플러그인과 PC 배선**을 처리한다. Codex 플러그인은 별도로 설치해야 한다.
- 프로젝트별 Hook이 호출하는 공통 엔진은 `~/claude/gg-skills/hooks/`의 추적 파일이다. **플러그인 설치 성공만으로 해당 경로·Hook 실행을 검증한 것으로 보지 않는다.** 새 PC에서는 파일 존재와 양쪽 프로젝트 `python .claude/hooks/guardrail.py --selftest`를 확인한다.
- `gg-skills:product-spec-kit`은 외부 `artifact-design` 스킬을 호출한다. 현재 `bootstrap.ps1`이 해당 스킬을 자동 설치하는 경로는 없으므로, 이 기능을 사용하려면 설치·호출 가능 여부를 별도 확인한다. **미검증 상태를 설치 완료라고 보고하지 않는다.**
- `grill-me`(RobMitt)와 `mattpocock-skills`의 인터뷰 관련 스킬은 서로 다른 출처다. 당장 자동 통합하지 않고 실제 호출·용도 중복 여부를 확인한 후 선택한다.
- `운영_워크플로우.md`는 2026-08 당시 기록으로 남긴다. **현재 실행 계약은 각 프로젝트의 `CLAUDE.md`와 Linear**가 우선한다.

## Codex

Claude Code의 bootstrap이 Codex plugin까지 대신 설치하지는 않는다. Superpowers는 각 harness별 설치가 필요하므로 Codex에서는 Codex plugin marketplace를 통해 별도로 설치한다. 다만 Claude가 만든 `.dev/research` / `.dev/plans` 정본은 같은 Git repo를 통해 Codex와 공유한다.

## Legacy

기존 `gg-harness` plugin, `/harness` command, 자체 phase/step 실행기, 자체 TDD workflow(`tdd_guard.py`)는
**2026-09-01 에 삭제했다.** 범용 workflow 정본은 Superpowers 다 — 계획은 `writing-plans`,
실행은 `subagent-driven-development`, TDD 는 `test-driven-development`, 완료 검증은
`verification-before-completion`. `gg-skills` 는 Superpowers 가 안 다루는 축(보안·성능·관측성·
진단·위키·기존시스템 현대화)만 맡는다.
