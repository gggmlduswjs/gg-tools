#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit) — 구현 파일을 고치려는데 **대응하는 테스트 파일이 없으면 확인 요청**.

"테스트 먼저"를 문서가 아니라 장치로 상기시킨다. 테스트가 통과하는지는 보지 않는다(파일 존재만).
기본은 **꺼져 있다** — 프로젝트가 `.claude/settings.json` 에서 직접 켠다(모든 프로젝트에 맞지 않음):
  {"matcher": "Write|Edit|MultiEdit",
   "hooks": [{"type": "command", "command": "python ~/claude/gg-skills/hooks/tdd_guard.py"}]}

보는 것: .py .ts .tsx .js .jsx .vue 중 테스트·설정·문서·마이그레이션이 아닌 파일.
대응 테스트: test_<이름>.py · <이름>_test.py · <이름>.test.* · <이름>.spec.* 가 프로젝트 안 어딘가에 있으면 통과.

self-test:  python tdd_guard.py --selftest
"""
import json
import os
import re
import sys

CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".vue")
SKIP_DIR = {"node_modules", ".git", "venv", ".venv", "dist", "build", "__pycache__", ".next"}
NON_TARGET = re.compile(
    r"(^|/)(tests?|__tests__|migrations|alembic|scripts|docs|\.claude|\.github)/|"
    r"(^|/)(conftest|setup|vite\.config|next\.config|tailwind\.config|eslint\.config)\.|"
    r"(^|/)(index|__init__|main|app)\.(py|ts|tsx|js|jsx|vue)$|"
    r"\.(test|spec|d)\.|(^|/)test_|_test\.",
)


def is_target(path):
    p = path.replace("\\", "/")
    return p.endswith(CODE_EXT) and not NON_TARGET.search(p)


def test_names(stem):
    exts = ("py", "ts", "tsx", "js", "jsx", "vue")
    names = {f"test_{stem}.py", f"{stem}_test.py"}
    names |= {f"{stem}.{k}.{e}" for k in ("test", "spec") for e in exts}
    return names


def has_test(path, root):
    stem = os.path.splitext(os.path.basename(path))[0]
    wanted = test_names(stem)
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIR]
        if wanted.intersection(fn):
            return True
    return False


def run():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        ti = json.loads(sys.stdin.read()).get("tool_input", {}) or {}
    except Exception:
        sys.exit(0)
    path = ti.get("file_path", "") or ""
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if path and is_target(path) and not has_test(path, root):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"[TDD 가드] {os.path.basename(path)}에 대응하는 테스트 파일이 없습니다. "
                                        "실패하는 테스트를 먼저 만들 수 있는지 확인하세요.",
        }}, ensure_ascii=False))
    sys.exit(0)


def selftest():
    import shutil
    import tempfile
    bad = []
    for p, want in [("src/a.py", True), ("src/a.test.ts", False), ("tests/test_a.py", False),
                    ("docs/x.py", False), ("README.md", False), ("src/index.ts", False),
                    ("src/comp/Card.vue", True), ("migrations/001.py", False)]:
        if is_target(p) != want:
            bad.append(("is_target", p))
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, "tests"))
        open(os.path.join(d, "tests", "test_pay.py"), "w").close()
        if not has_test("src/pay.py", d):
            bad.append(("has_test", "pay"))
        if has_test("src/refund.py", d):
            bad.append(("has_test", "refund"))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if bad:
        print("tdd_guard selftest FAIL:", bad)
        sys.exit(1)
    print("tdd_guard selftest OK (10 cases)")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else run()
