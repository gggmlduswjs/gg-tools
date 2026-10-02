# gg-tools

Claude Code용 **공용 전문 스킬(플러그인)과 공통 Hook 엔진**을 모아 둔 저장소입니다. 프로젝트 문서 템플릿이나 개발 방법론은 이 저장소에 복제하지 않습니다.

## 무엇이 어디에 있나

| 자산 | 위치 |
|---|---|
| 개발 방법론(TDD·계획·디버깅·검증) | 외부 **Superpowers** 플러그인 (이 저장소는 설치만 돕는다) |
| 프로젝트 표준·문서 양식 | [ai-dev-harness](https://github.com/gggmlduswjs/ai-dev-harness) |
| 공용 전문 스킬·Hook 엔진·Eval 도구 | 이 저장소 `gg-skills/` |
| 프로젝트 고유 정책·전용 스킬·Hook shim | 각 프로젝트 저장소 (여기에는 공통 동작만 둔다) |
| 실행 상태·일정·우선순위 | 이슈 트래커 (여기에 진행판을 만들지 않는다) |

> `ai-dev-harness`는 새 프로젝트의 **틀**, `gg-tools`는 **도구 배포**, Superpowers는 **개발 방법론**입니다. 파일을 세 곳에 복사하지 않습니다.

## 설치

Claude Code가 설치된 PC에서 이 저장소를 받고 한 줄을 실행합니다.

```powershell
gh repo clone gggmlduswjs/gg-tools ~/claude
pwsh ~/claude/bootstrap.ps1
```

**로컬 클론 경로는 `~/claude`로 유지합니다.** 프로젝트의 Hook shim이 이 경로(`~/claude/gg-skills/hooks/`)에서 공통 엔진을 찾습니다.

`bootstrap.ps1`은 여러 번 실행해도 안전하며(멱등) **`plugins.json`에 적힌 것**을 설치합니다. 도구를 더하거나 빼려면 그 파일만 고칩니다. `-DryRun`을 붙이면 아무것도 바꾸지 않고 실행할 명령만 보여 줍니다.

| 종류 | 내용 |
|---|---|
| 핵심 플러그인 | `superpowers`, `gg-skills`, `mattpocock-skills` (실패하면 중단) |
| 보완 플러그인 | `ponytail`, `ui-ux-pro-max`, `claude-mem`, `task-observer`, `codex`, `headroom` |
| 보안 플러그인 | Trail of Bits 9종 (`differential-review`, `insecure-defaults`, `static-analysis` 등) |
| 단일 스킬 | `grill-me`, `refactoring-ui` |
| 저장소 | 세컨드 브레인 `second-brain`을 `~/second-brain`에 받음 (비공개, `gh auth login` 필요) |
| npm 도구 | `lighthouse` (Node.js 필요) |
| 선택 설치 | Cybersecurity Skills 818개 (설명이 컨텍스트에 많이 올라가 기본 제외) |

보완·보안 플러그인과 단일 스킬은 실패해도 경고만 남기고 계속합니다. 내장 `/security-review`는 설치 없이 바로 씁니다.

실행 후 열려 있는 Claude Code 세션은 `/reload-plugins`를 하거나 새 세션을 엽니다. 플러그인만 필요하면 Claude Code 안에서 `/plugin marketplace add gggmlduswjs/gg-tools` 후 `/plugin install gg-skills@gg-tools`로도 설치됩니다.

## 구조

```text
gg-tools/
├─ .claude-plugin/marketplace.json   # marketplace name: gg-tools
├─ bootstrap.ps1                     # 한 번에 설치/업데이트
├─ plugins.json                      # 설치 목록 (도구 추가·삭제는 여기만)
├─ CLAUDE.md                         # 이 저장소 작업 규칙
├─ gg-skills/                        # 공용 전문 plugin
│  ├─ .claude-plugin/plugin.json
│  ├─ commands/
│  ├─ hooks/                         # 공통 Hook 엔진 (프로젝트 shim이 호출)
│  ├─ evals/
│  └─ skills/
├─ powershell/wt-engine.ps1          # worktree 공통 엔진
└─ scripts/                          # 보조 스크립트
```

`gg-skills`는 명시적 version을 고정하지 않습니다. Git-hosted marketplace의 commit SHA를 버전으로 쓰므로, 변경이 merge되면 `claude plugin update`가 최신 커밋을 받습니다.

## 알려진 의존성

- `bootstrap.ps1`은 **Claude Code용**만 처리합니다(Claude 안에서 Codex를 부르는 `codex` 플러그인 포함). Codex 앱 자체의 플러그인은 별도로 설치합니다.
- 프로젝트 Hook이 호출하는 공통 엔진은 `~/claude/gg-skills/hooks/`의 추적 파일입니다. **플러그인 설치 성공만으로 Hook 동작을 검증한 것으로 보지 않습니다.** 새 PC에서는 프로젝트의 `python .claude/hooks/guardrail.py --selftest`로 확인합니다.
- `gg-skills:product-spec-kit`은 외부 `artifact-design` 스킬을 호출합니다. `bootstrap.ps1`이 그 스킬을 자동 설치하지 않으므로, 이 기능을 쓰려면 설치·호출 가능 여부를 따로 확인합니다.
- `grill-me`(RobMitt)와 `mattpocock-skills`의 인터뷰 관련 스킬은 출처가 다릅니다. 자동으로 통합하지 않으니 실제 용도가 겹치는지 확인한 뒤 고릅니다.

## Codex

Claude Code의 bootstrap은 Codex 플러그인까지 설치하지 않습니다. Codex에서는 Codex plugin marketplace로 별도 설치합니다. Claude가 만든 `.dev/research`, `.dev/plans` 정본은 같은 Git 저장소를 통해 Codex와 공유합니다.
