#!/usr/bin/env python3
"""onboard 점검 — PC 도구, 프로젝트, 위키, 저장소가 준비됐는지 확인하고 표로 보고한다.

읽기 전용이다(아무것도 설치·수정하지 않는다). 표준 라이브러리만 쓴다.

  python check_setup.py                       # PC + sources.yaml 전체
  python check_setup.py --sources 경로.yaml   # 대상 목록 파일 지정
  python check_setup.py --structure           # + 프로젝트 구조 점검(sources.yaml 에 structure_check: true 로도 켬)
  python check_setup.py --structure --full    # 구조 밖 파일 전체 목록
  python check_setup.py --structure --deep    # 참조 검사 상한(2000개) 해제
  python check_setup.py --catalog             # + 강의 적용 카탈로그 점검(sources.yaml 에 catalog: true 로도 켬)
  python check_setup.py --adopt <경로|프로젝트이름>   # 기존 프로젝트 개편 계획서 초안(마크다운, stdout). --min-files N · --out 파일
  python check_setup.py --impact <경로|문자열> [--project <경로|이름>] [--full] [--out 파일]   # 참조 수 집계(위험 판정 아님)
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


ONBOARD_CFG = ".onboard.yaml"  # 프로젝트 루트의 설정(사람/PR 로만 만든다. 스킬은 읽기만). 키 아래 '- 값  # 이유' 목록(parse_sources 형식)
#   skip_structure: 의도적으로 두지 않는 기준 구조(예 docs/guides) — 보고에 '제외'와 사유로 표시


def load_pcfg(p):
    try:
        return parse_sources(open(os.path.join(p, ONBOARD_CFG), encoding="utf-8").read())
    except OSError:
        return {}


def skip_reasons(p):
    """skip_structure 항목 → 사유('# ' 뒤 주석, 없으면 ''). parse_sources 가 주석을 버려 원문에서 다시 읽는다."""
    out = {}
    try:
        txt = open(os.path.join(p, ONBOARD_CFG), encoding="utf-8").read()
    except OSError:
        return out
    for k in load_pcfg(p).get("skip_structure", []):
        m = re.search(r"^\s*-\s*" + re.escape(k) + r"\s*(?:#\s*(.*))?$", txt, re.M)
        out[k] = (m.group(1) or "").strip() if m else ""
    return out


def tracked(p):
    try:
        return [f for f in git(p, "ls-files").stdout.splitlines() if f]
    except Exception:  # git 없음
        return []


def locate(root, rel, files=None):
    """rel 이 없으면 추적 파일 중 같은 이름이 유일할 때 그 위치를 돌려준다(폴더 개명 뒤 오탐 방지). 없으면 None."""
    if os.path.exists(os.path.join(root, rel)):
        return rel
    base = os.path.basename(rel)
    if not os.path.splitext(base)[1]:
        return None
    hits = [f for f in (tracked(root) if files is None else files) if os.path.basename(f) == base]
    return hits[0] if len(hits) == 1 else None


def check_structure(path, full=False, deep=False):
    """([표 행], 상세 텍스트). 읽기 전용: git ls-files·grep·log 만 쓴다."""
    import time
    p = expand(path)
    if not os.path.isdir(os.path.join(p, ".git")):
        return [("구조", path, WARN, "git 저장소 아님(건너뜀)")], ""
    t0 = time.time()
    present, res, capped = classify(p, deep)
    skip_why = skip_reasons(p)
    skip = set(skip_why)
    miss = [k for k, v in present.items() if not v and k not in skip]
    n = sum(len(v) for v in res.values())
    lines = [f"### 구조 점검: {path} (로컬 체크아웃 기준 · git 추적 파일 · {time.time() - t0:.1f}초)",
             f"기준 구조 있음 {sum(present.values())}/{len(present)} · 없음: " + (", ".join(miss) if miss else "(없음)") +
             (f" · 제외 {len(skip & set(present))}개(.onboard.yaml 선언)" if skip else "")]
    lines += [f"제외: {k} — {skip_why[k] or '사유 미기재'}" for k in present if k in skip and not present[k]]
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
        moved = locate(root, a["path"]) if root and not os.path.exists(f) and not a["path"].startswith("~") else None
        if moved:  # 폴더 개명·이동 뒤에도 같은 이름 파일이 유일하면 그 위치로 판정(검사기 경로 하드코딩 오탐 방지)
            f = os.path.join(root, moved)
        if kind == "file_exists":
            return os.path.exists(f), ("" if not moved else f"실제 위치 {moved}") if os.path.exists(f) else f"없음: {a['path']}"
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
        return OK, "; ".join(r[1] for r in res if r[1])  # 비고: 자동 탐색한 '실제 위치'만
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


# ---- 기존 프로젝트 개편: --adopt(계획서 초안) · --impact(참조 수 집계). 읽기 전용, 결과는 stdout(--out 은 새 파일만) ----
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".java", ".kt", ".go", ".rs", ".cs", ".rb", ".php", ".sh", ".ps1"}
RULE_RE = re.compile(r"브랜치|\bPR\b|머지|\bmerge|운영|금지|⛔|Linear|정본|승인|worktree|force|--apply|--no-verify|origin/main", re.I)
UNK = "미확인"
MARK = "[ 승인 지점: ____ · 검증: ____ · 롤백: ____ ]"
MAP_MARK = "[ 사람이 매핑표 작성 ]"


def resolve_project(arg, projects):
    """경로면 그대로, 구분자 없는 이름이면 sources.yaml projects 의 폴더 이름과 대조. 못 찾으면 None."""
    if not re.search(r"[/\\~]", arg):
        for q in projects:
            if os.path.basename(expand(q).rstrip("/\\")).lower() == arg.lower() and os.path.isdir(expand(q)):
                return expand(q)
    p = expand(arg)
    return p if os.path.isdir(p) else None


def write_out(path, text, project):
    """새 파일만 쓴다. 이미 있거나 대상 프로젝트 안이면 거부(None=성공, 문자열=거부 사유)."""
    out, root = os.path.realpath(path), os.path.realpath(project)
    if os.path.exists(out):
        return f"이미 있어 덮어쓰지 않는다: {path}"
    try:
        if os.path.commonpath([out, root]) == root:
            return f"대상 프로젝트 안에는 쓰지 않는다: {path}"
    except ValueError:  # 다른 드라이브 = 프로젝트 밖
        pass
    try:
        with open(out, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except OSError as e:
        return f"쓰지 못했다({e}): {path}"


def read_lines(p, rel):
    try:
        return open(os.path.join(p, rel), encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return None


def nested_stale_titles(p, rel, lines, dirs=()):
    """제목(첫 # 줄)의 경로 토큰 중 루트·그 CLAUDE.md 폴더 기준으로도, 추적 폴더의 뒷부분으로도 없는 것(낡은 이름 의심)."""
    head = next((x for x in lines if x.startswith("#")), "")
    base = os.path.dirname(rel)
    toks = re.findall(r"[\w.\-]+(?:/[\w.\-]+)*/|[\w.\-]+(?:/[\w.\-]+)+", head)
    return [t for t in toks if not (os.path.exists(os.path.join(p, t)) or os.path.exists(os.path.join(p, base, t)) or
                                    any(d == t.rstrip("/") or d.endswith("/" + t.rstrip("/")) for d in dirs))]


def code_layout(p, files):
    """(상위 폴더 표 행, 코드 기준 폴더, 모듈 폴더 {폴더: (코드 파일 수, 줄 수)}). 줄 수는 코드 파일만."""
    cl = {}
    for f in files:
        if os.path.splitext(f)[1].lower() in CODE_EXT:
            try:
                cl[f] = open(os.path.join(p, f), "rb").read().count(b"\n")
            except OSError:
                pass
    top = {}
    for f in files:
        d = f.split("/")[0] if "/" in f else "(루트 파일)"
        t = top.setdefault(d, [0, 0, 0])
        t[0] += 1
        if f in cl:
            t[1] += 1
            t[2] += cl[f]
    base = ""
    if any(f.startswith("src/") for f in cl):
        base = "src"
        while True:  # 코드 80% 이상이 한 하위 폴더에 있고 이 폴더에 직속 코드가 없으면 한 단계 내려간다
            pre = base + "/"
            sub = {}
            for f in cl:
                if f.startswith(pre):
                    seg = f[len(pre):].split("/", 1)
                    sub[seg[0] if len(seg) > 1 else ""] = sub.get(seg[0] if len(seg) > 1 else "", 0) + 1
            tot = sum(sub.values())
            best = max((k for k in sub if k), key=lambda k: sub[k], default=None)
            if best and not sub.get("") and sub[best] >= 0.8 * tot:
                base += "/" + best
            else:
                break
    mods = {}
    pre = base + "/" if base else ""
    for f, n in cl.items():
        if f.startswith(pre) and "/" in f[len(pre):]:
            m = pre + f[len(pre):].split("/")[0]
            e = mods.setdefault(m, [0, 0])
            e[0] += 1
            e[1] += n
    if not base:  # src 가 없으면 코드가 든 최상위 폴더가 모듈 후보
        mods = {k: (v[1], v[2]) for k, v in top.items() if v[1] and k != "(루트 파일)"}
    return sorted(top.items(), key=lambda x: -x[1][0]), base, mods


def settings_hooks(p):
    """{이벤트: 항목 수}. settings.json 이 없거나 깨지면 None."""
    try:
        h = json.load(open(os.path.join(p, ".claude", "settings.json"), encoding="utf-8")).get("hooks", {})
        return {k: sum(len(x.get("hooks", [])) for x in v if isinstance(x, dict)) for k, v in h.items()}
    except Exception:
        return None


def build_adopt(path, min_files=10):
    import datetime
    p = expand(path)
    name = os.path.basename(os.path.realpath(p).rstrip("/\\"))
    files = [f for f in git(p, "ls-files").stdout.splitlines() if f]
    if not files:
        return f"# {name} 적용 계획서 초안\n\ngit 추적 파일을 읽지 못했다(git 저장소 아님?) — {UNK}.\n"
    branch = git(p, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or UNK
    fset = set(files)
    L = [f"# {name} -> ai-dev-harness 적용 계획서 초안 (자동 생성 · 읽기 전용)", "",
         f"생성일 {datetime.date.today()} · 대상 `{os.path.normpath(p)}` · 브랜치 {branch} · git 추적 파일 {len(files)}개",
         "이 문서는 `check_setup.py --adopt` 가 만든 초안이다. 숫자는 `git ls-files`·파일 읽기 결과이고, 모르는 것은 추측하지 않고 "
         f"'{UNK}' 로 적는다. 사람이 읽고 고친 뒤 정본으로 삼는다.", ""]
    # (0) 전제
    L += ["## 0. 전제 요약", "",
          "- 이 스크립트는 파일을 만들거나 고치지 않는다(대상 프로젝트 안에는 쓰지 않는다). 아래는 초안이다.",
          "- **이름·폴더 변경과 로직 변경은 스킬이 실행하지 않는다.** 질문서 Q6 에서 사람이 허용했을 때만 순서를 제안하며, 먼저 `--impact`(참조 수 집계) 로 영향을 본 뒤 사람이 결정한다. "
          "참조 수는 위험 판정이 아니다.",
          f"- 이 스크립트가 모르는 것: 운영 서버 유닛·cron, DB 에 경로·모듈명이 저장되는지, Linear 이슈 안의 경로, 테스트 커버리지, 죽은 코드 — 전부 {UNK}.",
          "- 프로젝트 정본 규칙(CLAUDE.md·AGENTS.md)이 harness 지침보다 우선한다(4장 인용).", ""]
    # (1) 현황
    L += ["## 1. 현황", "", "### 1-1. 구조(--structure 와 같은 판정)"]
    present, res, capped = classify(p)
    miss = [k for k, v in present.items() if not v]
    L.append(f"- 기준 구조 있음 {len(present) - len(miss)}/{len(present)} · 없음: " + (", ".join(miss) if miss else "(없음)"))
    L.append(f"- 구조 밖 문서 {sum(len(v) for v in res.values())}개: 참조됨 {len(res['참조됨'])} (코드·훅·문서가 경로 인용 — 이동 금지) · "
             f"낡은 후보 {len(res['낡은 후보'])} · 확인 {len(res['확인'])}" + (f" · 후보 상한({DEEP_CAP}) 초과로 참조 검사 생략" if capped else ""))
    L.append(f"- docs/ 추적 파일 {sum(1 for f in files if f.startswith('docs/'))}개 · 루트 PRODUCT.md 등 PRD 후보는 {UNK}(사람이 판단)")
    L += ["", "### 1-2. 강의 적용 카탈로그: 이 프로젝트 우선순위 상 `확인`"]
    rows = [r for r in check_catalog(CATALOG, [p]) if r[3] == name and r[4] == WARN and r[1] == "상"]
    L.append(f"- {len(rows)}개" + ("" if rows else " (없음)"))
    L += [f"  - {r[0]} {r[2]} — {r[5]}" for r in rows]
    L += ["", "### 1-3. 지침 파일"]
    L += ["| 파일 | 줄 수 | 비고 |", "|---|---|---|"]
    for rel in ("CLAUDE.md", "AGENTS.md"):
        ls = read_lines(p, rel)
        L.append(f"| {rel} | {len(ls)} | {'200줄 초과' if len(ls) > 200 else '200줄 이내'} |" if ls is not None else f"| {rel} | - | 없음 |")
    L += ["", "### 1-4. .claude/ 현황 (git 추적 기준)"]
    cf = [f for f in files if f.startswith(".claude/")]
    for sub in ("rules", "skills", "agents", "hooks"):
        fs = [f for f in cf if f.startswith(f".claude/{sub}/")]
        L.append(f"- {sub}: 파일 {len(fs)}개" + (" — " + ", ".join(sorted({f.split('/')[2] for f in fs})[:8]) if fs else ""))
    sh = settings_hooks(p)
    if not os.path.exists(os.path.join(p, ".claude", "settings.json")):
        L.append("- settings.json: 없음")
    elif sh is None:
        L.append(f"- settings.json: 읽지 못함({UNK})")
    else:
        L.append("- settings.json: hooks " + (", ".join(f"{k} {v}개" for k, v in sh.items()) or "없음"))
    L += ["", "### 1-5. 새 hook 과 경로 충돌 검토"]
    hooks = {os.path.basename(f) for f in cf if f.startswith(".claude/hooks/")}
    has_scripts = any(f.startswith("scripts/") for f in files)
    L.append(f"- CLAUDE.md 점검 `.claude/hooks/claude-md-check.py`: {'이미 있음' if 'claude-md-check.py' in hooks else '없음'}")
    L.append(f"- 그 shim 이 호출할 `scripts/check-claude-md.py`: {'있음' if 'scripts/check-claude-md.py' in fset else '없음'} · `scripts/` 폴더: "
             f"{'있음' if has_scripts else '없음'}" + ("" if has_scripts else " (`_scripts/` " + ("있음" if any(f.startswith("_scripts/") for f in files) else "없음") +
             ") — shim 은 예외를 삼키므로 폴더가 없으면 조용히 아무것도 안 한다(조용한 실패). 점검기 위치는 사람이 결정"))
    tdd = sorted(h for h in hooks if "tdd" in h.lower())
    cdx = sorted(os.path.basename(f) for f in files if f.startswith(".codex/hooks/") and "tdd" in f.lower())
    L.append("- TDD guard 류 Claude hook: " + (", ".join(tdd) or "없음") + " · `.codex/hooks` 의 TDD: " + (", ".join(cdx) or "없음"))
    L.append(f"- guardrail: {'`.claude/hooks/guardrail.py` 이미 있음 — 공용 엔진 shim 인지 사람이 확인' if 'guardrail.py' in hooks else '없음'}")
    if sh is not None:
        L.append(f"- SessionStart 항목 수 {sh.get('SessionStart', 0)}개 — 새 hook 은 `async: true` 로 추가해 세션 시작을 늦추지 않는다(기존 동기 항목이 있으면 확인)")
    pol = []
    for rel in ("CLAUDE.md", "AGENTS.md"):
        for i, ln in enumerate(read_lines(p, rel) or [], 1):
            m = re.search(r"TDD", ln, re.I)
            if m and re.search(r"금지|않는다|만들지|하지 마", ln):
                pol.append(f"{rel}:{i}: …{ln[max(0, m.start() - 60):m.end() + 40].strip()}…")
    L += [f"- 프로젝트 정책 충돌 가능(TDD): `{x}`" for x in pol] or ["- TDD 관련 금지 문구: 발견 못 함(없다는 보장은 아님)"]
    # (2) 레이아웃
    top, base, mods = code_layout(p, files)
    L += ["", "## 2. 코드·폴더 레이아웃 요약", "", "| 상위 폴더 | 추적 파일 | 코드 파일 | 코드 줄 수 |", "|---|---|---|---|"]
    L += [f"| {k} | {v[0]} | {v[1]} | {v[2]} |" for k, v in top[:15]]
    if len(top) > 15:
        L.append(f"| … 외 {len(top) - 15}개 폴더 | | | |")
    L += ["", f"- 코드 기준 폴더(자동 추정): `{base or '(저장소 루트)'}`"]
    rec = any(f.startswith(("src/backend/", "src/frontend/")) for f in files)
    L.append("- harness 권장 레이아웃(`src/backend`·`src/frontend`·도메인 폴더): " + ("있음" if rec else "없음 — 어긋남") +
             ("" if rec else f" → {MAP_MARK} (현재 경로 ↔ 권장 경로, 이동 여부는 `--impact` 후 사람이 결정)"))
    fe = sorted({os.path.dirname(f) or "." for f in files if os.path.basename(f) == "package.json"})
    L.append("- 프론트 후보(package.json 위치): " + (", ".join(fe[:6]) if fe else "없음") + (f" → {MAP_MARK}" if fe and not rec else ""))
    L.append("- 위 폴더 이름·위치를 바꾸라는 뜻이 아니다. 어긋남은 매핑표(문서)로 대응하고 이동은 별도 결정이다.")
    # (3) 도메인 CLAUDE.md
    L += ["", "## 3. 도메인별 CLAUDE.md 후보", "",
          f"기준: 코드 모듈 폴더(`{base or '루트'}` 아래)의 코드 파일 수 ≥ {min_files} 이고 그 폴더에 추적되는 CLAUDE.md 가 없음(`--min-files N` 로 조정). 담을 규칙은 사람이 정한다.", "",
          "| 폴더 | 코드 파일 | 코드 줄 수 | CLAUDE.md |", "|---|---|---|---|"]
    cand = [(m, v) for m, v in sorted(mods.items(), key=lambda x: -x[1][0]) if v[0] >= min_files and f"{m}/CLAUDE.md" not in fset]
    L += [f"| {m} | {v[0]} | {v[1]} | 없음 → 후보 |" for m, v in cand] or ["| (없음) | | | |"]
    L.append(f"\n후보 {len(cand)}개 / 모듈 폴더 {len(mods)}개. 임계 미만(후보 아님): " + (", ".join(f"{m}({v[0]})" for m, v in sorted(mods.items(), key=lambda x: -x[1][0])
             if v[0] < min_files and f"{m}/CLAUDE.md" not in fset) or "(없음)"))
    dirs = {"/".join(f.split("/")[:i]) for f in files for i in range(1, f.count("/") + 1)}
    nested = sorted(f for f in files if f.endswith("CLAUDE.md") and f != "CLAUDE.md")
    L += ["", f"기존 하위 CLAUDE.md {len(nested)}개:"]
    for rel in nested:
        ls = read_lines(p, rel) or []
        st = nested_stale_titles(p, rel, ls, dirs)
        L.append(f"- {rel}: {len(ls)}줄" + (" (200줄 초과)" if len(ls) > 200 else "") +
                 (f" · 제목의 경로 {', '.join('`' + t + '`' for t in st)} 가 존재하지 않음 → 낡은 이름 의심(사람이 확인)" if st else ""))
    # (4) 규칙 인용
    L += ["", "## 4. 프로젝트 규칙 인용 (이 계획의 제약)", "",
          "키워드(브랜치·PR·머지·운영·금지·Linear·정본·승인 등)가 든 줄을 그대로 옮겼다. 줄 번호는 현재 체크아웃 기준.", ""]
    nq = 0
    for rel in ("CLAUDE.md", "AGENTS.md"):
        ls = read_lines(p, rel)
        if ls is None:
            L.append(f"- {rel}: 없음")
            continue
        hit = [(i, x) for i, x in enumerate(ls, 1) if RULE_RE.search(x)]
        nq += len(hit)
        L.append(f"### {rel} ({len(hit)}줄)")
        L += [f"> {rel}:{i}: {x.strip()[:300]}" for i, x in hit[:60]]
        if len(hit) > 60:
            L.append(f"… 외 {len(hit) - 60}줄(원문 확인)")
    L.append(f"\n인용 합계 {nq}줄")
    # (5) PR 순서
    L += ["", "## 5. 단계별 PR 순서 골격 (의존 관계 제안일 뿐 — 일정·진행·담당은 프로젝트 정본/Linear)", "",
          "공통: 작업 브랜치 → 검증 → PR → 명시 승인된 merge. 이 스크립트는 머지하지 않는다. 한 PR = 한 변경(동작 보존과 동작 변경을 섞지 않는다).", ""]
    for n, t in (("① CLAUDE.md 슬림화", "도메인 한정 내용을 하위 CLAUDE.md 로 내리고(3장) 루트엔 포인터만. 낡은 하위 제목·경로 현행화"),
                 ("② docs 틀", "기준 구조(1-1 '없음' 목록)를 추가만 한다. 기존 docs 파일을 이동·삭제하지 않는다(코드가 읽는 파일일 수 있음 — '참조됨')"),
                 ("③ 위키 기반 문서 채우기", "PRD·ROADMAP·ARCHITECTURE·ADR 초안. **원본 위치는 사람이 지정**: `____`. 제품 범위·결정은 AI 가 단정하지 않는다"),
                 ("④ .claude hook", "CLAUDE.md 점검 hook 등(1-5 충돌 검토 반영). 프로젝트 정책과 충돌하는 hook 은 결정 전 제외"),
                 ("⑤ 이름·폴더 변경 (별도)", "**위험: 참조·서버·배포·DB 에 저장된 경로가 깨질 수 있다.** `--impact` 로 영향 분석 후 사람이 결정. 이 스크립트는 실행하지 않는다(질문서 Q6 에서 허용했을 때만 순서 제안). 결정 시 항목마다 별도 PR"),
                 ("⑥ 리팩토링 트랙 (분리)", "하네스 문서·hook PR 과 별도 트랙. 안전망(테스트) 확인 후 사람이 범위를 정한다. 로직 변경은 스크립트가 실행하지 않는다")):
        L += [f"### {n}", f"- 내용: {t}", f"- {MARK}", ""]
    # (6) 질문
    L += ["## 6. 사람이 결정할 질문 (자동으로 알 수 없는 것)", "",
          f"1. 운영 서버의 systemd 유닛·cron·EXE 가 이 저장소의 모듈·경로를 직접 부르는가? ({UNK} — 이름·폴더 변경 판단의 핵심)",
          f"2. DB 에 파일 경로·모듈 경로가 저장되는가? ({UNK})",
          f"3. Linear 이슈·PR 본문에 경로가 인용돼 있는가? ({UNK} — Linear 를 조회하지 않았다)",
          "4. 문서·구조 개편을 프로젝트의 작업 단위 규칙(4장)에 어떻게 맞출까(PR 여러 개를 한 묶음으로 볼지)?",
          "5. docs 틀에서 코드가 읽는 기존 문서('참조됨')를 어떻게 분류할까(그대로 두고 표기 vs 이동)?"]
    if pol:
        L.append("6. 프로젝트 정책이 TDD 관련 도구를 금지한 것으로 보인다(1-5). harness 의 TDD guard 를 넣을지, 정책을 고칠지?")
    if not has_scripts:
        L.append("7. 점검기 위치 `scripts/` 폴더가 없다. 만들지, 기존 폴더에 두고 shim 경로를 바꿀지?")
    L.append(f"8. 이 저장소에서 가장 먼저 줄일 지침은 무엇인가? (CLAUDE.md {len(read_lines(p, 'CLAUDE.md') or [])}줄 — 줄 수보다 도메인 한정 내용이 있는지가 기준)")
    return "\n".join(L) + "\n"


def impact_cat(f):
    """파일 경로 -> 범주. 위에서부터 첫 일치."""
    lo, base = f.lower(), os.path.basename(f).lower()
    parts = lo.split("/")
    ext = os.path.splitext(base)[1]
    if (lo.startswith(".github/") or base.startswith(("dockerfile", "docker-compose")) or ext in (".service", ".timer", ".cron") or
            any(x in parts[:-1] for x in ("systemd", "cron", "deploy", "scripts", "_scripts"))):
        return "CI/배포"
    if (any(x in parts[:-1] for x in ("tests", "test", "__tests__")) or base.startswith("test_") or
            re.search(r"(_test\.[a-z]+|\.(spec|test)\.[a-z]+)$", base)):
        return "테스트"
    if ext in (".md", ".mdx", ".txt", ".rst") or parts[0] == "docs":
        return "문서"
    if ext in (".toml", ".ini", ".cfg", ".json", ".yaml", ".yml", ".conf", ".env", ".spec", ".lock") or base in ("makefile", "procfile"):
        return "설정"
    if ext in CODE_EXT:
        return "코드"
    return "기타"


def is_ops_touch(f):
    lo, base = f.lower(), os.path.basename(f).lower()
    return (lo.startswith(".github/workflows/") or base.endswith((".spec", ".service", ".timer", ".cron")) or
            base in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", "codeowners", "procfile", "manage.py", "package.json") or
            base.startswith(("dockerfile", "docker-compose", "requirements")) or re.search(r"(^|/)(systemd|cron|deploy)/", lo) is not None or
            re.search(r"(wsgi|asgi)\.py$", base) is not None)


IMPORT_RE = re.compile(r"^\s*(from\s+\S+\s+import|import\s+\S|.*\brequire\()|^\s*import\s.*\bfrom\b")


def collect_impact(p, target):
    """{파일: [매칭 줄 수, import 줄 수]}. git grep -F -I 한 번(추적 파일만). '/' 가 든 대상은 역슬래시 형태도 찾는다."""
    pats = ["-e", target] + (["-e", target.replace("/", "\\")] if "/" in target else [])
    out = git(p, "grep", "-F", "-I", "-n", *pats).stdout
    hit = {}
    for line in out.splitlines():
        m = re.match(r"^(.*?):(\d+):(.*)$", line)
        if m:
            e = hit.setdefault(m.group(1), [0, 0])
            e[0] += 1
            if IMPORT_RE.match(m.group(3)) and os.path.splitext(m.group(1))[1].lower() in CODE_EXT:
                e[1] += 1
    return hit


def build_impact(path, target, full=False, depth=2):
    p = expand(path)
    files = [f for f in git(p, "ls-files").stdout.splitlines() if f]
    name = os.path.basename(os.path.realpath(p).rstrip("/\\"))
    if not files:
        return f"git 추적 파일을 읽지 못했다(git 저장소 아님?): {path}\n"
    t = target.replace("\\", "/")
    hit = collect_impact(p, t)
    cats = {}
    for f, (n, imp) in hit.items():
        c = cats.setdefault(impact_cat(f), [0, 0, 0])
        c[0] += 1
        c[1] += n
        c[2] += imp
    tn = t.rstrip("/")
    inside = [f for f in files if f == tn or f.startswith(tn + "/")]
    L = [f"# --impact 참조 수: `{target}` @ {name} (git 추적 {len(files)}개 파일 기준 · 읽기 전용)", "",
         "**주의:** 아래는 문자열이 든 파일·줄의 *참조 수*일 뿐 위험 판정이 아니다. 문자열(파일명) 일치 기반이라 같은 글자를 다른 뜻으로 쓴 곳은 과대, "
         "동적으로 조립한 경로·이름이나 추적되지 않는 파일(빌드 산출물·.gitignore)은 과소일 수 있다. "
         "Linear 이슈·DB 값·운영 서버의 실제 상태(systemd·cron·배포된 EXE)는 알지 못한다.", "",
         f"- 매칭 파일 {len(hit)}개 · 매칭 줄 {sum(v[0] for v in hit.values())}줄" +
         (f" · 대상이 추적 경로임(안의 파일 {len(inside)}개, 그중 매칭 {sum(1 for f in hit if f in set(inside))}개)" if inside else ""), "",
         "| 범주 | 파일 | 줄 | 그중 import 형태 줄 |", "|---|---|---|---|"]
    for c in ("코드", "설정", "CI/배포", "문서", "테스트", "기타"):
        v = cats.get(c, [0, 0, 0])
        L.append(f"| {c} | {v[0]} | {v[1]} | {v[2]} |")
    L.append(f"\nimport 형태 줄(코드·테스트 파일의 `import`/`from … import`/`require(` 줄) 합계: {sum(v[2] for v in cats.values())}줄 · "
             f"{sum(1 for v in hit.values() if v[1])}파일 (정규식 근사 — 여러 줄 import·문자열 속 import 는 틀릴 수 있다)")
    L += ["", f"### 상위 폴더별 분포({depth}단계)"]
    dist = {}
    for f, (n, _) in hit.items():
        k = "/".join(f.split("/")[:depth]) if f.count("/") >= depth else (os.path.dirname(f) or "(루트)")
        e = dist.setdefault(k, [0, 0])
        e[0] += 1
        e[1] += n
    L += [f"- {k}: 파일 {v[0]} · 줄 {v[1]}" for k, v in sorted(dist.items(), key=lambda x: -x[1][0])[:(None if full else 12)]] or ["- (없음)"]
    ops = sorted(f for f in hit if is_ops_touch(f))
    L += ["", f"### 운영 접점 파일이 걸렸는가: {len(ops)}개" + (" (서버·배포·EXE 스펙·패키지·테스트 설정 등 — 서버 쪽 실제 상태는 미확인)" if ops else "")]
    L += [f"- {f} ({hit[f][0]}줄)" for f in (ops if full else ops[:20])]
    if not full and len(ops) > 20:
        L.append(f"- … 외 {len(ops) - 20}개(--full)")
    top = sorted(hit.items(), key=lambda x: (-x[1][0], x[0]))
    L += ["", f"### 매칭 줄이 많은 파일 {'전체' if full else '상위 20'}"]
    L += [f"- {f} [{impact_cat(f)}] {v[0]}줄" for f, v in (top if full else top[:20])]
    if not full and len(top) > 20:
        L.append(f"- … 외 {len(top) - 20}개(--full)")
    return "\n".join(L) + "\n"


def run_adopt_impact(argv, sources_path):
    """--adopt / --impact 실행. 종료 코드를 돌려준다."""
    def opt(flag):
        return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None
    projects = []
    if os.path.exists(sources_path):
        projects = parse_sources(open(sources_path, encoding="utf-8").read()).get("projects", [])
    adopt, imp = opt("--adopt"), opt("--impact")
    ref = adopt or opt("--project") or os.getcwd()
    p = resolve_project(ref, projects)
    if not p or not os.path.isdir(os.path.join(p, ".git")):
        print(f"프로젝트를 찾지 못했거나 git 저장소가 아니다: {ref} (경로 또는 sources.yaml 의 프로젝트 이름)", file=sys.stderr)
        return 2
    try:
        mf = int(opt("--min-files") or 10)
    except ValueError:
        print("--min-files 는 정수", file=sys.stderr)
        return 2
    text = build_adopt(p, mf) if adopt else build_impact(p, imp, "--full" in argv)
    out = opt("--out")
    if out:
        err = write_out(expand(out), text, p)
        if err:
            print(err, file=sys.stderr)
            return 2
        print(f"저장: {out}")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(text)
    return 0


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
    if "--adopt" in argv or "--impact" in argv:  # 기존 프로젝트 개편 분석: PC 점검 없이 이것만
        return run_adopt_impact(argv, src)
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
        if run(["git", "--version"])[0] == 0:  # --impact·--adopt: 임시 저장소(-C 지정, GIT_* 는 selftest 첫머리에서 제거됨)
            e = os.path.join(d, "ex")
            os.makedirs(e)
            run(["git", "-C", e, "init", "-q"])
            tree = {"src/pkg/a.py": "from pkg import x\n", "src/pkg/b.py": "import pkg\nprint('pkg')\n", "src/pkg/sub/x.py": "pass\n",
                    "src/pkg/sub/y.py": "pass\n", "src/pkg/old/CLAUDE.md": "# `gone/name/` 모듈\n", "tests/test_a.py": "import pkg\n",
                    "docs/x.md": "pkg 설명\n", ".github/workflows/ci.yml": "run: pytest pkg\n", "pyproject.toml": "name = 'pkg'\n",
                    "deploy/app.service": "ExecStart=python -m pkg\n", "CLAUDE.md": "# t\n- main 에 직접 push 금지\n- 운영 DB 는 승인 후\n",
                    "AGENTS.md": "x\n"}
            for rel, body in tree.items():
                os.makedirs(os.path.dirname(os.path.join(e, rel)), exist_ok=True)
                open(os.path.join(e, rel), "w", encoding="utf-8").write(body)
            run(["git", "-C", e, "add", "."])
            run(["git", "-C", e, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "t"])
            assert [impact_cat(f) for f in ("src/a.py", "tests/t.py", "docs/x.md", "pyproject.toml", ".github/w.yml", "x/y.service", "a.png")] == \
                   ["코드", "테스트", "문서", "설정", "CI/배포", "CI/배포", "기타"]
            hit = collect_impact(e, "pkg")
            assert len(hit) == 7 and hit["src/pkg/b.py"] == [2, 1] and hit["src/pkg/a.py"] == [1, 1], hit
            txt = build_impact(e, "pkg")
            for want in ("| 코드 | 2 | 3 | 2 |", "| 테스트 | 1 | 1 | 1 |", "| 문서 | 1 | 1 | 0 |", "| 설정 | 1 | 1 | 0 |", "| CI/배포 | 2 | 2 | 0 |",
                         "합계: 3줄", "운영 접점 파일이 걸렸는가: 3개", "위험 판정이 아니다", "알지 못한다"):
                assert want in txt, (want, txt)
            ad = build_adopt(e, min_files=2)
            for want in ["## %d." % n for n in range(7)] + [UNK, MAP_MARK, "낡은 이름 의심", "src/pkg/sub | 2 |", "CLAUDE.md:2: - main 에 직접 push 금지",
                                                       "CLAUDE.md:3: - 운영 DB", "인용 합계 2줄", "--impact", "실행하지 않는다", "Q6"]:
                assert want in ad, (want, ad)
            assert "src/pkg/old/CLAUDE.md: 1줄 · 제목의 경로 `gone/name/`" in ad, ad
            assert resolve_project("ex", [e]) == e and resolve_project("none", [e]) is None and resolve_project(e, []) == e
            o = os.path.join(d, "plan.md")
            assert write_out(o, ad, e) is None and open(o, encoding="utf-8").read() == ad
            assert "덮어쓰지" in write_out(o, "x", e) and open(o, encoding="utf-8").read() == ad  # 덮어쓰기 거부
            assert "프로젝트 안" in write_out(os.path.join(e, "p.md"), "x", e) and not os.path.exists(os.path.join(e, "p.md"))
            assert run_adopt_impact(["--adopt", e, "--out", o], os.path.join(d, "none.yaml")) == 2  # CLI 도 거부
            assert run_adopt_impact(["--impact", "pkg", "--project", os.path.join(d, "nodir")], "") == 2
            assert run(["git", "-C", e, "status", "--short"])[1] == ""  # 읽기 전용: 저장소가 더러워지지 않음
        # 프로젝트 설정(.onboard.yaml)·이동 파일 자동 탐색·의도적 제외
        if run(["git", "--version"])[0] == 0:
            pj = os.path.join(d, "pj")
            for rel, body in {"scripts/ci/check-claude-md.py": "x\n", "a/dup.py": "x\n", "b/dup.py": "x\n"}.items():
                os.makedirs(os.path.dirname(os.path.join(pj, rel)), exist_ok=True)
                open(os.path.join(pj, rel), "w", encoding="utf-8").write(body)
            run(["git", "-C", pj, "init", "-q"])
            run(["git", "-C", pj, "add", "."])
            run(["git", "-C", pj, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "t"])
            assert load_pcfg(pj) == {} and skip_reasons(pj) == {}
            assert locate(pj, "scripts/check-claude-md.py") == "scripts/ci/check-claude-md.py"
            assert locate(pj, "x/dup.py") is None and locate(pj, "nope/none.py") is None  # 중복·부재는 못 찾음
            ok, why = eval_detect({"kind": "file_exists", "args": {"path": "scripts/check-claude-md.py"}}, pj, d)
            assert ok and "실제 위치 scripts/ci/check-claude-md.py" in why, why
            assert not eval_detect({"kind": "file_exists", "args": {"path": "nope/none.py"}}, pj, d)[0]
            assert eval_item({"detect": [{"kind": "file_exists", "args": {"path": "scripts/check-claude-md.py"}}]}, pj, d) == (OK, "실제 위치 scripts/ci/check-claude-md.py")
            r0, t0 = check_structure(pj)
            assert "제외" not in t0 and "docs/guides" in t0, t0  # 설정 없으면 기존과 같다
            open(os.path.join(pj, ONBOARD_CFG), "w", encoding="utf-8").write("skip_structure:\n  - docs/guides  # 의도적: 가이드는 위키에\n")
            r1, t1 = check_structure(pj)
            assert "제외: docs/guides — 의도적: 가이드는 위키에" in t1 and "의도적 제외" not in t1 and "없음: " in t1 and "docs/guides" not in t1.split("제외:")[0], t1
            assert run(["git", "-C", pj, "status", "--short"])[1].split() == ["??", ONBOARD_CFG]  # 읽기 전용: 테스트가 직접 만든 설정 외에 아무것도 생기지 않는다
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
    if "--selftest" in sys.argv:
        selftest()
    else:
        sys.exit(main(sys.argv[1:]) or 0)
