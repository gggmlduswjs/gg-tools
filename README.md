# gg-harness

Claude Code plugin source. 이 레포는 이제 **플러그인 자산만** 담는다.

## 포함하는 것

- `.claude-plugin/` — plugin/marketplace manifest
- `skills/` — 재사용 가능한 스킬
- `commands/` — Claude slash command
- `README.md` — 설치와 운영 기준

## 포함하지 않는 것

다음은 PC별 개인 설정이라 이 레포와 GitHub plugin 패키지에서 뺐다.

- `install.ps1`
- `home/CLAUDE.md`, `home/settings.json`, statusline 파일
- PowerShell profile/dev launcher/worktree helper
- 전역 hooks, token/cost/touch log scripts
- 프로젝트별 `.vscode`/git hook 배선
- 새 PC 체크리스트와 로컬 운영 메모

필요하면 로컬 PC에만 따로 둔다. plugin repo에 다시 넣지 않는다.

## 설치

Claude Code 안에서 한 줄씩 실행한다.

```text
/plugin marketplace add gggmlduswjs/claude
/plugin install gg-harness@gg-harness
```

이미 설치되어 있으면:

```text
/plugin update gg-harness@gg-harness
```

## 역할 분리

- 개인 기본값: `C:\Users\user\.claude\CLAUDE.md`
- 프로젝트 규칙: 각 프로젝트의 `CLAUDE.md` / `AGENTS.md`
- 재사용 자산: 이 레포의 `skills/`와 `commands/`
- worktree/harness/PowerShell 런처: 사용자가 명시했을 때만 쓰는 로컬 고급 도구

## 개발 규칙

1. 스킬을 추가하거나 지우면 `skills/README.md`도 같이 갱신한다.
2. plugin에 넣을 수 없는 PC별 배선 파일은 루트에 만들지 않는다. `.gitignore`의 local machine wiring 목록에 둔다.
3. 변경 후 commit/push하고 Claude Code에서 `/plugin update gg-harness@gg-harness`를 실행한다.