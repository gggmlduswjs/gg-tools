# dotfiles

여러 PC(회사·집)에서 공유하는 개인 개발 설정. **한 PC에서 고치고 push → 다른 PC에서 pull** 하면 반영.

프로젝트별 스크립트(빌드/테스트/워크트리)는 각 프로젝트 레포에 있고, 여기엔 **프로젝트를 가로지르는 개인 도구**만 둔다.

## 내용
- `powershell/dev-profile.ps1` — 프로젝트 세션 격리 통일 런처 `dev`.
  - `dev bm <이름>` → bookmart 격리 worktree에서 claude (`bookmart/_scripts/bmwt.ps1 start`)
  - `dev cp <이름>` → Coupang_v2 격리 worktree에서 claude (`Coupang_v2/wt.ps1 new`)
  - `dev` → 사용법. 이름 생략 시 자동 명명.
- `install.ps1` — 이 PC 프로필에 dev 런처 dot-source 한 줄 배선(idempotent).

## 새 PC 세팅 (1회)
```powershell
git clone https://github.com/gggmlduswjs/dotfiles $env:USERPROFILE\dotfiles
pwsh $env:USERPROFILE\dotfiles\install.ps1
# 새 터미널 → dev bm 반품
```

## 이후
- `dev` 고칠 일: `powershell/dev-profile.ps1` 수정 → commit/push. 다른 PC는 `git pull`만.

## 전제
- bookmart / Coupang_v2 가 **같은 상위 폴더에 나란히**(기본 `<사용자>\Desktop`).
- 다른 경로면 그 PC에서 `$env:DEV_PROJECTS` 에 상위폴더 지정.
