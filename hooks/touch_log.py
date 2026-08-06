#!/usr/bin/env python3
"""PostToolUse[Write|Edit] — 이 세션이 건드린 파일을 레포 안에 남긴다. 전역 훅 한 벌.

왜 필요한가 (2026-08-06): commit_sentinel 은 **크기**로 오염을 잡는다. 그래서 272 파일짜리
대형 오염은 잡지만, 같은 날 난 3 파일짜리 오염(다른 세션이 내가 만든 훅 파일을 자기 커밋에
담았다)은 임계 아래로 통과했다. 크기는 오염의 증상이지 오염 자체가 아니다.

오염 자체의 정의는 **"한 커밋 안에 서로 다른 세션의 작업이 섞여 있다"** 이다.
그걸 재려면 누가 무엇을 건드렸는지가 있어야 한다 — 이 훅이 그 기록을 남긴다.

    <repo>/.claude/sessions/<session_id>.touched   한 줄에 레포 상대경로 하나

commit_sentinel 은 커밋에 든 파일을 이 기록들과 대조해서, **둘 이상의 세션이 나눠 건드린
파일들이 한 커밋에 있으면** 알린다. 내 session_id 를 몰라도 판정된다 —
git 훅은 Claude 세션 정보를 받지 못하므로 이 설계가 아니면 잴 수가 없다.

설계 제약:
  · 매 편집마다 돈다 → append 만 한다(읽기·중복제거·정렬 전부 커밋 시점으로 미룬다)
  · 어떤 예외도 편집을 막지 않는다 → 항상 exit 0
  · `.claude/` 가 없는 레포·git 아닌 폴더는 조용히 스킵(전역 훅이라 아무 데서나 돈다)

self-test:  python touch_log.py --selftest
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def repo_root(cwd):
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def record(root, sid, file_path):
    """레포 상대경로를 <sid>.touched 에 append. 대상 밖이면 아무것도 안 한다."""
    if not root or not sid or not file_path:
        return None
    d = root / ".claude" / "sessions"
    if not d.parent.is_dir():
        return None  # .claude 없는 레포 = 관리 대상 아님
    try:
        rel = Path(file_path).resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None  # 레포 밖 파일 편집 — 오염과 무관
    d.mkdir(parents=True, exist_ok=True)
    line = rel.as_posix()
    with (d / f"{sid}.touched").open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return
    cwd = data.get("cwd") or os.getcwd()
    record(repo_root(cwd), data.get("session_id"), (data.get("tool_input") or {}).get("file_path"))


def _selftest():
    import tempfile
    root = Path(tempfile.mkdtemp()).resolve()
    (root / ".claude").mkdir()
    (root / "src").mkdir()

    assert record(root, "s1", str(root / "src" / "a.py")) == "src/a.py"
    assert record(root, "s1", str(root / "src" / "b.py")) == "src/b.py"
    assert record(root, "s2", str(root / "src" / "a.py")) == "src/a.py"   # 같은 파일 다른 세션

    log = (root / ".claude" / "sessions" / "s1.touched").read_text(encoding="utf-8")
    assert log.splitlines() == ["src/a.py", "src/b.py"], log
    assert (root / ".claude" / "sessions" / "s2.touched").exists()

    # 레포 밖 · 인자 누락 · .claude 없는 레포 — 전부 조용히 스킵
    assert record(root, "s1", "C:/somewhere/else.py") is None
    assert record(root, "s1", None) is None
    assert record(root, None, str(root / "src" / "a.py")) is None
    assert record(None, "s1", "x.py") is None
    bare = Path(tempfile.mkdtemp()).resolve()
    assert record(bare, "s1", str(bare / "x.py")) is None, ".claude 없는 레포는 대상 아님"

    print("touch_log selftest OK (9 cases)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        try:
            main()
        except Exception:
            pass  # 편집을 절대 막지 않는다
        sys.exit(0)
