# 새 PC 세팅

git 이 옮겨주는 것과 **사람이 손으로 해야 하는 것**을 구분해 적는다.
막히는 곳은 항상 뒤쪽(비밀·로그인)이지 앞쪽이 아니다.

## 1. git 이 다 해주는 것 (5분)

```powershell
git clone https://github.com/gggmlduswjs/dotfiles       $env:USERPROFILE\dotfiles
pwsh $env:USERPROFILE\dotfiles\install.ps1              # 프로필 배선 + ~\.claude 설정 배치

git clone https://github.com/gggmlduswjs/claude-skills  $env:USERPROFILE\.claude\skills

cd $env:USERPROFILE\Desktop                             # ★두 레포는 같은 상위 폴더에 나란히
git clone https://github.com/gggmlduswjs/Coupang_v2
git clone https://github.com/gggmlduswjs/bookmart
```

Desktop 이 아닌 곳에 두면 그 PC 프로필에 `$env:DEV_PROJECTS = '<상위폴더>'`.

`install.ps1` 은 **없는 파일만** 채운다(기존 설정 안 덮음). 덮고 싶으면 `-Force`.

## 2. 손으로 해야 하는 것

| | 무엇 | 어떻게 |
|---|---|---|
| a | **`.env`** (Coupang_v2 키 22개) | `.env.example` 이 모양을 알려준다. 값은 각 서비스에서 재발급 — 알라딘 TTB·네이버·카카오·한진(5개)·주소API·Supabase `DATABASE_URL` 2개·Gemini |
| b | **`.venv`** | `py -3.10+ -m venv .venv` → `.venv\Scripts\pip install -e .` → `playwright install chromium` |
| c | **CDP 로그인 크롬 6개** | 포트 9230~9235 = `007-ez·007-bm·002-bm·007-book·big6ceo·big60864`. **계정마다 WING 수동 로그인 1회.** 프로필은 `data/chrome_profile/`(gitignore) |
| d | **`gh auth login`** | PR·레포 작업용. 레포 삭제까지 하려면 `-s delete_repo` |
| e | **작업 스케줄러** | `src/scripts/runners/install_*_task.ps1` 5개 (광고리포트·자동완성·쿠팡트렌드·keepalive·seller_growth) |

★(c)가 제일 오래 걸리고 자동화가 **불가능**하다 — 쿠팡이 사람 로그인을 요구한다.
그래서 CDP 필요한 자동화는 집 PC 에만 둔다([[CLAUDE.md]] "자동화를 어디에 둘 것인가").

## 3. 확인

```powershell
dev cp 테스트          # 워크트리 생성 + claude 실행되면 1번 OK
.venv\Scripts\python.exe -c "import django, sqlalchemy, pytest, playwright"   # 2-b OK
.venv\Scripts\python.exe -m pytest tests\ -q                                   # 441개 통과
.venv\Scripts\python.exe -m scripts.deploy.check_drift                         # 드리프트 현황
```

⚠️`.venv` 판정은 `pip list` 말고 **import 스모크**로. dist-info 만 남은 부분손상이면
pip 은 "설치됨"이라고 답하면서 import 는 실패한다.

## 4. 옮겨지지 않는 것 (그냥 알고 있기)

- `out/`·`data/` 런타임 산출물 — 다시 돌리면 생긴다
- Obsidian 금고(`G:\내 드라이브\Obsidian`) — 구글 드라이브 동기화 소관
- `~/.claude/projects/*/memory/` — **세션 메모리. 이건 백업이 없다.**
  잃으면 프로젝트 맥락이 날아가므로, 옮길 거면 폴더째 복사할 것
