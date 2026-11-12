---
name: onboard
description: 새 PC나 새 프로젝트에서 개발 환경이 준비됐는지 한 번에 점검하고 빠진 것을 안내한다. PC 도구(git·gh·claude·python), gg-tools 플러그인, 위험 명령 차단 엔진, 프로젝트 틀(CLAUDE.md·docs/PRD.md), 위키(ingest 대기), GitHub 저장소 접근을 대상 목록(sources.yaml) 기준으로 확인한다. "온보딩", "onboard", "새 PC 세팅 확인", "환경 점검", "프로젝트 시작 준비됐어?" 같은 요청에 쓴다.
---

# onboard — 개발 환경 온보딩 점검

**읽기 전용 점검이 기본이다.** 설치·수정·삭제는 결과를 보여 주고 **사용자가 승인한 뒤에만** 한다. 로그인(`gh auth login`, `claude`)·계정 생성·비밀번호·키 입력은 대신하지 않고 사용자가 직접 하게 안내한다.

이 스킬의 구성(단일 기준 + 스크립트):
- `config/sources.example.yaml` — 점검 대상 목록의 예시. 실제 목록은 `~/.claude/onboard/sources.yaml`(개인 경로가 들어가므로 공개 저장소에 두지 않는다)
- `config/harness-catalog.json` — 강의 적용 카탈로그(`--catalog` 가 읽는 정책 목록. 포함 기준·필드는 파일 상단 `_doc`)
- `scripts/check_setup.py` — 점검 스크립트(표준 라이브러리만, 읽기 전용)
- `references/adopt-playbook.md`·`references/decision-questionnaire.md` — 기존 프로젝트 도입 절차와 결정 질문서(아래 4-4)

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
| 플러그인 중복 설치(같은 이름·다른 마켓플레이스) | 정본이 아닌 쪽 `claude plugin uninstall <id>` (사용자 승인 후) |
| 차단 엔진 실패 | gg-tools 위치가 `~/claude`인지 확인 |
| 프로젝트에 CLAUDE.md·docs/PRD.md 없음 | harness 틀(`ai-dev-harness`)로 만든 프로젝트가 아니다. 새 프로젝트면 `docs/guides/0-start-project.md`, 기존 프로젝트면 `docs/ADOPTION.md` |
| CLAUDE.md 200줄 초과 | 줄이거나 `docs/`로 링크 |
| 구조 밖 문서 `낡은 후보`·`확인` | 목록을 사용자에게 보이고 정리 여부를 묻는다. `참조됨`은 건드리지 않는다. 이동·삭제는 승인 후 별도 작업 |
| 위키 ingest 대기 | 위키 폴더에서 "위키에 넣어"(`wiki-ingest`) |
| 위키 폴더 없음 | `gh repo clone <내 위키 저장소> ~/second-brain` 또는 `wiki-template`으로 새로 생성 |
| 저장소 접근 불가 | 이름·로그인·권한 확인 |

4-1. **프로젝트 구조 점검(선택).** 낡은 문서를 가려내고 싶을 때만 `python scripts/check_setup.py --structure`(또는 sources.yaml에 `structure_check: true`)를 돌린다. 프로젝트마다 `git ls-files` 기준으로 harness 틀(CLAUDE.md·docs/·.dev/·_brain/) 존재 여부를 보이고, 틀 밖 문서성 파일을 `참조됨`(코드·훅·문서가 경로를 인용 — 이동 금지) / `낡은 후보`(참조 0건·180일 이상 미수정) / `확인`으로 나눠 개수·폴더별 집계·상위 10개를 보여 준다. `--full`은 전체 목록, `--deep`은 후보 2000개 초과 때 참조 검사 상한 해제. 참조는 경로 기준이다: 전체 경로, 또는 상위 폴더 1~2단계를 붙인 부분 경로(추적 파일 중 유일할 때만)가 다른 파일에 인용되면 인정하고, 파일명만 인용된 경우는 그 이름이 유일할 때만 인정한다(index.html·README 같은 중복 이름은 제외). 결과는 로컬 체크아웃(브랜치) 기준이다. **보고만 하고 삭제·이동·수정은 하지 않는다.**

4-2. **강의 적용 카탈로그 점검(선택).** 강의에서 나온 하네스·가드레일·문서 규칙이 이 PC와 프로젝트에 적용됐는지 보고 싶을 때만 `python scripts/check_setup.py --catalog`(또는 sources.yaml에 `catalog: true`)를 돌린다. `config/harness-catalog.json`의 항목마다 detect(파일 존재·파일 문구·플러그인 설치·settings 키·사람 확인)를 그때그때 계산해 `OK`(전부 충족) / `확인`(미충족·판정 불가) / `건너뜀`(졸업·과함 보류)으로 표를 내고, 끝에 `전체 N · OK N · 확인 N · 건너뜀 N` 요약과 우선순위 상 `확인` 상위 10개를 보인다. 파일·문구 점검은 sources.yaml의 프로젝트마다, 플러그인·settings는 PC 전역 기준이다. 모르는 detect 종류·읽지 못한 카탈로그·형식 오류·`manual`(사람이 답할 질문)은 `OK`가 아니라 `확인`이다. **읽기 전용이다.** 항목의 apply는 사용자에게 보여 줄 안내 문구일 뿐 스크립트가 설치·수정하지 않으며, 실제 설치·수정은 사용자 승인 뒤 별도 작업으로 한다. `requires_approval` 항목(permissions.deny·bypass 차단·전역 guardrail 배선)과 전역 settings 변경은 특히 승인 없이 건드리지 않는다. 카탈로그에는 상태를 적지 않는다(점검이 매번 계산).

4-3. **기존 프로젝트 개편 계획서 초안(`--adopt`)과 영향 조회(`--impact`, 선택).** 이미 운영 중인 프로젝트에 harness 틀을 입힐 때만 쓴다. `python scripts/check_setup.py --adopt <프로젝트경로|sources.yaml 의 프로젝트 이름>` 은 적용 계획서 초안(마크다운)을 stdout 으로 낸다(`--out <경로>` 를 주면 새 파일로만 쓰고, 이미 있거나 대상 프로젝트 안이면 거부). 섹션: 전제 요약 · 현황(구조·카탈로그 상 확인·CLAUDE.md/AGENTS.md 줄 수·.claude 현황·새 hook 과 경로 충돌) · 코드·폴더 레이아웃(권장과 어긋나면 `[ 사람이 매핑표 작성 ]`) · 도메인 CLAUDE.md 후보(`--min-files N`, 기본 10)와 낡은 하위 CLAUDE.md 제목 · 프로젝트 규칙 인용(줄 번호 포함, 계획의 제약) · 단계별 PR 순서 골격(승인 지점·검증·롤백은 빈칸) · 사람이 결정할 질문. 자동으로 알 수 없는 것(서버 유닛, DB 에 저장된 경로, Linear 이슈 내 경로)은 `미확인` 으로 적는다. `python scripts/check_setup.py --impact <경로|모듈문자열> [--project <프로젝트>] [--full]` 은 `git ls-files` 기준으로 그 문자열을 담은 파일·줄을 범주(코드·설정·CI/배포·문서·테스트)별로 세고 상위 폴더 분포·운영 접점(배포 워크플로·`*.spec`·pyproject/pytest.ini·systemd/cron) 걸림·상위 파일을 보인다. 결과는 **참조 수일 뿐 위험 판정이 아니며** 파일명 일치 기반이라 과대·과소일 수 있고, Linear·DB·서버의 실제 상태는 모른다. **둘 다 읽기 전용이고 이름·폴더 변경과 로직 변경은 스킬이 실행하지 않는다.** 그런 변경은 `--impact` 결과를 사람이 보고 결정한 뒤, 승인 후 별도로 superpowers 계획(`writing-plans`)과 서브에이전트 실행 스킬로 진행한다. 프로젝트 정본 규칙(CLAUDE.md·AGENTS.md)이 harness 지침보다 우선한다.
4-4. **하네스 양식 대비 문서 점검(`--templates`, 선택).** `python scripts/check_setup.py --templates <프로젝트경로|이름> [--harness <하네스 폴더>]`(하네스 위치는 sources.yaml 의 `harness:` 로도 줄 수 있다). 하네스의 `templates/*.md`·`docs/*.md` 양식 헤딩(`##`·`###`, 코드펜스·`[자리표시]` 제목 제외)이 프로젝트 문서에 있는지 비교해 `OK`/`확인`(빠진 섹션 이름)/`실패`(파일 없음)/`제외`로 표를 내고, 도메인 문서(`docs/domains/*.md`)가 `DOMAIN.md` 양식을 채웠는지와 코드 도메인 폴더 대 문서 대응을 보인다. 프로젝트 `.onboard.yaml` 의 `skip_templates`·`templates_dir`·`domain_root`·`domain_exclude`·`domain_alias` 로 의도적 차이를 선언한다. **읽기 전용이며 양식을 채우거나 문서를 만들지 않는다.**

4-4. **기존 프로젝트 도입(adopt, 선택).** 운영 중인 프로젝트를 하네스에 맞출 때, 단계마다 사용자에게 되묻지 않고 **계획을 한 번에 세우는** 절차다. 상세는 [references/adopt-playbook.md](references/adopt-playbook.md), 질문서는 [references/decision-questionnaire.md](references/decision-questionnaire.md).
   1. **Step 0 측정:** `--catalog`·`--structure`·`--adopt` 를 돌리고 처음 측정값을 표로 기록해 둔다.
   2. **Step 1 결정 질문서:** 프로젝트 규칙에서 인용한 후보 답을 채워 Q1~Q10 을 한 번에 묻고, 답을 계획서의 「고정 결정」 표로 박는다. 이후 이 표와 충돌할 때만 멈춰 묻는다.
   3. **Step 2 계획서:** Phase 표(선행·병렬 가능·완료 기준·사람 결정 지점)로 PR 단위 계획을 만든다. 구조 변경 Phase 는 Q6 이 허용일 때만 넣는다.
   4. **실행은 스킬이 하지 않는다.** 사용자가 승인한 뒤 에이전트나 사람이 PR 단위로 한다.
   5. **마감:** 같은 명령을 다시 돌려 처음 측정값과 표로 비교한다. 완료는 스크립트가 선언하지 않고, 사람 확인 항목을 사용자가 확인해 선언한다.

5. **마무리.** 모두 `OK`면 "준비됨"과 함께 다음 할 일을 한 줄로 안내한다: 새 프로젝트면 PRD 작성(`0-start-project.md`), 기존 프로젝트면 하루 루프(`2-daily-loop-and-second-brain.md`), 어떤 스킬을 언제 쓸지는 `3-when-to-use-skills.md`.

## 하지 않는 것

- 승인 없이 설치·수정·삭제·clone
- 로그인·키·비밀번호 입력, 계정 생성
- 전역 settings(`~/.claude/settings.json`) 자동 수정 — 카탈로그 점검은 읽기만 하고, 값은 제안만 한다
- 스킬이 대상 프로젝트의 파일·폴더를 만들거나 고치거나 이동하는 것(`--adopt`·`--impact` 포함). 사용자가 질문서 Q6 에서 구조 변경을 허용했을 때만 계획서에 순서를 *제안*하고, 실행은 승인 후 별도 작업이다. 질문서 답이 없으면 구조 변경 단계를 계획에 넣지 않는다
- 사람 확인 없이 도입 완료를 선언하는 것
- 목록에 없는 폴더를 뒤지거나 개인 파일 내용을 읽는 것(존재 여부와 위 표의 항목만 본다)
- 시맨틱 인덱스·그래프 DB 구축(1인 규모에는 과함. 대상이 수십 개 저장소로 커지면 별도 설계)
