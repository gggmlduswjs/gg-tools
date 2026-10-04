# Codex에서 gg-skills 사용

Claude와 Codex가 기존 13개 `SKILL.md`·scripts·references·assets를 공유한다. `.claude-plugin/plugin.json`이 공용 등록 목록의 정본이고 `.codex-plugin/plugin.json`은 같은 경로를 명시한다. Codex manifest의 명시 목록으로 `misc`·`in-progress`·`deprecated`를 제외한다. 두 목록의 일치는 `python -m unittest discover -s tests`가 검사한다.

## 설치

Codex CLI 0.160.0에서 설치·스킬 검색·hook 목록을 검증했다. 오래된 CLI에 `plugin` 명령이 없으면 업데이트 후 사용한다.

```powershell
# gg-tools 체크아웃에서
pwsh ./bootstrap-codex.ps1 -DryRun
pwsh ./bootstrap-codex.ps1
```

스크립트는 이 체크아웃을 marketplace로 등록하고 gg-skills만 설치한다. Codex marketplace 이름은 `gg-tools`다. 외부 `plugins.json` 목록은 Claude bootstrap 전용이며 이 스크립트는 설치하지 않는다. 이미 등록된 `gg-tools`가 다른 source를 가리키면 CLI 결과를 확인하고 사용할 source를 선택한다. 기존 marketplace를 자동 제거하지 않는다.

Windows에서는 데스크톱 앱의 동봉 Codex 실행 파일을 우선한다(실행 중인 앱의 경로, 없으면 설치된 최신 파일). 없으면 PATH의 CLI를 사용한다. 설치에 사용한 경로를 출력하며 `-CodexExecutable '<실행 파일 경로>'`로 명시할 수도 있다. 검증 PC에서는 npm의 `codex` 명령이 캐시 활성화 단계에서 `os error 5`로 실패했고 앱 동봉 실행 파일로 같은 설정의 설치가 성공했다. 캐시 ACL·관리자 권한·hook trust 설정을 자동 변경하지 않는다. 다시 실패하면 출력된 실행 파일과 실제 오류를 먼저 확인한다.

GitHub의 지원 변경이 들어간 ref에서도 설치할 수 있다:

```powershell
codex plugin marketplace add gggmlduswjs/gg-tools --ref codex/gg-skills-support
codex plugin add gg-skills@gg-tools
codex plugin list --json
```

위 ref는 개발 브랜치다. merge 뒤에는 기본 브랜치를 사용한다. 새 Codex 세션에서 등록 목록을 확인한다. 같은 버전의 캐시를 업데이트할 때도 `codex plugin add gg-skills@gg-tools`를 실행해 설치 결과를 확인한다. Codex 배포 시 manifest version을 올린다. Claude의 commit SHA 기반 업데이트는 그대로 유지한다.

## 호출

자연어로 요청하거나 설치된 목록에서 스킬을 지정한다. 예:

- `gg-skills:ask-gg로 어떤 스킬을 쓸지 알려줘`
- `gg-skills:onboard로 Codex 환경 점검해줘`
- `이 위키를 gg-skills:wiki-query로 찾아줘`
- `gg-skills:wiki-ingest로 이 자료를 정리해줘`
- `gg-skills:wiki-lint로 링크와 스키마 점검해줘`
- `gg-skills:project-review로 이 변경의 프로젝트 규칙을 리뷰해줘`

위키 3개는 같은 원본을 그대로 사용한다. `WIKI_SCHEMA.md`가 있는 위키 경로와 승인된 쓰기 범위를 지정한다. 조회만 하면 페이지·log를 수정하지 않는다. 구현 정본·운영 상태는 프로젝트 문서에서 확인한다.

온보딩은 스킬 디렉터리에서 `python scripts/check_setup.py --runtime codex`로 실행한다. Codex 대상 목록을 우선하고 기존 Claude 목록은 재사용할 수 있다. `--sources`로 명시한 목록이 최우선이다. `--adopt`/`--catalog`의 Claude hook 항목은 기존 현황 조사이며 Codex 활성화 판정은 아니다.

## Hook과 명령의 차이

기존 Claude `/gg-skills:review`는 Codex의 `project-review` 진입점이 [같은 review 계약](../gg-skills/commands/review.md)을 읽는다. Claude의 내장 slash command를 Codex에서 호출하지 않는다.

공용 guardrail·secret 탐지 엔진을 [Codex adapter](../gg-skills/hooks/codex_adapter.py)가 재사용한다. Codex `Bash`와 `apply_patch` 이벤트를 해석하며 patch의 추가 줄만 secret 검사한다. 기존 보호 규칙의 `ask`는 Codex에서 지원되지 않으므로 **deny로 변환한다**. 출력에는 감지한 secret 값이 포함되지 않는다.

설치만으로 hook이 활성화되지 않는다. Codex CLI의 `/hooks`에서 정의를 검토하고 직접 신뢰해야 한다. 전역 권한·hook trust·인증 설정은 installer가 변경하지 않는다. Hook 실행에는 로컬 Python이 필요하다. 실제 세션 검증 전에는 자동 보호가 켜졌다고 보고하지 않는다. 지원되는 로컬 도구 경로의 보조 장치이며 shell 우회·hosted tool·모든 위험 명령을 완전히 차단하는 경계는 아니다.

TDD guard는 기존처럼 기본 꺼짐이다. 프로젝트가 사용하기로 결정한 경우 hook 명령에 `--tdd`를 붙인다. 기존 `TDD_GUARD_DISABLE` 환경변수도 적용된다. 테스트 **파일 존재**만 검사하며 테스트 성공을 보장하지 않는다. 오래된 worktree 조회는 `SessionStart`에서 adapter의 `--stale-worktrees` 모드로 연결할 수 있다. 예시 설정의 `<설치된 plugin root>`는 실제 경로로 바꾸고 `/hooks`에서 신뢰한다:

```json
{
  "hooks": {
    "PreToolUse": [{"matcher": "apply_patch", "hooks": [{"type": "command", "command": "python \"<설치된 plugin root>/hooks/codex_adapter.py\" --tdd"}]}],
    "SessionStart": [{"matcher": "startup|resume", "hooks": [{"type": "command", "command": "python \"<설치된 plugin root>/hooks/codex_adapter.py\" --stale-worktrees"}]}]
  }
}
```

Git `commit_sentinel.py`는 기존 post-commit 배선으로 두 환경에 공통 적용된다. `memory_link.py`는 Claude의 메모리 경로를 연결하는 엔진이므로 Codex에는 자동 연결하지 않는다. 이미 있는 프로젝트 hook과 중복 등록하지 않는다.

## 평가·외부 도구

[평가 실행기](../gg-skills/evals/behavior/README.md)는 `EVAL_PROVIDER=openai`를 지원한다. API 키와 서로 다른 모델을 직접 지정하며 Codex 구독 로그인과 별도다. 유료 live eval은 이 이식 작업에서 실행하지 않는다. API prompt 평가와 실제 Codex 도구/스킬 동작 검증은 구분한다.

Supabase 등 외부 MCP와 Lighthouse 등 측정 도구는 각 스킬의 사전 조건을 따로 갖춰야 한다. 인증이나 project ref를 패키지에 넣지 않는다. Superpowers·mattpocock·외부 `skills_repo`는 현재 환경에 설치된 경우에만 연결하며 이 패키지에서 복사·자동 설치하지 않는다.

공식 형식: [plugin packaging](https://developers.openai.com/plugins/build/plugins), [Codex hooks](https://learn.chatgpt.com/docs/hooks).
