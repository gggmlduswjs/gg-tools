# gg-tools

여러 프로젝트에서 공통으로 쓰는 Claude Code 개발 보완 도구와 PC 배선을 관리한다.

## 역할

범용 개발 workflow의 정본은 **Superpowers**다.

- brainstorming / planning / worktree / TDD / execution / debugging / verification → Superpowers
- 기존 시스템 현대화, domain-modeling, code-review-7p, 보안·성능·AI-readiness·위키 → **gg-skills**
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
3. `RobMitt/grill-me-skill`의 최신 `SKILL.md`를 `~/.claude/skills/grill-me/`에 동기화
4. 기존 `install.ps1`을 실행해 PowerShell/profile/Claude 개인 설정 등 PC 배선

옵션:

```powershell
pwsh ./bootstrap.ps1 -Force          # PC별 복사 설정도 덮어쓰기
pwsh ./bootstrap.ps1 -InstallForge   # 보류 중인 forge 스킬 배선 포함
pwsh ./bootstrap.ps1 -SkipPcWiring   # plugin/skill만 갱신
```

열려 있는 Claude Code 세션은 실행 후 `/reload-plugins`를 하거나 새 세션을 연다.

## 새 PC

현재 repo 이름이 `claude`인 동안:

```powershell
gh repo clone gggmlduswjs/claude ~/gg-tools
pwsh ~/gg-tools/bootstrap.ps1
```

repo를 `gg-tools`로 rename한 뒤에는:

```powershell
gh repo clone gggmlduswjs/gg-tools ~/gg-tools
pwsh ~/gg-tools/bootstrap.ps1
```

bootstrap은 rename 과도기를 위해 `gggmlduswjs/gg-tools`를 먼저 시도하고, 없으면 `gggmlduswjs/claude`를 fallback으로 사용한다.

## Plugin 구조

```text
gg-tools/
├─ .claude-plugin/marketplace.json   # marketplace name: gg-tools
├─ bootstrap.ps1                     # 한 번에 설치/업데이트
├─ install.ps1                       # PC 배선
├─ gg-skills/                        # 현재 공용 전문 plugin
│  ├─ .claude-plugin/plugin.json
│  ├─ commands/
│  └─ skills/
└─ gg-harness/                       # deprecated 호환본; 신규 설치 금지
```

`gg-skills`는 명시적 version을 고정하지 않는다. Git-hosted marketplace의 commit SHA를 버전으로 사용하므로 새 변경이 merge되면 `bootstrap.ps1`의 `claude plugin update`가 최신 커밋을 받는다.

## Codex

Claude Code의 bootstrap이 Codex plugin까지 대신 설치하지는 않는다. Superpowers는 각 harness별 설치가 필요하므로 Codex에서는 Codex plugin marketplace를 통해 별도로 설치한다. 다만 Claude가 만든 `.dev/research` / `.dev/plans` 정본은 같은 Git repo를 통해 Codex와 공유한다.

## Legacy

기존 `gg-harness`, `/harness`, 자체 phase/step 실행기, 자체 TDD workflow는 deprecated다. 프로젝트 참조가 모두 제거된 뒤 별도 cleanup으로 삭제한다.
