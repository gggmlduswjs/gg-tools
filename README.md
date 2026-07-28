# dotfiles

여러 PC(회사·집)에서 공유하는 개인 개발 설정. **한 PC에서 고치고 push → 다른 PC에서 pull** 하면 반영.

프로젝트별 스크립트(빌드/테스트/워크트리)는 각 프로젝트 레포에 있고, 여기엔 **프로젝트를 가로지르는 개인 도구**만 둔다.

## 내용
- `powershell/dev-profile.ps1` — 프로젝트 세션 격리 통일 런처 `dev`.
  - `dev bm <이름>` → bookmart 격리 worktree에서 claude (`bookmart/_scripts/bmwt.ps1 start`)
  - `dev cp <이름>` → Coupang_v2 격리 worktree에서 claude (`Coupang_v2/wt.ps1 new`)
  - `dev` → 사용법. 이름 생략 시 자동 명명.
- `powershell/wt-engine.ps1` — worktree lifecycle **공용 엔진**. bookmart `bmwt.ps1` ·
  Coupang `wt.ps1` · `devclean` 이 전부 이걸 부른다(2026-07-28 3벌 → 1벌 통합).
- `claude/` — `~\.claude` 의 손으로 쓴 설정 백업(`CLAUDE.md` · `settings.json` ·
  `commands/` · `statusline.ps1`). 여기 없으면 디스크가 죽을 때 같이 사라진다.
  `settings.json` 의 `permissions.allow` 는 지난 세션 스크래치패드 경로라 비워서 담는다.
- `install.ps1` — 프로필에 dev 런처 배선 + `claude/` 배치(idempotent).
- `북마크_레포.md` — 포크 대신 Star 로 돌린 남의 레포 색인(복구용).
- `새PC.md` — **git 이 못 옮기는 것**(`.env` · `.venv` · CDP 로그인 크롬) 체크리스트.

## 새 PC 세팅 (1회)
```powershell
git clone https://github.com/gggmlduswjs/dotfiles $env:USERPROFILE\dotfiles
pwsh $env:USERPROFILE\dotfiles\install.ps1
# 새 터미널 → dev bm 반품
```
그다음 **`새PC.md`** — 여기까진 5분이고, 진짜 시간은 `.env` 값과 CDP 로그인 6계정에서 든다.

`install.ps1` 은 **없는 파일만** 채운다(그 PC에서 손본 설정을 조용히 덮지 않는다). 덮으려면 `-Force`.

## 이후
- `dev` 고칠 일: `powershell/dev-profile.ps1` 수정 → commit/push. 다른 PC는 `git pull`만.

## 전제
- bookmart / Coupang_v2 가 **같은 상위 폴더에 나란히**(기본 `<사용자>\Desktop`).
- 다른 경로면 그 PC에서 `$env:DEV_PROJECTS` 에 상위폴더 지정.
