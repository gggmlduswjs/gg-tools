#!/usr/bin/env python3
"""onboard 점검 — PC 도구, 프로젝트, 위키, 저장소가 준비됐는지 확인하고 표로 보고한다.

읽기 전용이다(아무것도 설치·수정하지 않는다). 표준 라이브러리만 쓴다.

  python check_setup.py                       # PC + sources.yaml 전체
  python check_setup.py --sources 경로.yaml   # 대상 목록 파일 지정
  python check_setup.py --selftest

대상 목록 기본 위치: ~/.claude/onboard/sources.yaml (예시: ../config/sources.example.yaml)
"""
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
OK, WARN, FAIL = "OK", "확인", "없음"


def parse_sources(text):
    """키 아래 '- 값' 목록만 읽는 최소 파서(PyYAML 불필요). {키: [값, ...]}"""
    out, key = {}, None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_]+):\s*$", line)
        if m:
            key = m.group(1)
            out[key] = []
            continue
        m = re.match(r"^\s*-\s+(.+)$", line)
        if m and key:
            out[key].append(m.group(1).strip().strip("'\""))
    return out


def expand(p):
    return os.path.expanduser(p)


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # 도구가 없거나 시간 초과
        return 1, str(e)


def check_pc():
    rows = []
    for tool, arg in (("git", "--version"), ("gh", "--version"), ("python", "--version"), ("claude", "--version")):
        code, out = run([tool, arg])
        rows.append(("PC", tool, OK if code == 0 else FAIL, out.strip().splitlines()[0] if code == 0 and out.strip() else "설치 필요(새 PowerShell 창에서 다시 확인)"))
    code, out = run(["gh", "auth", "status"])
    rows.append(("PC", "GitHub 로그인", OK if code == 0 else FAIL, "" if code == 0 else "gh auth login 은 직접 실행"))
    # 플러그인: ~/claude/plugins.json 대 설치 등록부
    cfg_path = os.path.join(HOME, "claude", "plugins.json")
    reg_path = os.path.join(HOME, ".claude", "plugins", "installed_plugins.json")
    if not os.path.exists(cfg_path):
        rows.append(("PC", "gg-tools 클론", FAIL, "gh repo clone gggmlduswjs/gg-tools ~/claude"))
        return rows
    rows.append(("PC", "gg-tools 클론", OK, cfg_path))
    try:
        want = [p["id"] for p in json.load(open(cfg_path, encoding="utf-8"))["plugins"]]
        have = set(json.load(open(reg_path, encoding="utf-8")).get("plugins", {}).keys())
        missing = [w for w in want if w not in have]
        rows.append(("PC", f"플러그인 {len(want)}개", OK if not missing else WARN,
                     "모두 설치됨" if not missing else "미설치: " + ", ".join(missing) + " → pwsh ~/claude/bootstrap.ps1"))
    except Exception as e:
        rows.append(("PC", "플러그인", WARN, f"등록부를 읽지 못함({e})"))
    engine = os.path.join(HOME, "claude", "gg-skills", "hooks", "guardrail.py")
    if os.path.exists(engine):
        code, out = run([sys.executable, engine, "--selftest"])
        rows.append(("PC", "위험 명령 차단 엔진", OK if code == 0 else FAIL, out.strip().splitlines()[-1] if out.strip() else ""))
    else:
        rows.append(("PC", "위험 명령 차단 엔진", FAIL, "gg-tools 를 ~/claude 에 받아야 함"))
    return rows


def check_project(path):
    p = expand(path)
    if not os.path.isdir(p):
        return [("프로젝트", path, FAIL, "폴더 없음")]
    notes, status = [], OK
    if not os.path.isdir(os.path.join(p, ".git")):
        notes.append("git 저장소 아님"); status = WARN
    for rel, label in (("CLAUDE.md", "CLAUDE.md"), (os.path.join("docs", "PRD.md"), "docs/PRD.md"),
                       (os.path.join(".claude", "settings.json"), ".claude/settings.json")):
        if not os.path.exists(os.path.join(p, rel)):
            notes.append(f"{label} 없음"); status = WARN
    cm = os.path.join(p, "CLAUDE.md")
    if os.path.exists(cm):
        n = sum(1 for _ in open(cm, encoding="utf-8", errors="replace"))
        if n > 200:
            notes.append(f"CLAUDE.md {n}줄(200줄 이하 권장)"); status = WARN
    return [("프로젝트", path, status, "; ".join(notes) if notes else "틀 구성 확인")]


def check_wiki(path):
    p = expand(path)
    if not os.path.isdir(p):
        return [("위키", path, FAIL, "폴더 없음 — gh repo clone 또는 wiki-template 로 생성")]
    if not os.path.exists(os.path.join(p, "WIKI_SCHEMA.md")):
        return [("위키", path, FAIL, "WIKI_SCHEMA.md 없음(위키 폴더가 아님)")]
    seen, pending = "", []
    for dp, _, fns in os.walk(os.path.join(p, "wiki")):
        for fn in fns:
            if fn.endswith(".md"):
                seen += open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read() + "\n"
    for dp, _, fns in os.walk(os.path.join(p, "raw")):
        for fn in fns:
            if fn == ".gitkeep":
                continue
            rel = os.path.relpath(os.path.join(dp, fn), p).replace("\\", "/")
            if rel not in seen and fn not in seen:
                pending.append(rel)
    return [("위키", path, OK if not pending else WARN,
             "raw 전부 반영됨" if not pending else f"ingest 대기 {len(pending)}개")]


def check_repo(name):
    code, out = run(["gh", "api", f"repos/{name}", "-q", ".full_name"])
    return [("저장소", name, OK if code == 0 else FAIL, "" if code == 0 else "접근 불가(이름·로그인·권한 확인)")]


def check_doc(path):
    p = expand(path)
    return [("문서", path, OK if os.path.isdir(p) else FAIL, "" if os.path.isdir(p) else "폴더 없음")]


def report(rows):
    lines = ["| 구분 | 대상 | 상태 | 비고 |", "|---|---|---|---|"]
    for kind, name, st, note in rows:
        lines.append(f"| {kind} | {name} | {st} | {note} |")
    bad = sum(1 for r in rows if r[2] == FAIL)
    chk = sum(1 for r in rows if r[2] == WARN)
    lines.append(f"\n합계: OK {len(rows) - bad - chk} · 확인 {chk} · 없음 {bad}")
    return "\n".join(lines)


def main(argv):
    src = os.path.join(HOME, ".claude", "onboard", "sources.yaml")
    if "--sources" in argv:
        src = expand(argv[argv.index("--sources") + 1])
    rows = check_pc()
    if os.path.exists(src):
        cfg = parse_sources(open(src, encoding="utf-8").read())
        for p in cfg.get("projects", []):
            rows += check_project(p)
        for w in cfg.get("wikis", []):
            rows += check_wiki(w)
        for r in cfg.get("repos", []):
            rows += check_repo(r)
        for d in cfg.get("docs", []):
            rows += check_doc(d)
    else:
        rows.append(("대상 목록", src, WARN, "없음 — sources.example.yaml 을 복사해 내 값으로 작성"))
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(report(rows))


def selftest():
    import shutil
    import tempfile
    t = "projects:\n  - ~/a  # 주석\nrepos:\n  - x/y\n\nwikis:\n"
    got = parse_sources(t)
    assert got == {"projects": ["~/a"], "repos": ["x/y"], "wikis": []}, got
    d = tempfile.mkdtemp()
    try:
        assert check_project(d)[0][2] == WARN
        assert check_project(os.path.join(d, "none"))[0][2] == FAIL
        assert check_wiki(d)[0][2] == FAIL
        os.makedirs(os.path.join(d, "raw")); os.makedirs(os.path.join(d, "wiki"))
        open(os.path.join(d, "WIKI_SCHEMA.md"), "w").close()
        open(os.path.join(d, "raw", "a.md"), "w").close()
        r = check_wiki(d)[0]
        assert r[2] == WARN and "1개" in r[3], r
        assert "합계" in report([("PC", "x", OK, "")])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("onboard check_setup selftest OK (7 cases)")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main(sys.argv[1:])
