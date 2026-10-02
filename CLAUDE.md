# gg-tools 작업 규칙

이 저장소는 Claude Code 플러그인 마켓플레이스(`gg-tools`)다. 플러그인은 `gg-skills` 하나.

## 폴더

- `gg-skills/skills/<분류>/<스킬>/SKILL.md` — 분류: `engineering` · `diagnostics` (플러그인에 실림), `misc` · `in-progress` · `deprecated` (실리지 않음)
- `gg-skills/.claude-plugin/plugin.json` — `skills` 배열에 적힌 스킬만 설치된다
- `gg-skills/hooks/` — 위험 명령 차단 등 hook 엔진 (프로젝트 shim이 `~/claude/gg-skills/hooks/`를 부른다)
- `plugins.json` — `bootstrap.ps1`이 설치할 목록. 도구 추가·삭제는 여기만
- `scripts/` — 점검 스크립트

## 스킬을 추가·이동·삭제할 때

1. `SKILL.md`(대문자)를 두고 description에 사용자가 쓸 법한 말을 넣는다.
2. `plugin.json`의 `skills` 배열과 `gg-skills/skills/README.md` 표에 등록한다. 이름으로 대조하며, 어긋나면 pre-commit이 막는다.
3. `ask-gg` 라우터 표를 갱신한다.
4. `claude plugin validate gg-skills`를 통과시킨다.

## 지키는 것

- 개인 경로·키·회사 정보를 넣지 않는다. 이 저장소는 공개다.
- 외부 저장소의 파일을 복사해 넣지 않는다. `plugins.json`으로 설치한다.
- 개인 PC 설정은 비공개 `gg-dotfiles`에 둔다.
- 변경 후 `pwsh ./bootstrap.ps1 -DryRun`과 `python gg-skills/hooks/guardrail.py --selftest`를 돌린다.
