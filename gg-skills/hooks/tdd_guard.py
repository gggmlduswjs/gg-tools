#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit) — 구현 파일을 고치려는데 **대응하는 테스트 파일이 없으면 확인 요청**.

"테스트 먼저"를 문서가 아니라 장치로 상기시킨다. 테스트가 통과하는지는 보지 않는다(파일 존재만).
기본은 **꺼져 있다** — 프로젝트가 `.claude/settings.json` 에서 직접 켠다(모든 프로젝트에 맞지 않음):
  {"matcher": "Write|Edit|MultiEdit",
   "hooks": [{"type": "command", "command": "python ~/claude/gg-skills/hooks/tdd_guard.py"}]}

차단 모드(확인 요청 대신 도구 호출을 deny):
  "command": "python ~/claude/gg-skills/hooks/tdd_guard.py --mode deny"
끄기: 환경변수 TDD_GUARD_DISABLE=1 (옵션·환경변수가 없으면 기존 동작 = ask).

보는 것: .py .ts .tsx .js .jsx .vue 중 테스트·설정·문서·마이그레이션이 아닌 파일.
대응 테스트: test_<이름>.py · <이름>_test.py · <이름>.test.* · <이름>.spec.* 가 프로젝트 안 어딘가에 있으면 통과.

self-test:  python tdd_guard.py --selftest   (ask·deny 모드 포함)
"""
import json
import os
import re
import sys

CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".vue")
SKIP_DIR = {"node_modules", ".git", "venv", ".venv", "dist", "build", "__pycache__", ".next"}
NON_TARGET = re.compile(
    r"(^|/)(tests?|__tests__|migrations|alembic|scripts|docs|types|\.claude|\.github)/|"
    r"(^|/)(conftest|setup)\.|\.config\.|"
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


def expected_test(path):
    stem, ext = os.path.splitext(os.path.basename(path))
    return f"test_{stem}.py" if ext == ".py" else f"{stem}.test{ext}"


def decide(path, root, mode):
    """None=통과, 아니면 hookSpecificOutput dict."""
    if not (path and is_target(path) and not has_test(path, root)):
        return None
    if mode == "deny":
        return {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "테스트 파일이 존재하지 않습니다. 코드를 작성하기 전에 테스트부터 작성하세요.\n"
                                            f"예상 테스트 경로: {expected_test(path)}"}
    return {"hookEventName": "PreToolUse", "permissionDecision": "ask",
            "permissionDecisionReason": f"[TDD 가드] {os.path.basename(path)}에 대응하는 테스트 파일이 없습니다. "
                                        "실패하는 테스트를 먼저 만들 수 있는지 확인하세요."}


def run():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if os.environ.get("TDD_GUARD_DISABLE"):
        sys.exit(0)
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv[:-1] else "ask"
    try:
        ti = json.loads(sys.stdin.read()).get("tool_input", {}) or {}
    except Exception:
        sys.exit(0)
    path = ti.get("file_path", "") or ""
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    out = decide(path, root, mode)
    if out:
        print(json.dumps({"hookSpecificOutput": out}, ensure_ascii=False))
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
    import subprocess
    me = os.path.abspath(__file__)
    d2 = tempfile.mkdtemp()
    try:
        def call(args, path, env_extra=None):
            env = {**os.environ, "CLAUDE_PROJECT_DIR": d2}
            env.pop("TDD_GUARD_DISABLE", None)
            env.update(env_extra or {})
            res = subprocess.run([sys.executable, me, *args], input=json.dumps({"tool_input": {"file_path": path}}),
                                 capture_output=True, text=True, encoding="utf-8", env=env)
            return res.returncode, res.stdout
        rc, out = call(["--mode", "deny"], "src/pay.py")
        o = json.loads(out)["hookSpecificOutput"] if out else {}
        reason = o.get("permissionDecisionReason", "")
        if rc != 0 or o.get("permissionDecision") != "deny" or "테스트부터 작성" not in reason or "test_pay.py" not in reason:
            bad.append(("deny", rc, out))
        rc, out = call([], "src/pay.py")
        if rc != 0 or json.loads(out)["hookSpecificOutput"]["permissionDecision"] != "ask":
            bad.append(("default-ask", rc, out))
        if call(["--mode", "deny"], "src/pay.py", {"TDD_GUARD_DISABLE": "1"}) != (0, ""):
            bad.append(("disable",))
        for ok in ("tests/test_pay.py", "src/types/user.ts", "jest.config.js", ""):
            if call(["--mode", "deny"], ok) != (0, ""):
                bad.append(("pass", ok))
    finally:
        shutil.rmtree(d2, ignore_errors=True)
    if bad:
        print("tdd_guard selftest FAIL:", bad)
        sys.exit(1)
    print("tdd_guard selftest OK (10 + 7 cases)")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else run()
