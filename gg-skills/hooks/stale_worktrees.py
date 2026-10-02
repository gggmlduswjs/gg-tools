#!/usr/bin/env python3
"""SessionStart 보조 — main 에서 너무 멀어진 워크트리를 알린다. 공용 엔진 한 벌.

왜 필요한가 (2026-08-13 실측):
  쿠팡에 워크트리가 22개 쌓여 있었는데 `wt.ps1 prune` 은 **정리 대상 0**을 반환했다.
  dirty 워크트리의 미커밋이 대부분 **하네스 자신의 phase 산출물**이라 "dirty 는 손대지
  않는다" 가드에 전부 걸린 것이다. 도구는 멀쩡했고 **아무도 안 봤을 뿐**이다.
  북마트도 같은 날 8개가 쌓여 있었는데 거긴 경고 자체가 없었다.
  그래서 '발견'을 사람에서 훅으로 옮긴다.

★왜 나이(일)가 아니라 **뒤처진 커밋 수**인가:
  main 이 하루 50~72커밋으로 움직인다. 실측 대응 — 1일≈34~69 · 2일≈92~124 ·
  4일≈195 · 6일=416커밋. 416커밋 뒤처진 워크트리에서 다시 시작하는 것보다
  새로 따는 게 언제나 싸다. 커밋 수가 "얼마나 쓸모없어졌나"를 더 정확히 잰다.

환경변수 (shim 이 설정):
    WORKTREE_BEHIND_LIMIT   이만큼 뒤처지면 폐기물로 본다        기본 100 (≈이틀치)
    WORKTREE_REPORT_MAX     화면에 띄울 최대 개수                기본 5
    WORKTREE_BASE           비교 기준                            기본 origin/main

⚠️ **fetch 하지 않는다** — 훅은 빨라야 한다. 세션 시작 스크립트가 먼저 main 을 당기므로
   `origin/main` 은 대개 신선하고, 낡았으면 이 경고가 **과소보고될 뿐 오보는 아니다.**

self-test:  python stale_worktrees.py --selftest   (git 없이 도는 순수 파싱 테스트)
"""
import os
import subprocess
import sys
from pathlib import Path

BEHIND_LIMIT = int(os.environ.get("WORKTREE_BEHIND_LIMIT", "100"))
REPORT_MAX = int(os.environ.get("WORKTREE_REPORT_MAX", "5"))
BASE = os.environ.get("WORKTREE_BASE", "origin/main")


# ── 순수 함수 (git 없이 테스트된다) ────────────────────────────────────────

def parse_worktrees(porcelain: str) -> list:
    """`git worktree list --porcelain` → [{path, branch}].

    ⚠️ --porcelain 을 쓰는 이유: 사람이 읽는 형식과 달리 **경로를 escape 하지 않는다.**
       이 레포들은 폴더명이 한글 천지라 escape 되면 경로가 통째로 못 쓰게 된다.
    """
    trees, cur = [], {}
    for line in (porcelain or "").splitlines():
        if line.startswith("worktree "):
            if cur:
                trees.append(cur)
            cur = {"path": line[len("worktree "):]}
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch "):].replace("refs/heads/", "")
    if cur:
        trees.append(cur)
    return trees


def parse_refs(out: str) -> dict:
    """`for-each-ref --format=%(refname:short)|%(committerdate:short)|%(ahead-behind:BASE)`
    → {branch: (behind, 마지막커밋일)}.

    ahead-behind 는 git 2.41+ 다. 못 쓰는 git 에선 값이 비어 여기서 조용히 빠지고,
    호출부가 브랜치별 rev-list 로 폴백한다.
    """
    meta = {}
    for line in (out or "").splitlines():
        name, _, rest = line.partition("|")
        date, _, ab = rest.partition("|")
        parts = ab.split()
        if len(parts) == 2 and parts[1].isdigit():   # "ahead behind"
            meta[name] = (int(parts[1]), date)
    return meta


def select_stale(trees: list, meta: dict, root: Path, limit: int) -> list:
    """임계를 넘은 것만, 많이 뒤처진 순으로. [(behind, 이름, 마지막커밋일, 경로)]

    ⚠️ 임계 미만(=작업 중)은 **아예 언급하지 않는다.** 상시 경고는 곧 무시된다.
    """
    out = []
    for t in trees:
        path, branch = t.get("path", ""), t.get("branch")
        if not branch:
            continue
        try:
            if Path(path).resolve() == Path(root).resolve():
                continue   # 메인 체크아웃은 별도 관리다
        except OSError:
            pass
        if branch not in meta:
            continue
        behind, last = meta[branch]
        if behind >= limit:
            out.append((behind, Path(path).name, last, path))
    return sorted(out, key=lambda r: -r[0])


def format_lines(stale: list, dirty: dict) -> list:
    """사람이 읽을 줄. ⚠️ **여기서 자르지 않는다** — 자른 목록에 "외 N개" 줄을 섞으면
    호출부의 len() 이 그 줄까지 세어 건수를 틀리게 말한다(08-13 에 6개라 적고 실제 7개).
    자르는 일은 출력하는 쪽에서 한다.
    """
    lines = []
    for behind, name, last, path in stale:
        n = dirty.get(path, 0)
        lines.append(f"{name} — main 뒤 {behind}커밋 · 마지막 커밋 {last}"
                     + (f" · 미커밋 {n}건" if n else ""))
    return lines


# ── git 을 부르는 부분 ─────────────────────────────────────────────────────

def report(root) -> list:
    """워크트리 경고 줄 목록. 못 재면 빈 목록(오탐보다 침묵이 낫다)."""
    root = Path(root)

    def _git(args, cwd=None, timeout=5):
        return subprocess.run(["git", "-C", str(cwd or root), *args],
                              capture_output=True, text=True, timeout=timeout)

    try:
        r = _git(["worktree", "list", "--porcelain"])
        if r.returncode != 0:
            return []
    except Exception:
        return []

    trees = parse_worktrees(r.stdout)

    # 브랜치별 (뒤처진 커밋 수, 마지막 커밋일)을 **한 번의 호출**로 받는다.
    # ⚠️ 브랜치마다 rev-list+log 를 돌리면 워크트리 13개에 2.6초가 걸렸다(Windows 는
    #    프로세스 생성이 비싸다). for-each-ref 의 ahead-behind 는 전부 0.2초다.
    meta = {}
    try:
        f = _git(["for-each-ref",
                  f"--format=%(refname:short)|%(committerdate:short)|%(ahead-behind:{BASE})",
                  "refs/heads"])
        meta = parse_refs(f.stdout)
    except Exception:
        pass

    if not meta:   # 구버전 git 폴백 — 느리지만 조용히 죽지는 않는다
        for t in trees:
            b = t.get("branch")
            if not b:
                continue
            try:
                c = _git(["rev-list", "--count", f"{b}..{BASE}"])
                meta[b] = (int((c.stdout or "0").strip() or 0), "?")
            except Exception:
                continue

    stale = select_stale(trees, meta, root, BEHIND_LIMIT)

    # dirty 는 **화면에 보일 것만** 본다 — status 는 워크트리마다 인덱스를 여느라 비싸다.
    dirty = {}
    for _behind, _name, _last, path in stale[:REPORT_MAX]:
        try:
            s = _git(["status", "--porcelain"], cwd=path, timeout=8)
            dirty[path] = len([l for l in (s.stdout or "").splitlines() if l.strip()])
        except Exception:
            pass

    return format_lines(stale, dirty)


def _selftest() -> int:
    porcelain = (
        "worktree C:/repo\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree C:/repo-wt/한글이름\nHEAD def\nbranch refs/heads/wip/a\n\n"
        "worktree C:/repo-wt/detached\nHEAD 999\ndetached\n\n"
        "worktree C:/repo-wt/fresh\nHEAD fff\nbranch refs/heads/wip/b\n"
    )
    trees = parse_worktrees(porcelain)
    assert len(trees) == 4, trees
    assert trees[1]["path"] == "C:/repo-wt/한글이름"        # 한글 경로가 안 깨진다
    assert trees[1]["branch"] == "wip/a"
    assert "branch" not in trees[2]                          # detached 는 브랜치가 없다

    meta = parse_refs("main|2026-08-13|0 0\n"
                      "wip/a|2026-08-07|3 412\n"
                      "wip/b|2026-08-13|1 4\n"
                      "wip/old|2026-08-01|0 \n")             # ahead-behind 미지원 형태
    assert meta["wip/a"] == (412, "2026-08-07"), meta
    assert "wip/old" not in meta                             # 파싱 안 되면 조용히 빠진다

    stale = select_stale(trees, meta, Path("C:/repo"), 100)
    assert [s[1] for s in stale] == ["한글이름"], stale       # fresh(4) 는 언급도 안 한다
    assert stale[0][0] == 412

    # 메인 체크아웃은 제외된다 (main 이 아무리 뒤처져도)
    assert select_stale(trees, {"main": (999, "x")}, Path("C:/repo"), 100) == []

    lines = format_lines(stale, {"C:/repo-wt/한글이름": 7})
    assert lines == ["한글이름 — main 뒤 412커밋 · 마지막 커밋 2026-08-07 · 미커밋 7건"], lines
    # ⚠️ 자르지 않는다 — 호출부의 len() 이 정확해야 한다
    assert len(format_lines(stale, {})) == len(stale)

    print("stale_worktrees engine self-check OK - 9 passed")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    for line in report(sys.argv[1] if len(sys.argv) > 1 else Path.cwd()):
        print(line)
