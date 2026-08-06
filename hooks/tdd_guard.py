#!/usr/bin/env python3
"""PreToolUse[Edit|Write] TDD 가드 — **공용 엔진 한 벌**.

지정한 계층의 .py 를 편집/생성하려 할 때, 그 모듈을 참조하는 테스트가 이미
있는지 확인한다. 없으면 ask(확인) — 테스트 먼저를 넛지한다. 하드 차단이 아니다.
코멘트·문서 편집이면 확인 후 그대로 진행하면 된다.

각 레포는 `.claude/hooks/tdd_guard.py` 라는 얇은 shim 에서 환경변수 둘만 정하고
이 파일을 실행한다(wt-engine.ps1 과 같은 배선). 로직이 한 벌이라 한쪽에서 고친
오탐이 반대편에도 간다 — 두 벌이었을 때 서로의 교훈을 못 받던 게 통합 이유다.

    TDD_GUARDED  검사할 경로 조각, 쉼표 구분   예) /src/core/,/src/operations/
    TDD_TESTS    테스트 폴더(레포 루트 기준 glob), 쉼표 구분   예) tests  ·  src/*/tests

self-test:  python tdd_guard.py --selftest
"""
import json
import os
import re
import sys
from pathlib import Path

GUARDED = tuple(g for g in os.environ.get("TDD_GUARDED", "/src/").split(",") if g)
TEST_GLOBS = tuple(t for t in os.environ.get("TDD_TESTS", "tests").split(",") if t)


def repo_root(file_path):
    """…/src/core/x.py 에서 /src/ 앞부분 = 레포 루트. 실패 시 CLAUDE_PROJECT_DIR."""
    norm = file_path.replace("\\", "/")
    i = norm.rfind("/src/")
    if i != -1:
        return Path(norm[:i])
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else None


def test_dirs(root):
    """TDD_TESTS 의 glob 을 풀어 실제 존재하는 테스트 폴더만 준다."""
    if not root:
        return []
    out = []
    for g in TEST_GLOBS:
        out.extend(p for p in root.glob(g) if p.is_dir())
    return out


def has_test_for(basename, root):
    """테스트 폴더 어딘가에 basename 을 (파일명 또는 본문 참조)으로 쓰는 테스트가 있나."""
    word = re.compile(r"\b" + re.escape(basename) + r"\b")
    for d in test_dirs(root):
        for p in d.rglob("test_*.py"):
            if basename in p.stem:  # 파일명 매치 (test_barcode_heal.py)
                return True
            try:
                if word.search(p.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except OSError:
                continue
    return False


def decide(file_path, root):
    """ask 사유(str) 또는 통과(None)."""
    norm = file_path.replace("\\", "/")
    if not norm.endswith(".py"):
        return None
    if not any(g in norm for g in GUARDED):
        return None
    basename = Path(norm).stem
    if basename == "__init__":  # 패키지 초기화 = 테스트 대상 아님
        return None
    if has_test_for(basename, root):
        return None
    where = " · ".join(TEST_GLOBS)
    scope = " · ".join(g.strip("/") for g in GUARDED)
    return (f"TDD 가드: '{basename}' 참조 테스트가 {where} 에 없습니다. "
            f"로직 변경이면 테스트 먼저 권장(예: test_{basename}.py) · "
            f"코멘트/문서 편집이면 확인 후 진행. [범위: {scope}]")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 → UTF-8 (한글 사유 보존)
    except Exception:
        pass
    try:
        fp = json.loads(sys.stdin.read()).get("tool_input", {}).get("file_path", "") or ""
    except Exception:
        sys.exit(0)  # 파싱 실패 = 통과 (가드가 정상 작업을 막지 않는다)
    if not fp:
        sys.exit(0)
    reason = decide(fp, repo_root(fp))
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"[가드레일] {reason}",
        }}, ensure_ascii=False))
    sys.exit(0)


def _selftest():
    """두 레포의 실제 배치를 각각 재현해서 돌린다 — 설정이 갈려도 로직은 한 벌이어야 한다."""
    import tempfile
    global GUARDED, TEST_GLOBS
    ok = 0

    # ── Coupang 배치: tests/ 가 레포 루트 ──────────────────────────────────
    GUARDED, TEST_GLOBS = ("/src/core/", "/src/operations/"), ("tests",)
    root = Path(tempfile.mkdtemp())
    (root / "tests").mkdir()
    (root / "tests" / "test_barcode_heal.py").write_text("from core.x import heal\n", encoding="utf-8")
    (root / "tests" / "test_constants_pricing.py").write_text("import constants\n", encoding="utf-8")
    assert decide("/repo/src/scripts/collect.py", root) is None      # 범위 밖
    assert decide("/repo/src/webapp/views.py", root) is None         # 범위 밖
    assert decide("/repo/src/core/__init__.py", root) is None        # 패키지 초기화
    assert decide("/repo/src/core/notes.md", root) is None           # 비 .py
    assert decide("/repo/src/core/services/barcode_heal.py", root) is None  # 파일명 매치
    assert decide("/repo/src/core/constants.py", root) is None       # 본문 참조 매치
    assert decide("/repo/src/core/brand_new.py", root) is not None   # 테스트 없음
    assert decide("/repo/src/operations/uploader.py", root) is not None
    ok += 8

    # ── bookmart 배치: tests 가 src/<앱>/tests/ ────────────────────────────
    GUARDED, TEST_GLOBS = ("/src/orders/services/",), ("src/*/tests",)
    root = Path(tempfile.mkdtemp())
    (root / "src" / "orders" / "tests").mkdir(parents=True)
    (root / "src" / "orders" / "tests" / "test_purchase_return.py").write_text("x\n", encoding="utf-8")
    assert decide("/repo/src/orders/views/list.py", root) is None    # 범위 밖(views)
    assert decide("/repo/src/orders/services/purchase_return.py", root) is None  # 파일명 매치
    assert decide("/repo/src/orders/services/brand_new.py", root) is not None    # 테스트 없음
    ok += 3

    # ── 테스트 폴더가 아예 없어도 죽지 않는다 ──────────────────────────────
    assert decide("/repo/src/orders/services/x.py", Path(tempfile.mkdtemp())) is not None
    ok += 1

    print(f"tdd_guard selftest OK ({ok} cases · 두 레포 배치 모두)")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
