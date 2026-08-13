#!/usr/bin/env python3
"""PreToolUse 가드레일 — 공용 엔진 한 벌. 판정 로직 + **두 레포가 같이 지는 위험**.

각 레포는 `.claude/hooks/guardrail.py` shim 에서 자기 규칙만 정하고 여기를 부른다.

    engine = runpy.run_path(ENGINE, run_name="guardrail_engine")
    RULES = REPO_DENY + engine["deny_common"](migration_hint="…") \
          + REPO_ASK  + engine["ask_common"]()
    engine["check"](RULES, REPO_CASES)   # --selftest
    engine["run"](RULES)                 # 실제 훅

★왜 갈랐나 (2026-08-13): 쿠팡 95줄 / 북마트 199줄이 **`decide()`·`main()` 은 글자까지
  같은데 규칙만 갈려** 있었다. 그래서 한쪽이 겪은 사고를 반대편이 그대로 안고 있었다 —
  북마트만 알던 것 셋을 쿠팡이 못 받고 있었다:
    · 명령줄 인라인 시크릿(`sk-…` 를 승인하면 settings.local.json allow 에 **평문**으로 박힌다)
    · `git rm --pathspec-from-file`(대상이 명령에 안 보이는 일괄삭제 우회)
    · `git checkout/restore .` 계열 워킹트리 폐기
  반대로 쿠팡만 알던 `git add .env` 를 북마트가 못 받고 있었다.

⚠️★★★ **순서가 곧 판정이다** — 위→아래, 첫 매치 적용. 그래서 shim 은 rule 을 이어붙일 때
  **deny 를 전부 앞에** 둔다(`REPO_DENY + COMMON_DENY + REPO_ASK + COMMON_ASK`).
  안 그러면 `DB_ALLOW_WRITE=1 python manage.py migrate` 같은 게 ask 로 새 나간다.

⚠️ 차단 아닌 `ask` 를 넉넉히 쓰는 이유: **오탐 한 번이면 사람이 가드를 통째로 끈다.**
  막는 장치는 오탐 비용이 크고, 묻는 장치는 "한 줄 더 읽기"가 전부다.

self-test:  python guardrail.py --selftest      (공용 규칙만 검사)
"""
import json
import re
import sys


def deny_common(migration_hint="마이그레이션 경로로만"):
    """어느 레포에서나 금지. `migration_hint` 만 레포 사정으로 갈린다."""
    return [
        (r"\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b", "deny",
         f"운영 DB DDL 금지. 스키마 변경은 {migration_hint}."),
        (r"\bALTER\s+(TABLE|DATABASE|SCHEMA)\b", "deny",
         f"운영 DB DDL 금지. 스키마 변경은 {migration_hint}."),
        # 파국적 rm 만. 일반 `rm -rf <subdir>` 는 통과시킨다 — allowlist 를 존중해야
        # 사람이 가드를 안 끈다.
        (r"\brm\s+-[a-z]*[rf][a-z]*\s+(-[a-z]+\s+)*(/|~|\*|\.)/?(\s|$|;|&)", "deny",
         "루트/홈/전체(/ ~ * .) 대상 rm -rf 는 되돌릴 수 없음. 구체 경로를 지정하라."),
    ]


def ask_common():
    """파괴적이지만 가끔 정당 — 확인을 강제한다. 두 레포가 같이 지는 위험만 둔다."""
    return [
        (r"git\s+push\b[^|&;]*(--force|--force-with-lease|\s-f\b)", "ask",
         "force push 는 원격 이력을 덮어씀. 브랜치·원격 확인 후 진행."),
        (r"git\s+reset\s+--hard\b", "ask",
         "reset --hard 는 **워킹트리 전체**를 되돌린다 — 지우려는 커밋뿐 아니라 그 폴더의 "
         "미커밋 작업이 전부 날아간다(2026-08-06: 임시 커밋 하나 지우려다 다른 파일 2개의 "
         "미커밋 수정을 같이 잃었다). 커밋만 풀 거면 `git reset --soft HEAD~1`."),
        # 2026-08-06 사고: 다른 세션이 `git add -A` 를 하는 바람에 272 파일이 그쪽 커밋에
        # 딸려갔다(중앙값 1 파일인 레포에서). 알아챈 건 우연이었다.
        (r"git\s+add\s+(-A\b|--all\b|\.(\s|$))", "ask",
         "`git add -A`/`git add .` 는 워킹트리 전부를 담는다 — 같은 폴더에서 다른 세션이 "
         "작업 중이면 남의 파일까지 커밋된다(2026-08-06, 272개). "
         "경로를 적어라: `git add -- <파일1> <파일2>`"),
        (r"\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)", "ask",
         "checkout/restore . 는 커밋 안 된 작업(다른 세션 포함) 전부 폐기. 대상 파일 명시."),
        (r"\bgit\s+add\b[^|&;]*(\.env|credentials|\.pem|id_rsa|secret|api[_-]?key)", "ask",
         ".env/credentials/키 파일 스테이징 주의 — 커밋 금지 대상. `.example` 이면 확인 후 진행."),
        # 명령줄 인라인 시크릿 — 2026-08-06 사고: `OPENAI_API_KEY=sk-proj-… python -c "…"` 를
        # 승인했더니 그 키가 settings.local.json 의 allow 에 **평문으로** 박혔다(4개 항목).
        # gitignore 라 GitGuardian 도 CI 도 못 잡아 몇 달을 살았다.
        (r"(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
         r"|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})", "ask",
         "명령줄에 API 키가 들어 있다. 승인하면 이 명령이 통째로 allow 에 평문 저장된다 — "
         "키는 `.env` 에 넣고 명령에서는 빼라(2026-08-06 사고)."),
        (r"(API_?KEY|SECRET(_KEY)?|TOKEN|PASSWORD|PASSWD)\s*=\s*['\"]?[A-Za-z0-9_\-+/=]{16,}", "ask",
         "명령줄에 시크릿 값이 들어 있다. 승인하면 allow 에 평문으로 남는다 — `.env` 를 써라."),
        # 경로를 파일로 넘기면 명령만 봐서는 뭘 지우는지 알 수 없다 — 실제로 이걸로 우회됐다.
        (r"git\s+rm\b[^|&;]*--pathspec-from-file", "ask",
         "일괄 삭제 — 명령에 대상 경로가 안 보인다. 목록 파일 내용을 먼저 출력해 확인하라."),
    ]


# 공용 규칙의 회귀 케이스. shim 의 `check()` 가 **레포 케이스와 함께 반드시 돌린다** —
# 그래야 한쪽 레포가 규칙을 재정의해 공용 보호를 깨뜨리면 그 레포에서 빨개진다.
# ⚠️ 아래 키 모양 문자열은 전부 **가짜 값**이다(형태만 흉내).
_FAKE_SK = "sk-proj-" + "A" * 24
COMMON_CASES = [
    ("psql -c 'DROP TABLE products'", "deny"),
    ("echo 'ALTER TABLE x ADD y'", "deny"),
    ("rm -rf /", "deny"),
    ("rm -rf ~/", "deny"),
    ("rm -rf *", "deny"),
    ("git push --force origin main", "ask"),
    ("git push -f", "ask"),
    ("git reset --hard HEAD~1", "ask"),
    ("git add -A", "ask"),
    ("git add --all && git commit -m x", "ask"),
    ("git add .", "ask"),
    ("git checkout -- .", "ask"),
    ("git restore .", "ask"),
    ("git add .env", "ask"),
    ("git add config/credentials.json", "ask"),
    (f'{_FAKE_SK} python -c "x"', "ask"),
    (f'OPENAI_API_KEY={_FAKE_SK} python -c "x"', "ask"),
    ("GH_TOKEN=ghp_" + "B" * 24 + " gh pr list", "ask"),
    ("AKIA" + "C" * 16 + " aws s3 ls", "ask"),
    ("POPBILL_SECRET_KEY=" + "D" * 20 + " python x.py", "ask"),
    ("git rm --pathspec-from-file=list.txt", "ask"),
    # ── 오탐 방지 (여기가 깨지면 사람이 가드를 통째로 끈다) ────────────
    ("rm -rf build/", None),
    ("rm build/out.js", None),
    ("git add -- src/x.py", None),
    ("git add ./src/orders/", None),          # './경로' 는 명시다
    ("git push origin main", None),
    ("git log --oneline", None),
    ("sed -i '/^OPENAI_API_KEY/d' .env", None),          # 값이 없다
    ('grep -rn "OPENAI_API_KEY" src/', None),
    ("echo 'OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}' >> .env", None),  # 워크플로 형태
    ("gh secret list", None),
    ("psql -c 'SELECT * FROM products LIMIT 5'", None),
]


def decide(cmd, rules):
    """명령 문자열 → (decision, reason) 또는 (None, None). 위→아래 첫 매치."""
    for pat, decision, reason in rules:
        if re.search(pat, cmd, re.IGNORECASE):
            return decision, reason
    return None, None


def run(rules):
    """실제 훅 — stdin JSON 을 읽고 판정만 출력한다(jq 의존 없음)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 → UTF-8 (한글 사유 보존)
    except Exception:
        pass
    try:
        cmd = json.loads(sys.stdin.read()).get("tool_input", {}).get("command", "") or ""
    except Exception:
        sys.exit(0)  # 파싱 실패 = 통과 (가드가 정상 작업을 막지 않는다)
    decision, reason = decide(cmd, rules)
    if decision:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"[가드레일] {reason}",
        }}, ensure_ascii=False))
    sys.exit(0)


def check(rules, extra_cases=(), label="guardrail"):
    """공용 케이스 + 레포 케이스를 **한꺼번에** 검사한다.

    ⚠️ 공용 케이스를 빼고 돌 수 없게 만든 게 핵심이다 — 레포가 규칙 순서를 잘못 이어붙여
       공용 보호가 죽으면 **그 레포의 selftest 에서** 빨개져야 한다.
    """
    failed = []
    for cmd, expected in list(COMMON_CASES) + list(extra_cases):
        got = decide(cmd, rules)[0]
        if got != expected:
            failed.append(f"  {cmd[:70]!r} → 기대 {expected} · 실제 {got}")
    if failed:
        print(f"{label} selftest FAIL ({len(failed)}건)")
        print("\n".join(failed))
        return 1
    n = len(COMMON_CASES) + len(extra_cases)
    print(f"{label} selftest OK ({n} cases · 공용 {len(COMMON_CASES)} + 레포 {len(extra_cases)})")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(check(deny_common() + ask_common(), label="guardrail engine"))
    print("이 파일은 엔진이다 — 레포 shim(.claude/hooks/guardrail.py)이 부른다.", file=sys.stderr)
    sys.exit(0)
