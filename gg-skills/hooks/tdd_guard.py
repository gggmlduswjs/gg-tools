#!/usr/bin/env python3
"""TDD Guard 엔진 — PreToolUse[Write|Edit] 공용 로직 (레포별 shim 이 env 로 배치만 정한다).

레포 shim 예:
  TDD_GUARDED=/src/orders/services/
  TDD_TESTS=src/*/tests,src/*/*/tests
  → runpy 로 이 파일을 실행

동작:
  · 가드 범위 밖 / 테스트 파일 자체 / 비소스 → 통과
  · 가드 범위 소스인데 테스트가 모듈을 참조하지 않으면 ask (기본)
  · TDD_DECISION=deny 이면 데모 프로젝트처럼 하드 차단
    (https://github.com/jha0313/demo-project/blob/main/.claude/hooks/tdd-guard.sh)

참조 판정 (하나라도 있으면 OK):
  1) 테스트 파일명에 stem 포함 — test_<stem>.py / *test*<stem>*.py / <stem>.test.*
  2) 테스트 파일 본문에 stem 토큰 (import 등)

self-test:  python ~/claude/hooks/tdd_guard.py --selftest
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TAG = "[가드레일]"


def _norm(p: str) -> str:
    return (p or "").replace("\\", "/")


def _repo_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.cwd()


def _guarded_prefixes() -> list[str]:
    raw = os.environ.get("TDD_GUARDED", "").strip()
    if not raw:
        return []
    return [p.strip().replace("\\", "/") for p in raw.split(",") if p.strip()]


def _test_globs() -> list[str]:
    raw = os.environ.get("TDD_TESTS", "tests").strip()
    return [g.strip().replace("\\", "/") for g in raw.split(",") if g.strip()]


def _decision() -> str:
    d = (os.environ.get("TDD_DECISION") or "ask").strip().lower()
    return "deny" if d == "deny" else "ask"


def _is_test_path(path: str) -> bool:
    p = _norm(path).lower()
    name = Path(p).name.lower()
    if "/tests/" in p or "/__tests__/" in p or "/test/" in p:
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if ".test." in name or ".spec." in name:
        return True
    if name.endswith("_test.js") or name.endswith(".test.js"):
        return True
    return False


def _is_source_path(path: str) -> bool:
    p = _norm(path)
    name = Path(p).name
    if name in ("__init__.py", "apps.py", "admin.py"):
        return False
    if "/migrations/" in p:
        return False
    return p.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))


def _in_guarded(path: str, prefixes: list[str]) -> bool:
    p = _norm(path)
    if not p.startswith("/"):
        p = "/" + p.lstrip("/")
    # also accept without leading slash match against "/src/..."
    variants = {p, p.lstrip("/"), "/" + p.lstrip("/")}
    for pref in prefixes:
        pref_n = pref if pref.startswith("/") else "/" + pref
        for v in variants:
            vv = v if v.startswith("/") else "/" + v
            if pref_n in vv or vv.startswith(pref_n.rstrip("/") + "/") or vv.endswith(pref_n.rstrip("/")):
                # substring match like "/src/orders/services/" in full path
                if pref_n.rstrip("/") in vv:
                    return True
    # simpler: normalize and check containment
    full = _norm(path)
    if not full.startswith("/"):
        full = "/" + full
    for pref in prefixes:
        token = pref if pref.startswith("/") else "/" + pref
        if token.rstrip("/") in full:
            return True
    return False


def _stem(path: str) -> str:
    name = Path(_norm(path)).name
    for ext in (".py", ".tsx", ".ts", ".jsx", ".js"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return Path(name).stem


def _expand_test_roots(root: Path, globs: list[str]) -> list[Path]:
    """TDD_TESTS 항목을 실제 디렉터리 목록으로.

    · 'tests' → <root>/tests
    · 'src/*/tests' → glob
    · 'src/*/*/tests' → glob
    """
    out: list[Path] = []
    for g in globs:
        g = g.strip().strip("/")
        if any(ch in g for ch in "*?[]"):
            for hit in root.glob(g):
                if hit.is_dir():
                    out.append(hit)
        else:
            p = root / g
            if p.is_dir():
                out.append(p)
    # unique
    seen = set()
    uniq = []
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def _name_match(stem: str, file_name: str) -> bool:
    n = file_name.lower()
    s = stem.lower()
    if n in (f"test_{s}.py", f"{s}_test.py", f"{s}.test.py", f"{s}.test.ts",
             f"{s}.test.tsx", f"{s}.test.js", f"{s}.spec.ts", f"{s}.spec.js"):
        return True
    # soft: test file name contains stem (avoid tiny stems)
    if len(s) >= 4 and s in n and ("test" in n or "spec" in n):
        return True
    return False


def _content_has_stem(path: Path, stem: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    # word-ish: import … stem / from … stem / "stem"
    if re.search(rf"(?<![A-Za-z0-9_]){re.escape(stem)}(?![A-Za-z0-9_])", text):
        return True
    return False


def has_referencing_test(stem: str, test_roots: list[Path]) -> bool:
    if not stem or stem == "__init__":
        return True
    patterns = ("test_*.py", "*_test.py", "*.test.py", "*.test.ts", "*.test.tsx",
                "*.test.js", "*.test.jsx", "*.spec.ts", "*.spec.js")
    for root in test_roots:
        files: list[Path] = []
        for pat in patterns:
            files.extend(root.rglob(pat))
        # also any .py under tests/ named with test
        files.extend(p for p in root.rglob("*.py") if "test" in p.name.lower())
        seen = set()
        for f in files:
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            if _name_match(stem, f.name):
                return True
            if _content_has_stem(f, stem):
                return True
    return False


def scope_label(prefixes: list[str]) -> str:
    parts = []
    for p in prefixes:
        p = p.strip("/")
        # short: last 2 segments
        segs = [s for s in p.split("/") if s]
        parts.append("·".join(segs[-2:]) if segs else p)
    return "·".join(parts) if parts else "?"


def check(file_path: str, root: Path | None = None) -> str | None:
    """없으면 None(통과). 있으면 차단/확인 reason 문자열."""
    prefixes = _guarded_prefixes()
    if not prefixes:
        return None
    path = _norm(file_path)
    if not path:
        return None
    if not _in_guarded(path, prefixes):
        return None
    if _is_test_path(path):
        return None
    if not _is_source_path(path):
        return None

    root = root or _repo_root()
    stem = _stem(path)
    test_roots = _expand_test_roots(root, _test_globs())
    if not test_roots:
        # 테스트 폴더를 못 찾으면 오탐 방지 — 통과
        return None
    if has_referencing_test(stem, test_roots):
        return None

    example = f"tests/test_{stem}.py"
    # 같은 앱 트리의 tests/ 를 우선 (src/orders/services → src/orders/tests)
    if test_roots:
        src_full = _norm(str((root / path.lstrip("/")).resolve())) if not Path(path).is_absolute() else _norm(path)
        best = None
        best_score = -1
        for tr in test_roots:
            tr_s = _norm(str(tr.resolve()))
            # 공통 부모 깊이로 점수
            a, b = src_full.split("/"), tr_s.split("/")
            n = 0
            for x, y in zip(a, b):
                if x != y:
                    break
                n += 1
            if n > best_score:
                best_score = n
                best = tr
        rel = best or test_roots[0]
        try:
            rel_s = rel.relative_to(root).as_posix()
            example = f"{rel_s}/test_{stem}.py"
        except Exception:
            pass

    return (
        f"TDD 가드: '{stem}' 참조 테스트가 tests/ 에 없습니다. "
        f"로직 변경이면 테스트 먼저 권장(예: {example}) · "
        f"코멘트/문서 편집이면 확인 후 진행. [범위: {scope_label(prefixes)}]"
    )


def emit(decision: str, reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"{TAG} {reason}",
        }
    }, ensure_ascii=False))


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        ti = data.get("tool_input") or {}
        file_path = ti.get("file_path") or ""
    except Exception:
        sys.exit(0)

    reason = check(file_path)
    if reason:
        emit(_decision(), reason)
    sys.exit(0)


def _selftest() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        svc = root / "src" / "orders" / "services"
        tests = root / "src" / "orders" / "tests"
        svc.mkdir(parents=True)
        tests.mkdir(parents=True)
        (svc / "demo_data.py").write_text("X = 1\n", encoding="utf-8")
        (svc / "pricing_math.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        (tests / "test_pricing_math.py").write_text(
            "from orders.services.pricing_math import f\n", encoding="utf-8"
        )

        os.environ["TDD_GUARDED"] = "/src/orders/services/"
        os.environ["TDD_TESTS"] = "src/*/tests"
        os.environ.pop("TDD_DECISION", None)

        # has test → pass
        assert check("src/orders/services/pricing_math.py", root) is None
        # no test → ask reason
        r = check("src/orders/services/demo_data.py", root)
        assert r and "demo_data" in r and "TDD 가드" in r, r
        # outside guard → pass
        assert check("src/orders/views/foo.py", root) is None
        # test file itself → pass
        assert check("src/orders/tests/test_pricing_math.py", root) is None
        # non-py → pass
        assert check("src/orders/services/readme.md", root) is None
        # empty guard → pass
        os.environ["TDD_GUARDED"] = ""
        assert check("src/orders/services/demo_data.py", root) is None

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("tdd_guard engine self-check OK - 6 passed")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
