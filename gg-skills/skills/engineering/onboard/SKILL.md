---
name: onboard
description: 새 PC나 새 프로젝트에서 개발 환경이 준비됐는지 한 번에 점검하고 빠진 것을 안내한다. PC 도구(git·gh·claude·python), gg-tools 플러그인, 위험 명령 차단 엔진, 프로젝트 틀(CLAUDE.md·docs/PRD.md), 위키(ingest 대기), GitHub 저장소 접근을 대상 목록(sources.yaml) 기준으로 확인한다. "온보딩", "onboard", "새 PC 세팅 확인", "환경 점검", "프로젝트 시작 준비됐어?" 같은 요청에 쓴다.
---

# onboard — 개발 환경 온보딩 점검

**읽기 전용 점검이 기본이다.** 설치·수정·삭제는 결과를 보여 주고 **사용자가 승인한 뒤에만** 한다. 로그인(`gh auth login`, `claude`)·계정 생성·비밀번호·키 입력은 대신하지 않고 사용자가 직접 하게 안내한다.

이 스킬의 구성(단일 기준 + 스크립트):
- `config/sources.example.yaml` — 점검 대상 목록의 예시. 실제 목록은 `~/.claude/onboard/sources.yaml`(개인 경로가 들어가므로 공개 저장소에 두지 않는다)
- `scripts/check_setup.py` — 점검 스크립트(표준 라이브러리만, 읽기 전용)

## 절차

1. **점검 실행.** 이 스킬의 base directory에서:
   ```
   python scripts/check_setup.py
   ```
   `~/.claude/onboard/sources.yaml`이 없으면 PC 점검만 하고 "대상 목록 없음"이 표시된다.
2. **대상 목록이 없으면 만든다.** 사용자에게 한 번에 묻는다: 내 로컬 프로젝트 폴더, 접근해야 할 GitHub 저장소, 위키 폴더, 위키 밖 정본 문서 폴더. 답으로 `~/.claude/onboard/sources.yaml`을 `config/sources.example.yaml` 형식으로 쓰고(폴더가 없으면 만든다) 1번을 다시 실행한다.
3. **결과를 표로 보여 준다.** 상태는 `OK` / `확인`(문제는 아니지만 볼 것) / `없음`(해야 할 것). 한 줄 총평을 앞에 둔다.
4. **빠진 것마다 해결 방법을 한 줄로 제안한다.** 아래 표를 따른다. 실행은 승인 후에.

| 상태 | 해결 |
|---|---|
| git·gh·claude·python 없음 | `docs/guides/00-new-pc-setup.md`의 winget 명령. 설치 뒤 새 PowerShell 창 |
| GitHub 로그인 안 됨 | 사용자가 직접 `gh auth login` |
| gg-tools 클론 없음 | `gh repo clone gggmlduswjs/gg-tools ~/claude` |
| 플러그인 미설치 | `pwsh ~/claude/bootstrap.ps1` (여러 번 실행해도 안전, `-DryRun`으로 미리 보기) |
| 차단 엔진 실패 | gg-tools 위치가 `~/claude`인지 확인 |
| 프로젝트에 CLAUDE.md·docs/PRD.md 없음 | harness 틀(`ai-dev-harness`)로 만든 프로젝트가 아니다. 새 프로젝트면 `docs/guides/0-start-project.md`, 기존 프로젝트면 `docs/ADOPTION.md` |
| CLAUDE.md 200줄 초과 | 줄이거나 `docs/`로 링크 |
| 위키 ingest 대기 | 위키 폴더에서 "위키에 넣어"(`wiki-ingest`) |
| 위키 폴더 없음 | `gh repo clone <내 위키 저장소> ~/second-brain` 또는 `wiki-template`으로 새로 생성 |
| 저장소 접근 불가 | 이름·로그인·권한 확인 |

5. **마무리.** 모두 `OK`면 "준비됨"과 함께 다음 할 일을 한 줄로 안내한다: 새 프로젝트면 PRD 작성(`0-start-project.md`), 기존 프로젝트면 하루 루프(`2-daily-loop-and-second-brain.md`), 어떤 스킬을 언제 쓸지는 `3-when-to-use-skills.md`.

## 하지 않는 것

- 승인 없이 설치·수정·삭제·clone
- 로그인·키·비밀번호 입력, 계정 생성
- 목록에 없는 폴더를 뒤지거나 개인 파일 내용을 읽는 것(존재 여부와 위 표의 항목만 본다)
- 시맨틱 인덱스·그래프 DB 구축(1인 규모에는 과함. 대상이 수십 개 저장소로 커지면 별도 설계)
