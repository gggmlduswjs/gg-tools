#!/usr/bin/env python3
"""SessionStart 훅 — 프로젝트 메모리를 Drive 공용 폴더로 잇는다. 공용 엔진 한 벌.

왜 필요한가 (2026-08-13 실측):
  Claude Code 는 메모리를 `~/.claude/projects/<경로슬러그>/memory` 에 둔다. 슬러그는
  **작업 폴더 절대경로**에서 나오므로 **레포를 옮기면 슬러그가 바뀌고, 새 자리엔 빈
  폴더가 생긴다.** 그날부터 그 레포 세션은 메모리를 0개로 본다 — 에러 없이.
  북마트가 `Desktop\\bookmart` → `Desktop\\북마트\\bookmart` 로 옮긴 08-10 이후
  **사흘간 447건을 못 보고 돌았다.** 워크트리도 같은 이유로 각자 빈 폴더를 갖는다.

  전에는 전역 `settings.json` 의 PowerShell 한 줄이 이 링크를 만들었는데, 그 훅이
  라이브 설정에서 사라진 걸 **아무도 몰랐다**(설정 파일에 `hooks` 키 자체가 없었다).
  그래서 배선을 레포 안(.claude/settings.json + shim)으로 내렸다 —
  레포가 옮겨가도 워크트리를 따도 배선이 따라온다.

각 레포는 `.claude/hooks/memory_link.py` shim 에서 환경변수만 정하고 이 파일을 실행한다
(tdd_guard·commit_sentinel 과 같은 배선).

    MEMORY_DRIVE_NAME   Drive 쪽 폴더 이름 (예: coupang-v2-memory)   필수
    MEMORY_DRIVE_ROOT   공용 루트                                     기본 G:\\내 드라이브\\claude-sync

⚠️ **기존 메모리가 든 실폴더는 절대 건드리지 않는다.** 비어 있을 때만 링크로 바꾼다 —
   지우고 잇는 순간 그 레포가 로컬에만 쌓아둔 것이 사라지기 때문이다.

self-test:  python memory_link.py --selftest
"""
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = r"G:\내 드라이브\claude-sync"


def slug(path: str) -> str:
    """Claude Code 가 projects/ 아래에 쓰는 이름. 영숫자·하이픈 외는 전부 '-'.

    한글 한 글자가 하이픈 하나가 된다 — `Desktop\\쿠팡\\Coupang_v2` 가
    `C--Users-user-Desktop----Coupang-v2` 인 이유(실측 확인).
    """
    return re.sub(r"[^a-zA-Z0-9-]", "-", path)


def plan(link: Path, target: Path):
    """무엇을 할지 결정한다. (action, 사유) — 부수효과 없음이라 테스트가 쉽다.

    action: ok | link | replace_empty | keep_nonempty | no_target
    """
    if not target.exists():
        return "no_target", f"공용 폴더가 없다: {target}"
    if link.is_symlink():
        try:
            same = link.resolve() == target.resolve()
        except OSError:
            same = False
        return ("ok", "이미 이어져 있다") if same else ("keep_nonempty", f"다른 곳을 가리킨다: {link.resolve()}")
    if not link.exists():
        return "link", "링크가 없다"
    entries = list(link.iterdir())
    if entries:
        # 여기서 지우면 로컬 전용 메모리를 잃는다. 사람이 옮겨야 한다.
        return "keep_nonempty", f"실폴더에 {len(entries)}건이 있다 — 사람이 옮겨야 한다"
    return "replace_empty", "빈 실폴더다"


def apply(link: Path, target: Path, action: str) -> None:
    if action == "replace_empty":
        link.rmdir()
    if action in ("link", "replace_empty"):
        link.parent.mkdir(parents=True, exist_ok=True)
        _symlink(link, target)


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError:
        pass
    # Windows 에서 개발자 모드/권한이 없으면 symlink 가 막힌다. junction 은 권한이 필요 없다.
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True,
        )
    else:
        raise


def main() -> int:
    name = os.environ.get("MEMORY_DRIVE_NAME", "").strip()
    if not name:
        return 0  # shim 이 안 정했으면 조용히 넘어간다 — 남의 레포에서 훅이 시끄러우면 안 된다
    root = Path(os.environ.get("MEMORY_DRIVE_ROOT", DEFAULT_ROOT))
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    link = Path.home() / ".claude" / "projects" / slug(str(Path(cwd).resolve())) / "memory"
    target = root / name

    action, why = plan(link, target)
    if action == "ok":
        return 0
    if action in ("no_target", "keep_nonempty"):
        # ⚠️ 조용히 넘어가면 메모리 0개인 채로 도는 걸 또 몇 주 모른다.
        print(f"⚠️ 프로젝트 메모리가 공용 폴더에 안 이어져 있다 — {why}")
        print(f"   링크: {link}\n   대상: {target}")
        return 0
    try:
        apply(link, target, action)
    except Exception as e:  # 훅이 세션을 막으면 안 된다
        print(f"⚠️ 메모리 링크 실패({why}): {e}")
        return 0
    n = len(list(link.iterdir())) if link.exists() else 0
    print(f"[memory-link] 공용 메모리 연결 — {name} ({n}건)")
    return 0


def _selftest() -> int:
    import tempfile

    assert slug(r"C:\Users\user\Desktop\쿠팡\Coupang_v2") == "C--Users-user-Desktop----Coupang-v2"
    assert slug(r"C:\Users\user\Desktop\북마트\bookmart") == "C--Users-user-Desktop-----bookmart"
    assert slug(r"C:\Users\user\Desktop\bookmart") == "C--Users-user-Desktop-bookmart"

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        target = td / "drive" / "mem"
        link = td / "proj" / "memory"

        # 대상이 없으면 만들지 않는다
        assert plan(link, target)[0] == "no_target"
        target.mkdir(parents=True)
        (target / "a.md").write_text("x", encoding="utf-8")

        # 없으면 잇는다
        act, _ = plan(link, target)
        assert act == "link", act
        apply(link, target, act)
        assert (link / "a.md").exists()

        # 두 번째 실행은 아무것도 안 한다
        assert plan(link, target)[0] == "ok"

        # 빈 실폴더는 바꾼다
        link2 = td / "proj2" / "memory"
        link2.mkdir(parents=True)
        act, _ = plan(link2, target)
        assert act == "replace_empty", act
        apply(link2, target, act)
        assert (link2 / "a.md").exists()

        # ★ 내용이 든 실폴더는 절대 안 건드린다
        link3 = td / "proj3" / "memory"
        link3.mkdir(parents=True)
        (link3 / "local.md").write_text("소중함", encoding="utf-8")
        act, why = plan(link3, target)
        assert act == "keep_nonempty", act
        assert "1건" in why, why
        assert (link3 / "local.md").exists()

    print("memory_link engine self-check OK - 8 passed")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
