#!/usr/bin/env python3
"""onboard 점검 — PC 도구, 프로젝트, 위키, 저장소가 준비됐는지 확인하고 표로 보고한다.

읽기 전용이다(아무것도 설치·수정하지 않는다). 표준 라이브러리만 쓴다.

  python check_setup.py                       # PC + sources.yaml 전체
  python check_setup.py --sources 경로.yaml   # 대상 목록 파일 지정
  python check_setup.py --structure           # + 프로젝트 구조 점검(sources.yaml 에 structure_check: true 로도 켬)
  python check_setup.py --structure --full    # 구조 밖 파일 전체 목록
  python check_setup.py --structure --deep    # 참조 검사 상한(2000개) 해제
  python check_setup.py --catalog             # + 강의 적용 카탈로그 점검(sources.yaml 에 catalog: true 로도 켬)
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


def check_dup_plugins(reg_path, cfg_path):
    """같은 플러그인 이름이 다른 마켓플레이스로 이중 설치됐는지 본다. 파일이 없거나 형식이 다르면 [](조용히 통과)."""
    try:
        ids = list(json.load(open(reg_path, encoding="utf-8"))["plugins"].keys())
    except Exception:
        return []
    try:
        canon = {p["id"] for p in json.load(open(cfg_path, encoding="utf-8"))["plugins"]}
    except Exception:
        canon = set()
    by_name = {}
    for i in ids:
        if isinstance(i, str) and "@" in i:
            by_name.setdefault(i.split("@", 1)[0], []).append(i)
    notes = []
    for name, group in sorted(by_name.items()):
        if len(group) > 1:
            keep = [g for g in group if g in canon]
            notes.append(" · ".join(group) + (" — plugins.json 정본(마켓플레이스)만 남기세요: " + keep[0] if keep else ""))
    return [("PC", "플러그인 중복 설치", WARN if notes else OK, "; ".join(notes) if notes else "중복 없음")]


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
    rows += check_dup_plugins(reg_path, cfg_path)
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

# ---- 프로젝트 구조 점검(--structure): ai-dev-harness 틀 기준, git 추적 파일만, 읽기 전용 ----
STD_FILES = ["CLAUDE.md", "_brain/WIKI_SCHEMA.md"] + ["docs/" + f for f in (
    "PRD.md", "ROADMAP.md", "ARCHITECTURE.md", "ADR.md", "CONVENTIONS.md", "UI_GUIDE.md", "REFERENCES.md")]
STD_DIRS = ["docs/" + d for d in ("adr", "domains", "features", "guides", "reference", "_archive")] + [
    ".dev/plans", ".dev/research", "_brain/raw", "_brain/wiki"]
DOC_EXT = {".md", ".mdx", ".txt", ".pdf", ".xlsx", ".xls", ".html", ".docx", ".doc", ".pptx", ".csv"}
SKIP_DIRS = {".claude", ".codex", ".github", ".cursor", "node_modules", "vendor", "third_party", "tests", "test",
             "__tests__", "fixtures", "fixture", "testdata", "dist", "build", "migrations", "static", "public", "templates"}
SKIP_ROOT = {"README.md", "AGENTS.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE.md", "SECURITY.md", "requirements.txt", "robots.txt"}
SKIP_BASE = {"CLAUDE.md", "README.md", "AGENTS.md", "requirements.txt", "robots.txt"}  # 하위 폴더의 이 이름들은 소스 옆 설명
STALE_DAYS, TOP_N, DEEP_CAP = 180, 10, 2000


def in_structure(f):
    return f in STD_FILES or any(f.startswith(d + "/") for d in STD_DIRS)


def doc_candidates(files):
    """구조 밖 문서성 파일(제외 규칙 적용). docs/·.dev/·_brain/ 안의 기준 밖 파일도 후보다."""
    out = []
    for f in files:
        parts = f.split("/")
        if os.path.splitext(f)[1].lower() not in DOC_EXT or in_structure(f):
            continue
        if (len(parts) == 1 and f in SKIP_ROOT) or parts[-1] in SKIP_BASE and len(parts) > 1:
            continue
        if any(x in SKIP_DIRS for x in parts[:-1]):
            continue
        out.append(f)
    return out


def git(p, *args):
    return subprocess.run(["git", "-C", p, "-c", "core.quotepath=off", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)


def referenced(p, cands, files):
    """{후보: 자신 외 추적 파일이 경로로 인용하면 True}. git grep -F -f 한 번에 묶음 검사.
    패턴 = 후보의 전체 경로 + 뒤 1~3단계 부분 경로(파일명 포함). 부분 경로는 추적 파일 전체에서 유일할 때만 쓴다
    (index.html 처럼 이름이 여럿이면 foundations/colors.md 처럼 상위 폴더가 붙어 유일해질 때만 인정). 역슬래시 경로도 같이 찾는다.
    ponytail: 부분 경로는 접두 경계를 보지 않는다(xfoo/a.md 도 foo/a.md 로 본다 = 참조됨 쪽 과대, 안전)."""
    import collections
    import tempfile
    tails = collections.Counter(t for f in files for t in {"/".join(f.split("/")[-n:]) for n in (1, 2, 3)})
    pats = collections.defaultdict(set)  # 패턴 -> 후보들
    for f in cands:
        parts = f.split("/")
        for t in {f} | {"/".join(parts[-n:]) for n in (1, 2, 3)}:
            if t == f or tails[t] == 1:
                pats[t].add(f)
                if "/" in t:
                    pats[t.replace("/", "\\")].add(f)
    fd, pf = tempfile.mkstemp()
    os.close(fd)
    try:
        with open(pf, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(sorted(pats)) + "\n")
        out = git(p, "grep", "-F", "-o", "-I", "-f", pf).stdout
    finally:
        os.remove(pf)
    ok = dict.fromkeys(cands, False)
    for line in out.splitlines():
        path, _, m = line.partition(":")
        for f in pats.get(m, ()):
            if f != path:
                ok[f] = True
        for f in pats.get(m.replace("\\", "/"), ()):
            if f != path:
                ok[f] = True
    return ok


def last_modified(p, cands):
    """{파일: 마지막 커밋 epoch}. git log 를 최신부터 훑다 후보를 다 찾으면 중단."""
    left, out, ts = set(cands), {}, 0
    proc = subprocess.Popen(["git", "-C", p, "-c", "core.quotepath=off", "log", "--name-only", "--no-renames", "--format=@%ct"],
                            stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line.startswith("@") and line[1:].isdigit():
            ts = int(line[1:])
        elif line in left:
            out[line] = ts
            left.discard(line)
            if not left:
                break
    proc.kill()
    return out


def classify(p, deep=False):
    """(기준 존재 {경로: bool}, {분류: [파일]}, 상한으로 검사 생략 여부)"""
    import time
    files = [f for f in git(p, "ls-files").stdout.splitlines() if f]
    present = {x: any(f == x or f.startswith(x + "/") for f in files) for x in STD_FILES + STD_DIRS}
    cands = doc_candidates(files)
    res = {"참조됨": [], "낡은 후보": [], "확인": []}
    if not deep and len(cands) > DEEP_CAP:
        res["확인"] = cands
        return present, res, True
    refs = referenced(p, cands, files) if cands else {}
    mt = last_modified(p, [f for f in cands if not refs[f]]) if cands else {}
    now = time.time()
    for f in cands:
        if refs[f]:
            res["참조됨"].append(f)
        elif f in mt and now - mt[f] >= STALE_DAYS * 86400:
            res["낡은 후보"].append(f)
        else:
            res["확인"].append(f)
    return present, res, False


def check_structure(path, full=False, deep=False):
    """([표 행], 상세 텍스트). 읽기 전용: git ls-files·grep·log 만 쓴다."""
    import time
    p = expand(path)
    if not os.path.isdir(os.path.join(p, ".git")):
        return [("구조", path, WARN, "git 저장소 아님(건너뜀)")], ""
    t0 = time.time()
    present, res, capped = classify(p, deep)
    miss = [k for k, v in present.items() if not v]
    n = sum(len(v) for v in res.values())
    lines = [f"### 구조 점검: {path} (로컬 체크아웃 기준 · git 추적 파일 · {time.time() - t0:.1f}초)",
             f"기준 구조 있음 {len(present) - len(miss)}/{len(present)} · 없음: " + (", ".join(miss) if miss else "(없음)")]
    if capped:
        lines.append(f"후보 {n}개가 상한 {DEEP_CAP}개를 넘어 참조·날짜 검사를 생략했다(전부 '확인'). --deep 으로 전체 검사")
    desc = {"참조됨": "구조 밖·참조됨(코드·훅·문서가 인용 — 함부로 이동 금지)",
            "낡은 후보": f"구조 밖·낡은 후보(참조 0건 · {STALE_DAYS}일 이상 미수정)", "확인": "구조 밖·확인(그 외)"}
    for k, v in res.items():
        lines.append(f"- {desc[k]}: {len(v)}개")
        if v:
            dirs = {}
            for f in v:
                d = os.path.dirname(f) or "."
                dirs[d] = dirs.get(d, 0) + 1
            lines.append("  폴더별: " + ", ".join(f"{d}({c})" for d, c in sorted(dirs.items(), key=lambda x: -x[1])[:TOP_N]))
            lines += [f"  · {f}" for f in (v if full else v[:TOP_N])]
            if not full and len(v) > TOP_N:
                lines.append(f"  … 외 {len(v) - TOP_N}개(--full 로 전체)")
    lines.append("삭제·이동·수정은 하지 않는다. 승인 뒤에만.")
    row = f"기준 없음 {len(miss)}개 · 구조 밖 문서 {n}개(참조됨 {len(res['참조됨'])} · 낡은 후보 {len(res['낡은 후보'])} · 확인 {len(res['확인'])})"
    return [("구조", path, OK if not miss and not n else WARN, row)], "\n".join(lines)


# ---- 강의 적용 카탈로그 점검(--catalog): config/harness-catalog.json 의 detect 를 매번 계산, 읽기 전용 ----
SKIP = "건너뜀"
CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "harness-catalog.json")
KINDS = {"file_exists": ("path",), "file_contains": ("path", "pattern"), "plugin_installed": ("id",),
         "setting_present": ("file", "key_path"), "manual": ("question",)}


def _path(p, root, home):
    if p.startswith("~"):
        return os.path.join(home, p[1:].lstrip("/\\"))
    return os.path.join(root or home, p)


def _dig(d, key_path):
    for k in key_path.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def eval_detect(d, root, home):
    """(충족 여부, 비고). 모르는 kind·형식 오류·manual·못 읽음은 전부 False — OK 로 통과시키지 않는다."""
    try:
        kind, a = d["kind"], d["args"]
        if kind not in KINDS:
            return False, f"모르는 detect kind: {kind}"
        if any(not isinstance(a.get(k), str) or not a[k] for k in KINDS[kind]):
            return False, f"{kind} 인자 형식 오류"
        if kind == "manual":
            return False, "사람 확인: " + a["question"]
        if kind == "plugin_installed":
            have = json.load(open(os.path.join(home, ".claude", "plugins", "installed_plugins.json"), encoding="utf-8")).get("plugins", {})
            return a["id"] in have, "" if a["id"] in have else f"플러그인 미설치: {a['id']}"
        if kind == "setting_present":
            if a["file"] not in ("user", "project") or (a["file"] == "project" and not root):
                return False, "setting_present file 형식 오류"
            f = os.path.join(home, ".claude", "settings.json") if a["file"] == "user" else os.path.join(root, ".claude", "settings.json")
            v = _dig(json.load(open(f, encoding="utf-8")), a["key_path"])
            ok = v not in (None, "", [], {}) and (not a.get("contains") or a["contains"].lower() in json.dumps(v, ensure_ascii=False).lower())
            return ok, "" if ok else f"settings {a['key_path']} 없음"
        f = _path(a["path"], root, home)
        if kind == "file_exists":
            return os.path.exists(f), "" if os.path.exists(f) else f"없음: {a['path']}"
        if not os.path.isfile(f):
            return False, f"없음: {a['path']}"
        ok = re.search(a["pattern"], open(f, encoding="utf-8", errors="replace").read(), re.I | re.M) is not None
        return ok, "" if ok else f"{a['path']} 에 '{a['pattern']}' 없음"
    except Exception as e:  # 파일 없음·JSON 오류·정규식 오류·키 누락
        return False, f"판정 불가({type(e).__name__})"


def eval_item(it, root, home):
    """(상태, 비고). 순서: deferred → retire_when → detect(+hold)."""
    if it.get("deferred"):
        return SKIP, "보류(과함): " + str(it["deferred"])
    rw = it.get("retire_when")
    if isinstance(rw, list) and rw and all(eval_detect(d, root, home)[0] for d in rw):
        return SKIP, "졸업(retire_when 충족)"
    det = it.get("detect")
    if not isinstance(det, list) or not det:
        return WARN, "detect 형식 오류(비었거나 배열 아님)"
    res = [eval_detect(d, root, home) for d in det]
    if all(r[0] for r in res):
        return OK, ""
    notes = [r[1] for r in res if not r[0]]
    if it.get("hold"):
        notes.insert(0, "보류: " + str(it["hold"]))
    return WARN, "; ".join(notes)


def check_catalog(cat_path, projects, home=HOME):
    """[(id, 우선순위, 항목, 대상, 상태, 비고)]. 못 읽은 카탈로그·형식 오류는 '확인' 한 줄."""
    try:
        items = json.load(open(cat_path, encoding="utf-8"))["items"]
        assert isinstance(items, list)
    except Exception as e:
        return [("-", "상", "카탈로그", "-", WARN, f"카탈로그를 읽지 못함({type(e).__name__}) — {cat_path}")]
    rows = []
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("id"), str):
            rows.append(("?", "상", "형식 오류 항목", "-", WARN, "id 없음·객체 아님"))
            continue
        base = (it["id"], it.get("priority") or "하", str(it.get("title", ""))[:60])
        if it.get("scope") == "project" and not it.get("deferred"):
            for p in projects:
                root = expand(p)
                st, note = (WARN, "폴더 없음") if not os.path.isdir(root) else eval_item(it, root, home)
                rows.append(base + (os.path.basename(root.rstrip("/\\")) or p, st, note))
        elif it.get("scope") in ("pc", "project"):
            rows.append(base + ("PC" if it["scope"] == "pc" else "(전체)",) + eval_item(it, None, home))
        else:
            rows.append(base + ("-", WARN, "scope 형식 오류(pc|project)"))
    return rows


def report_catalog(rows):
    n = lambda s: sum(1 for r in rows if r[4] == s)
    lines = ["### 강의 적용 카탈로그 (읽기 전용 · apply 는 안내일 뿐 설치·수정하지 않음)",
             "| ID | 우선순위 | 항목 | 대상 | 상태 | 비고 |", "|---|---|---|---|---|---|"]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |" for r in rows]
    lines.append(f"\n전체 {len(rows)} · OK {n(OK)} · 확인 {n(WARN)} · 건너뜀 {n(SKIP)}")
    top = [r for r in rows if r[4] == WARN and r[1] == "상"]
    lines.append(f"우선순위 상 확인 {len(top)}개" + (" (상위 10개)" if len(top) > TOP_N else ""))
    lines += [f"  · {r[0]} {r[2]} @ {r[3]} — {r[5]}" for r in top[:TOP_N]]
    return "\n".join(lines)


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
    structure, details = "--structure" in argv, []
    catalog, projects = "--catalog" in argv, []
    if os.path.exists(src):
        text = open(src, encoding="utf-8").read()
        cfg = parse_sources(text)
        projects = cfg.get("projects", [])
        structure = structure or bool(re.search(r"^structure_check:\s*true", text, re.M | re.I))
        catalog = catalog or bool(re.search(r"^catalog:\s*true", text, re.M | re.I))
        for p in cfg.get("projects", []):
            rows += check_project(p)
            if structure:
                r, detail = check_structure(p, "--full" in argv, "--deep" in argv)
                rows += r
                details.append(detail)
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
    for d in details:
        print()
        print(d)
    if catalog:
        print()
        print(report_catalog(check_catalog(CATALOG, projects)))
        if not projects:
            print("(projects 없음 — 프로젝트 항목은 점검하지 못했다)")


def selftest():
    import shutil
    import tempfile
    for k in [k for k in os.environ if k.startswith("GIT_")]:  # pre-commit 훅의 GIT_DIR·INDEX 가 임시 저장소 검사를 현재 저장소로 새게 한다
        del os.environ[k]
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
        assert in_structure("docs/adr/x.md") and not in_structure("docs/ADOPTION.md")
        assert doc_candidates(["docs/PRD.md", "docs/old.md", "a/README.md", ".claude/x.md", "tests/f.md", "README.md", "src/a.py", "n.txt"]) == ["docs/old.md", "n.txt"]
        if run(["git", "--version"])[0] == 0:
            for k in [k for k in os.environ if k.startswith("GIT_")]:  # git hook 안에서 돌면 GIT_DIR 이 임시 repo 를 가린다
                del os.environ[k]
            run(["git", "-C", d, "init", "-q"])
            open(os.path.join(d, "n.txt"), "w").write("x")
            open(os.path.join(d, "o.md"), "w").write("see n.txt")
            run(["git", "-C", d, "add", "n.txt", "o.md"])
            run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "t"])
            _, res, _ = classify(d)
            assert res["참조됨"] == ["n.txt"] and res["확인"] == ["o.md"], res
            # 경로 기준: (a) 전체 경로 (b) 유일 basename (c) 중복 basename만 인용 -> 참조 아님
            for q in ("docs/a/x.md", "docs/b/x.md", "docs/u.md"):
                os.makedirs(os.path.dirname(os.path.join(d, q)), exist_ok=True)
                open(os.path.join(d, q), "w").write("-")
            open(os.path.join(d, "ref.txt"), "w").write("docs/a/x.md u.md x.md")
            run(["git", "-C", d, "add", "docs", "ref.txt"])
            files = [x for x in run(["git", "-C", d, "ls-files"])[1].split() if x]
            r = referenced(d, ["docs/a/x.md", "docs/b/x.md", "docs/u.md"], files)
            assert r == {"docs/a/x.md": True, "docs/b/x.md": False, "docs/u.md": True}, r
            open(os.path.join(d, "ref.txt"), "w").write(r"docs\b\x.md only x.md")
            assert referenced(d, ["docs/a/x.md", "docs/b/x.md"], files) == {"docs/a/x.md": False, "docs/b/x.md": True}
        assert "합계" in report([("PC", "x", OK, "")])
        reg, cfg = os.path.join(d, "reg.json"), os.path.join(d, "cfg.json")
        json.dump({"plugins": [{"id": "a@m1"}]}, open(cfg, "w"))
        for body, want in (('{"plugins":{"a@m1":[],"a@m2":[],"b@m1":[]}}', WARN), ('{"plugins":{"a@m1":[],"b@m1":[]}}', OK),
                           ('[1,2]', None), ('not json', None)):
            open(reg, "w").write(body)
            r = check_dup_plugins(reg, cfg)
            assert (r[0][2] if r else None) == want, (body, r)
        open(reg, "w").write('{"plugins":{"a@m1":[],"a@m2":[]}}')
        note = check_dup_plugins(reg, cfg)[0][3]
        assert "a@m1 · a@m2" in note and "정본" in note, note
        assert check_dup_plugins(os.path.join(d, "none.json"), cfg) == []
        # 카탈로그: 가짜 홈·가짜 프로젝트로 충족·미충족·모르는 kind·형식 오류·hold·deferred·retire_when
        home, proj = os.path.join(d, "home"), os.path.join(d, "proj")
        os.makedirs(os.path.join(home, ".claude", "plugins")); os.makedirs(os.path.join(proj, ".claude"))
        json.dump({"plugins": {"p@m": []}}, open(os.path.join(home, ".claude", "plugins", "installed_plugins.json"), "w"))
        json.dump({"permissions": {"deny": ["Read(.env)"]}, "hooks": {}}, open(os.path.join(home, ".claude", "settings.json"), "w"))
        open(os.path.join(proj, "a.md"), "w").write("hello Guardrail")
        fe = lambda p: {"kind": "file_exists", "args": {"path": p}}
        fc = lambda p, t: {"kind": "file_contains", "args": {"path": p, "pattern": t}}
        sp = lambda k, c=None: {"kind": "setting_present", "args": {"file": "user", "key_path": k, **({"contains": c} if c else {})}}
        mk = lambda i, det, scope="project", **kw: {"id": i, "scope": scope, "priority": "상", "title": i, "detect": det, **kw}
        cat = {"items": [
            mk("ok", [fe("a.md"), fc("a.md", "guardrail")]),                        # 모두 충족 -> OK (대소문자 무시)
            mk("miss", [fe("a.md"), fe("none.md")]),                                # 하나 미충족 -> 확인
            mk("kind", [{"kind": "cmd", "args": {"x": "1"}}]),                      # 모르는 kind -> 확인
            mk("args", [{"kind": "file_exists", "args": {}}]),                      # 인자 누락 -> 확인
            mk("empty", []), mk("notlist", {"kind": "file_exists"}),                # 형식 오류 -> 확인
            mk("badre", [fc("a.md", "(")]),                                         # 정규식 오류 -> 확인
            mk("man", [fe("a.md"), {"kind": "manual", "args": {"question": "q?"}}]),  # manual -> 확인
            mk("hold", [fe("none.md")], hold="결정 대기"),                          # hold 미충족 -> 확인+보류
            mk("holdok", [fe("a.md")], hold="결정 대기"),                           # hold 라도 충족이면 OK
            mk("def", [fe("a.md")], deferred="과함"),                               # deferred -> 건너뜀(프로젝트별 아닌 1줄)
            mk("ret", [fe("none.md")], retire_when=[fe("a.md")]),                   # retire 충족 -> 건너뜀
            mk("ret2", [fe("none.md")], retire_when=[fe("none.md")]),               # retire 미충족 -> detect 평가
            mk("plug", [{"kind": "plugin_installed", "args": {"id": "p@m"}}], "pc"),
            mk("plug2", [{"kind": "plugin_installed", "args": {"id": "q@m"}}], "pc"),
            mk("set", [sp("permissions.deny", "read(.env)")], "pc"),
            mk("sethooks", [sp("hooks")], "pc"),                                    # 빈 {} 는 없음
            mk("home", [fe("~/.claude/settings.json")], "pc"),
            {"id": "noscope", "detect": [fe("a.md")]}, 5,                           # scope 없음·객체 아님 -> 확인
        ]}
        cp = os.path.join(d, "cat.json")
        json.dump(cat, open(cp, "w"))
        got = {r[0]: r[4:] for r in check_catalog(cp, [proj], home)}
        want = {"ok": OK, "miss": WARN, "kind": WARN, "args": WARN, "empty": WARN, "notlist": WARN, "badre": WARN, "man": WARN,
                "hold": WARN, "holdok": OK, "def": SKIP, "ret": SKIP, "ret2": WARN, "plug": OK, "plug2": WARN, "set": OK,
                "sethooks": WARN, "home": OK, "noscope": WARN, "?": WARN}
        assert {k: v[0] for k, v in got.items()} == want, got
        assert "모르는 detect kind" in got["kind"][1] and "보류: 결정 대기" in got["hold"][1] and "사람 확인" in got["man"][1], got
        rows = check_catalog(cp, [proj, os.path.join(d, "nodir")], home)
        assert sum(1 for r in rows if r[0] == "ok") == 2 and any(r[3] == "nodir" and r[4] == WARN for r in rows)
        # 못 읽은 카탈로그·형식 오류는 OK 가 아니라 확인
        for bad in (os.path.join(d, "none.json"), cp + ".x"):
            open(cp + ".x", "w").write('{"items": 3}')
            r = check_catalog(bad, [proj], home)
            assert len(r) == 1 and r[0][4] == WARN, r
        open(cp + ".x", "w").write("not json")
        assert check_catalog(cp + ".x", [], home)[0][4] == WARN
        txt = report_catalog(rows)
        assert f"전체 {len(rows)} · OK " in txt and "건너뜀" in txt and "우선순위 상 확인" in txt
        many = [(f"i{n}", "상", "t", "p", WARN, "") for n in range(12)]
        assert report_catalog(many).count("  · i") == TOP_N
        # 실제 카탈로그: 알려진 kind·필수 인자·id 유일·상태 필드 없음(오타가 조용히 '확인'으로 남는 것을 막는다)
        items = json.load(open(CATALOG, encoding="utf-8"))["items"]
        assert len({i["id"] for i in items}) == len(items) and items
        for i in items:
            assert i["scope"] in ("pc", "project") and i["detect"] and not {"status", "status_note"} & set(i), i["id"]
            for x in i["detect"] + (i.get("retire_when") or []):
                assert x["kind"] in KINDS and all(k in x["args"] for k in KINDS[x["kind"]]), (i["id"], x)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("onboard check_setup selftest OK")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main(sys.argv[1:])
