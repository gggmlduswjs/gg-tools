#!/usr/bin/env python
"""ci_index.py — 3레포 + Obsidian 을 가로지르는 문서 인덱스 · 통합 검색.

Ch05 자산 04(Context Intelligence)의 우리 규모 판. 강의는 embedding·관계그래프를
쓰지만 여기 소스는 md 700여 개다 — 벡터DB 손익분기 아래고, 레포 3개 사이 코드 의존은
`notify_owner` 하나뿐이라 그래프로 그릴 게 없다. 그래서 남은 둘만 만든다:
  - 원문 저장소 = 파일 그대로 (이미 있다)
  - 통합 검색   = 한 번에 4곳 (이게 빈 칸이었다)

왜 필요했나: "이 주제 문서가 어디 있나"에 답하려면 지금은 grep 을 4군데 따로 돌린다.
2026-08-06 「계획서 11건 상태 정리」에서 실제로 그렇게 했다.

    python ci_index.py                # 인덱스 생성 → ~/claude/_ci/index.md
    python ci_index.py --search 재고   # 제목 + 본문 통합 검색
    python ci_index.py --selftest

⚠️ 인덱스는 **경로순**으로 정렬한다. 갱신일순이 읽기엔 낫지만 문서 하나 고칠 때마다
   700줄이 통째로 밀려 diff 가 쓸모없어진다. 갱신일은 열로만 보여준다.
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = Path.home()
DESKTOP = Path(os.environ.get("DEV_PROJECTS", HOME / "Desktop"))
VAULT = Path(os.environ.get("CI_VAULT", r"G:\내 드라이브\Obsidian"))
OUT = Path(os.environ.get("CI_INDEX_OUT", HOME / "claude" / "_ci" / "index.md"))

# (표시이름, 루트, [루트 기준 하위경로], git 레포인가)
# 하위경로를 명시하는 이유 — 레포 md 를 전부 담으면 Coupang docs/memory 215개가
# 인덱스의 절반을 먹는다. 그건 Claude 가 자동으로 읽는 것이지 사람이 찾을 대상이 아니다.
SOURCES = [
    ("bookmart", DESKTOP / "bookmart", [".dev/plans", ".dev/research", ".dev/maps"], True),
    ("Coupang", DESKTOP / "Coupang_v2",
     ["docs/plans", "docs/adr", "docs/runbooks", "docs/architecture", "docs/specs",
      "docs/reference"], True),
    ("claude", HOME / "claude", ["home/skills", "."], True),
    ("Obsidian", VAULT, ["20. Project", "30. Workspace", "60. Second Brain", "00. Index"], False),
]

# 건너뛸 디렉터리 — **이름을 하나씩 적는다**. `_` 접두 일괄 제외로 했더니
# bookmart `research/_매뉴얼`(시스템 지도·데이터 흐름도 15개)과 Obsidian `_핵심`
# (마스터플랜·ERD 17개)이 통째로 사라졌다. 규칙이 짧다고 맞는 게 아니다(2026-08-06 실측).
SKIP_DIRS = {
    "_archive", "_원본데이터", "_screenshots", "_secrets",
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "01-Daily",   # 날짜별 일지. Obsidian `10. Planner` 를 뺀 것과 같은 이유 — 결정이 아니다
}
# 스킬 폴더는 한 스킬 = 한 줄. 안 그러면 baoyu-design 의 참조 문서 33개가 인덱스를 먹는다.
SKILL_FILES = {"SKILL.md", "README.md"}
# 인덱스에서 **뺀 것**은 반드시 적는다. 안 적으면 "다 훑었다"로 읽힌다.
EXCLUDED_NOTE = [
    "Coupang `docs/memory` 215개 — Claude 자동 메모리(사람이 찾는 대상 아님)",
    "Obsidian `10. Planner`(일지 175) · `50. 공부` · `80. Archive` · `40. Inbox`",
    "bookmart `.dev/harness`(실행 산출물) · `.dev/mockups`",
]

RE_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)
RE_STATE = re.compile(r"^>\s*상태:\s*(\S+)", re.M)
RE_UPDATED = re.compile(r"갱신:\s*(\d{4}-\d{2}-\d{2})")
RE_WRITTEN = re.compile(r"(?:작성일?|작성):\s*(\d{4}-\d{2}-\d{2})")


def read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse(text, fallback_name):
    """문서 한 장에서 제목·상태·본문날짜를 뽑는다. 없으면 None (git/mtime 으로 뒤에서 채운다)."""
    m = RE_TITLE.search(text)
    title = m.group(1).strip() if m else fallback_name
    title = re.sub(r"\s+", " ", title)[:90]
    st = RE_STATE.search(text)
    # 템플릿은 안에 `> 상태: 진행` 이 예시로 박혀 있다. 그대로 두면 「진행 중인 계획」을
    # 셀 때마다 4건이 더해진다(실측: `_template.md` 3개 + `_템플릿.md` 1개).
    # 빼지는 않는다 — 새 계획을 쓸 때 찾아야 하는 문서다.
    if re.search(r"(?i)(template|템플릿)", fallback_name):
        return title, "템플릿", ""
    # 갱신 우선 — 작성일만 보면 꾸준히 고치는 문서가 낡은 걸로 보인다(2026-08-06 실측 오탐).
    d = RE_UPDATED.search(text) or RE_WRITTEN.search(text)
    return title, (st.group(1) if st else ""), (d.group(1) if d else "")


def git_dates(root):
    """레포 전체 파일의 최종 커밋일을 한 번에 — 파일마다 git log 를 부르면 700번이 된다.
    파일 mtime 을 쓰지 않는 이유: clone 하면 전부 클론 시각으로 뭉개진다."""
    out = {}
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=false", "log",
             "--format=@%cs", "--name-only", "--no-merges"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return out
    if r.returncode != 0:
        return out
    cur = ""
    for line in r.stdout.splitlines():
        if line.startswith("@"):
            cur = line[1:]
        elif line and cur:
            out.setdefault(line, cur)   # 최신 커밋부터 오므로 첫 등장이 최종 수정일
    return out


def mtime_date(p):
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return ""


def skip(parts, sub):
    """parts = 루트 기준 상대경로 조각(파일명 포함). 건너뛸 파일이면 True."""
    if any(p in SKIP_DIRS for p in parts[:-1]):
        return True
    return sub == "home/skills" and parts[-1] not in SKILL_FILES


def collect():
    rows = []
    for name, root, subs, is_git in SOURCES:
        if not root.exists():
            rows.append((name, None, None, None, None))   # 소스 자체가 없음 표시
            continue
        gd = git_dates(root) if is_git else {}
        seen = set()
        for sub in subs:
            base = root / sub
            if not base.exists():
                continue
            # "." 은 루트 md 만 (재귀하면 하위를 통째로 다시 먹는다)
            files = base.glob("*.md") if sub == "." else base.rglob("*.md")
            for f in sorted(files):
                if skip(f.relative_to(root).parts, sub):
                    continue
                rel = f.relative_to(root).as_posix()
                if rel in seen:
                    continue
                seen.add(rel)
                title, state, doc_date = parse(read(f), f.stem)
                date = doc_date or gd.get(rel) or mtime_date(f)
                rows.append((name, rel, title, state, date))
    return rows


def render(rows):
    today = datetime.now().strftime("%Y-%m-%d")
    out = [
        "# 통합 문서 인덱스 (Context Intelligence)",
        "",
        f"> 자동 생성 — `python ~/claude/scripts/ci_index.py` · 마지막 갱신 {today}",
        "> ⛔ 손으로 고치지 마라. 다음 실행에 덮어쓴다. 범위를 바꾸려면 `ci_index.py` 의 `SOURCES`.",
        "",
        "찾기: `python ~/claude/scripts/ci_index.py --search <낱말>` — 제목과 본문을 4소스에서 한 번에.",
        "",
        "## 인덱스에서 뺀 것",
        "",
    ]
    out += [f"- {e}" for e in EXCLUDED_NOTE]
    out.append("")

    for name, root, _subs, _g in SOURCES:
        mine = [r for r in rows if r[0] == name]
        if mine and mine[0][1] is None:
            out += [f"## {name}", "", f"⚠️ 소스 없음 — `{root}` (이 PC 에 없거나 드라이브 미마운트)", ""]
            continue
        out += [f"## {name} — {len(mine)}건", "", f"`{root}`", "",
                "| 갱신 | 상태 | 제목 | 경로 |", "|---|---|---|---|"]
        for _n, rel, title, state, date in mine:
            t = title.replace("|", "\\|")
            out.append(f"| {date or '?'} | {state or '·'} | {t} | `{rel}` |")
        out.append("")
    return "\n".join(out) + "\n"


def search(keyword, rows):
    """제목 히트와 본문 히트를 나눠 보여준다 — 섞으면 제목이 정확히 맞는 문서가 묻힌다."""
    kw = keyword.lower()
    by_title, by_body = [], []
    for name, rel, title, state, date in rows:
        if rel is None:
            continue
        root = next(s[1] for s in SOURCES if s[0] == name)
        if kw in title.lower() or kw in rel.lower():
            by_title.append((name, rel, title, state, date, ""))
            continue
        text = read(root / rel)
        i = text.lower().find(kw)
        if i >= 0:
            line = text[max(0, i - 40):i + 60].replace("\n", " ").strip()
            by_body.append((name, rel, title, state, date, line))
    return by_title, by_body


def print_hits(label, hits, limit):
    print(f"\n=== {label} {len(hits)}건" + (f" (상위 {limit})" if len(hits) > limit else "") + " ===")
    for name, rel, title, state, date, ctx in hits[:limit]:
        print(f"  [{name}] {title}  ({date or '?'}{' · ' + state if state else ''})")
        print(f"      {rel}")
        if ctx:
            print(f"      … {ctx} …")


def selftest():
    import tempfile
    t, s, d = parse("# 제목입니다\n> 상태: 진행 · 작성: 2026-07-01 · 갱신: 2026-08-03\n", "fb")
    assert (t, s, d) == ("제목입니다", "진행", "2026-08-03"), (t, s, d)
    t, s, d = parse("> 작성일: 2026-07-03 · 대상: x\n# 나중제목\n", "fb")
    assert d == "2026-07-03", d          # 작성일 표기도 잡아야 한다(Coupang 형식)
    assert t == "나중제목"
    t, s, d = parse("본문만 있다\n", "파일이름")
    assert (t, s, d) == ("파일이름", "", ""), (t, s, d)
    t, _, _ = parse("#   공백   많은    제목  \n", "fb")
    assert t == "공백 많은 제목", repr(t)
    t, _, _ = parse("# " + "가" * 200 + "\n", "fb")
    assert len(t) == 90                   # 표가 깨지지 않게 자른다
    # 갱신이 작성보다 먼저 나와도 갱신을 쓴다
    _, _, d = parse("> 갱신: 2026-08-05 · 작성: 2026-01-01\n", "fb")
    assert d == "2026-08-05", d
    # 상태는 줄 맨 앞 `>` 만 — 본문 중간의 "상태:" 를 주우면 안 된다
    _, s, _ = parse("내용 중 상태: 폐기 라고 적힘\n", "fb")
    assert s == "", s
    # 템플릿의 예시 상태를 진짜 상태로 세지 않는다
    _, s, d = parse("# [기능명] 구현 계획\n> 상태: 진행 · 갱신: 2026-07-28\n", "_template")
    assert (s, d) == ("템플릿", ""), (s, d)
    _, s, _ = parse("> 상태: 진행\n", "_템플릿")
    assert s == "템플릿", s
    _, s, _ = parse("> 상태: 진행\n", "재고원장_도입_plan")   # 보통 문서는 그대로
    assert s == "진행", s

    # 필터 — 322건을 잘못 먹었던 자리다. 되돌아가지 않게 양쪽을 다 박아둔다.
    assert skip((".dev", "plans", "_archive", "a.md"), ".dev/plans")
    assert not skip((".dev", "research", "_매뉴얼", "시스템_지도.md"), ".dev/research")
    assert not skip(("30. Workspace", "bookmart", "_핵심", "09_마스터_ERD.md"), "30. Workspace")
    assert skip(("30. Workspace", "bookmart", "01-Daily", "2026-04-25.md"), "30. Workspace")
    assert skip(("30. Workspace", "bookmart", "_secrets", "x.md"), "30. Workspace")
    assert not skip(("home", "skills", "harness", "SKILL.md"), "home/skills")
    assert skip(("home", "skills", "baoyu-design", "references", "x.md"), "home/skills")
    # 같은 파일명이라도 스킬 폴더 밖이면 통과해야 한다
    assert not skip(("docs", "adr", "SKILL.md"), "docs/adr")
    assert not skip(("docs", "adr", "0001.md"), "docs/adr")

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "a.md"
        p.write_text("# 한글 제목\n내용 재고 확인\n", encoding="utf-8")
        assert "한글 제목" in read(p)
        assert mtime_date(p).count("-") == 2
    assert read(Path(td) / "없는파일.md") == ""    # 사라진 파일에 죽지 않는다

    rows = [("bookmart", "a.md", "재고 원장", "진행", "2026-08-01")]
    ti, _bo = search("재고", rows)
    assert len(ti) == 1
    ti, _bo = search("없는낱말", rows)
    assert len(ti) == 0
    md = render([("bookmart", "a.md", "파이프|포함", "진행", "2026-08-01")])
    assert r"파이프\|포함" in md              # 표를 깨뜨리지 않게 이스케이프
    assert "인덱스에서 뺀 것" in md            # 제외 범위는 늘 보인다
    print("selftest OK")
    return 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    rows = collect()
    if "--search" in argv:
        kw = argv[argv.index("--search") + 1]
        by_title, by_body = search(kw, rows)
        if not by_title and not by_body:
            print(f"'{kw}' — 4소스에서 0건")
            return 1
        print_hits("제목·경로", by_title, 20)
        print_hits("본문", by_body, 15)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(rows), encoding="utf-8")
    live = [r for r in rows if r[1] is not None]
    print(f"인덱스 {len(live)}건 → {OUT}")
    for name, _r, _s, _g in SOURCES:
        n = len([r for r in live if r[0] == name])
        missing = any(r[0] == name and r[1] is None for r in rows)
        print(f"  {name}: {'⚠️ 소스 없음' if missing else n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
