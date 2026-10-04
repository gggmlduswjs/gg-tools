#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit) — 코드·설정 파일에 시크릿이 박히는 것을 **확인 요청**으로 막는다.

차단(deny)이 아니라 ask 다: 오탐 한 번이면 사람이 가드를 통째로 끈다(guardrail.py 와 같은 원칙).
확실한 형식(접두어가 있는 키·토큰, 개인키 블록)만 본다. 비밀번호 같은 일반 단어는 보지 않는다.
`.example` `.sample` `.template` 파일은 예시 값을 쓰는 자리라 통과시킨다.

프로젝트 `.claude/settings.json` 에 켠다:
  {"matcher": "Write|Edit|MultiEdit",
   "hooks": [{"type": "command", "command": "python ~/claude/gg-skills/hooks/secret_guard.py"}]}

self-test:  python secret_guard.py --selftest
"""
import json
import re
import sys

PATTERNS = [
    ("Anthropic 키", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI 계열 키", re.compile(r"\bsk-(?:(?:proj|svcacct)-[A-Za-z0-9_\-]{32,}|[A-Za-z0-9]{32,})")),
    ("GitHub 토큰", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}")),
    ("AWS 액세스 키", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack 토큰", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("Google API 키", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("개인키 블록", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
]
EXEMPT_SUFFIX = (".example", ".sample", ".template")


def find_secret(path, text):
    if path.lower().endswith(EXEMPT_SUFFIX):
        return None
    for label, rx in PATTERNS:
        if rx.search(text or ""):
            return label
    return None


def texts_of(tool_input):
    """Write=content, Edit=new_string, MultiEdit=edits[].new_string."""
    parts = [tool_input.get("content") or "", tool_input.get("new_string") or ""]
    for e in tool_input.get("edits") or []:
        parts.append((e or {}).get("new_string") or "")
    return "\n".join(parts)


def run():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        ti = json.loads(sys.stdin.read()).get("tool_input", {}) or {}
    except Exception:
        sys.exit(0)  # 파싱 실패 = 통과
    label = find_secret(ti.get("file_path", "") or "", texts_of(ti))
    if label:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"[시크릿 가드] {label}로 보이는 값을 파일에 쓰려 합니다. "
                                        "환경변수나 .env(커밋 제외)로 옮길 수 있는지 확인하세요.",
        }}, ensure_ascii=False))
    sys.exit(0)


CASES = [
    ("a.py", "KEY = 'sk-proj-" + "aA_-" * 25 + "'", True),
    ("a.py", "KEY = 'sk-svcacct-" + "aA_-" * 25 + "'", True),
    (".env.example", "OPENAI_API_KEY=sk-proj-" + "aA_-" * 25, False),
    ("README.md", "키는 sk-proj-... 형식입니다", False),
    ("a.py", "KEY = 'sk-ant-api03-" + "x" * 30 + "'", True),
    ("a.py", "t = 'ghp_" + "a" * 36 + "'", True),
    ("a.py", "k = 'AKIA" + "A" * 16 + "'", True),
    ("id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----\nabc", True),
    ("config.ts", "const k = 'AIza" + "b" * 35 + "'", True),
    (".env.example", "ANTHROPIC_API_KEY=sk-ant-api03-" + "x" * 30, False),
    ("a.py", "password = get_password()  # 일반 단어는 보지 않는다", False),
    ("a.py", "sk-short", False),
    ("README.md", "키는 sk-ant-... 형식입니다", False),
]


def selftest():
    bad = [(p, t[:30]) for p, t, want in CASES if bool(find_secret(p, t)) != want]
    multi = find_secret("a.py", texts_of({"edits": [{"new_string": "x='AKIA" + "B" * 16 + "'"}]}))
    if not multi:
        bad.append(("MultiEdit", "edits"))
    if bad:
        print("secret_guard selftest FAIL:", bad)
        sys.exit(1)
    print(f"secret_guard selftest OK ({len(CASES) + 1} cases)")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else run()
