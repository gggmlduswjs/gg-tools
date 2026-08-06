#!/usr/bin/env python3
"""post-commit 감시자 — 방금 만든 커밋이 이상하면 **알린다**(막지 않는다). 공용 엔진 한 벌.

왜 post-commit 인가 (2026-08-06):
  Prevent 층(PreToolUse 훅·git pre-commit)은 세 가지로 우회된다 —
  `--no-verify` · `BOOKMART_HOOK_OK=1` · **tty 없음**(에이전트 세션은 'yes' 를 칠 수 없다).
  오늘 실제로 우회했고, 그 결과 272 파일이 남의 커밋에 딸려갔다(중앙값 1 인 레포에서).
  `--no-verify` 는 pre-commit·commit-msg 만 끈다 — **post-commit 은 끄지 못한다.**
  커밋은 이미 만들어졌지만 아직 push 전이라 **되돌리기가 가장 싼 순간**이기도 하다.

차단이 아니라 알림인 이유: pre-commit 과 트레이드오프가 정반대다. 막는 장치는 오탐이
한 번만 나도 우회가 상시화되지만(2026-08-01 진단), 알리는 장치는 오탐이 나도 손해가
"한 줄 더 읽는 것" 뿐이다. 그래서 임계를 실측 p99 근처로 놓고 넉넉히 본다.

각 레포는 `.git/hooks/post-commit` 에서 환경변수만 정하고 이 파일을 실행한다(tdd_guard 와 같은 배선).

    SENTINEL_FILES     혼자일 때 파일 수 임계        기본 40
    SENTINEL_DIRS      혼자일 때 디렉터리 span 임계  기본 6
    SENTINEL_SESSIONS  세션 레지스트리 경로(레포 루트 기준). 있으면 peers 를 센다. 선택.

peers > 1 (같은 워킹 디렉터리에 다른 세션이 살아 있음) 이면 임계를 5/2 로 낮춘다 —
그때가 오염이 실제로 일어나는 유일한 조건이라 레포별 튜닝이 필요 없다.

self-test:  python commit_sentinel.py --selftest
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

FILES_MAX = int(os.environ.get("SENTINEL_FILES", "40"))
DIRS_MAX = int(os.environ.get("SENTINEL_DIRS", "6"))
SESSIONS = os.environ.get("SENTINEL_SESSIONS", "")

# 다른 세션이 살아 있다고 볼 시간. session_unregister 가 매 턴 끝에 등록을 갱신하므로
# 살아있는 세션의 파일은 턴 간격마다 젊어진다(bookmart session_guard 와 같은 값).
STALE_SEC = 30 * 60
PEER_FILES_MAX = 5
PEER_DIRS_MAX = 2


def git(root, *args):
    # quotePath=false — 켜져 있으면 한글 경로를 `"home/skills/…"` 로 감싸 내보내서
    # 앞의 따옴표가 별개 디렉터리로 세어진다(실측: 272파일 커밋이 디렉터리 3곳으로 보였다).
    try:
        r = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false", *args],
                           capture_output=True, text=True, timeout=10,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def commit_files(root, sha="HEAD"):
    """커밋에 든 파일 목록. 머지 커밋이면 None — 남의 커밋을 통째로 들여오는 게 정상이다."""
    par = git(root, "rev-list", "--parents", "-n", "1", sha)
    if par and len(par.split()) > 2:
        return None
    out = git(root, "show", "--name-only", "--format=", sha)
    if out is None:
        return None
    return [l.strip() for l in out.splitlines() if l.strip()]


def live_peers(root, rel):
    """같은 워킹 디렉터리를 공유하는 살아있는 세션 수. 레지스트리가 없으면 None(판정 불가)."""
    if not rel:
        return None
    d = Path(root) / rel
    if not d.is_dir():
        return None
    me = os.path.normcase(os.path.normpath(str(root)))
    now, n = time.time(), 0
    for f in d.glob("*.json"):
        try:
            if now - f.stat().st_mtime > STALE_SEC:
                continue
            cwd = json.loads(f.read_text(encoding="utf-8")).get("cwd", "")
        except Exception:
            continue
        if os.path.normcase(os.path.normpath(cwd)) == me:
            n += 1
    return n


def touch_owners(root, rel, files):
    """커밋에 든 파일을 최근에 건드린 세션 id 집합. 기록이 없으면 빈 집합.

    둘 이상이면 **한 커밋에 여러 세션의 작업이 섞였다** = 오염의 정의 그 자체다.
    크기 임계와 달리 작은 오염도 잡는다(2026-08-06: 3 파일짜리가 임계 아래로 샜다).
    내 session_id 는 알 필요가 없다 — git 훅은 세션 정보를 못 받기 때문에 이 설계여야 한다.
    """
    if not rel or files is None:
        return set()
    d = Path(root) / rel
    if not d.is_dir():
        return set()
    fset, now, owners = set(files), time.time(), set()
    for f in d.glob("*.touched"):
        try:
            if now - f.stat().st_mtime > STALE_SEC:
                continue
            touched = {l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}
        except OSError:
            continue
        if fset & touched:
            owners.add(f.stem)
    return owners


def top(f):
    """파일 경로 → 셀 단위. 최상위 파일은 전부 하나로 묶는다 —
    파일명을 그대로 키로 쓰면 루트 파일 5개짜리 커밋이 '디렉터리 5곳' 으로 부푼다."""
    return f.split("/")[0] + "/" if "/" in f else "(루트)"


def judge(files, peers, owners=frozenset()):
    """(사유 목록, 임계쌍) — 사유가 비면 정상."""
    if files is None:
        return [], None
    n = len(files)
    dirs = {}
    for f in files:
        dirs[top(f)] = dirs.get(top(f), 0) + 1

    contaminable = peers is not None and peers > 1
    fmax = PEER_FILES_MAX if contaminable else FILES_MAX
    dmax = PEER_DIRS_MAX if contaminable else DIRS_MAX

    why = []
    # 크기와 무관하게 이게 제일 강한 신호다 — 크기는 오염의 증상이고 이건 오염 자체다.
    if len(owners) > 1:
        why.append(f"세션 {len(owners)}개의 작업이 한 커밋에 섞였다")
    if n > fmax:
        why.append(f"파일 {n}개 (임계 {fmax})")
    if len(dirs) > dmax:
        why.append(f"디렉터리 {len(dirs)}곳 (임계 {dmax})")
    return why, (dirs, contaminable, peers)


def report(root, sha, short, why, dirs, contaminable, peers):
    head = "⚠️ 방금 커밋이 이상하다"
    if contaminable:
        head = f"⚠️⚠️ 오염 의심 — 같은 폴더에서 세션 {peers}개가 작업 중인데 커밋이 크다"
    lines = [
        "",
        f"{head}  [{short}]",
        "   " + " · ".join(why),
    ]
    big = sorted(dirs.items(), key=lambda kv: -kv[1])[:6]
    lines.append("   " + " · ".join(f"{k} {v}" for k, v in big)
                 + (" …" if len(dirs) > 6 else ""))
    lines += [
        f"   확인:   git show --stat {short}",
        "   되돌림: git reset --soft HEAD~1      ← 커밋만 풀린다. 파일은 그대로.",
        "   ⛔ 이미 push 했다면 reset 하지 말 것 — 남이 받아 갔을 수 있다.",
        "",
    ]
    sys.stderr.write("\n".join(lines) + "\n")


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8")  # Windows cp949 → 한글 사유 보존
    except Exception:
        pass
    root = git(os.getcwd(), "rev-parse", "--show-toplevel")
    if not root:
        return
    files = commit_files(root)
    why, extra = judge(files, live_peers(root, SESSIONS), touch_owners(root, SESSIONS, files))
    if not why:
        return
    dirs, contaminable, peers = extra
    report(root, "HEAD", git(root, "rev-parse", "--short", "HEAD") or "HEAD",
           why, dirs, contaminable, peers)


def _selftest():
    """실제 git 레포를 만들어 돌린다 — 커밋 크기 판정은 모킹하면 못 잰다."""
    import tempfile
    global FILES_MAX, DIRS_MAX
    FILES_MAX, DIRS_MAX = 40, 6

    root = Path(tempfile.mkdtemp())
    for a in (["init", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        git(root, *a)

    def commit(paths, msg):
        for p in paths:
            f = root / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("x", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-qm", msg)

    # ── 정상 커밋은 조용하다 ────────────────────────────────────────────
    commit([f"src/a{i}.py" for i in range(3)], "small")
    assert judge(commit_files(root), None)[0] == [], "3파일 1디렉터리는 정상"
    assert judge(commit_files(root), 1)[0] == [], "혼자면 임계가 느슨하다"

    # ── 파일 수 초과 ────────────────────────────────────────────────────
    commit([f"src/b{i}.py" for i in range(50)], "big")
    why, _ = judge(commit_files(root), None)
    assert any("파일 50개" in w for w in why), why
    assert not any("디렉터리" in w for w in why), "한 디렉터리뿐인데 span 을 잡으면 오탐"

    # ── 디렉터리 span 초과 ──────────────────────────────────────────────
    commit([f"d{i}/x.py" for i in range(8)], "wide")
    why, _ = judge(commit_files(root), None)
    assert any("디렉터리 8곳" in w for w in why), why

    # ── peers > 1 이면 임계가 조여진다 = 오늘 사고 모양 ──────────────────
    commit([f"src/c{i}.py" for i in range(7)], "7 files while others work")
    files = commit_files(root)
    assert judge(files, 1)[0] == [], "혼자면 7파일은 정상"
    why, (_, contaminable, _) = judge(files, 3)
    assert contaminable and any("파일 7개" in w for w in why), why

    # ── 루트 파일은 하나로 묶는다(부풀림 방지) + 한글 경로 quote ─────────
    commit([f"r{i}.md" for i in range(9)], "root files")
    why, (dirs, _, _) = judge(commit_files(root), None)
    assert list(dirs) == ["(루트)"], f"루트 파일 9개는 한 칸이어야 한다: {dirs}"
    assert why == [], "9개 루트 파일이 '디렉터리 9곳' 으로 부풀면 안 된다"

    commit([f"한글폴더/파일{i}.md" for i in range(3)], "korean paths")
    files = commit_files(root)
    assert all(not f.startswith('"') for f in files), f"quotePath 가 살아 있다: {files}"
    assert list(judge(files, None)[1][0]) == ["한글폴더/"], files

    # ── 세션 교차 감지 — 크기 임계 아래여도 잡는다 ──────────────────────
    # 2026-08-06 실제 사고 재현: 3 파일짜리 커밋에 두 세션의 작업이 섞였다.
    sess = root / ".claude" / "sessions"
    sess.mkdir(parents=True, exist_ok=True)
    commit(["src/mine.py", "src/theirs.py", "docs/x.md"], "3 files, two sessions")
    files = commit_files(root)
    assert judge(files, None)[0] == [], "크기만 보면 3파일은 통과한다 — 그래서 샜다"

    (sess / "sessionA.touched").write_text("src/mine.py\ndocs/x.md\n", encoding="utf-8")
    (sess / "sessionB.touched").write_text("src/theirs.py\n", encoding="utf-8")
    owners = touch_owners(root, ".claude/sessions", files)
    assert owners == {"sessionA", "sessionB"}, owners
    why, _ = judge(files, None, owners)
    assert any("세션 2개" in w for w in why), why

    # 한 세션만 건드렸으면 조용하다 = 정상 작업
    (sess / "sessionB.touched").unlink()
    assert judge(files, None, touch_owners(root, ".claude/sessions", files))[0] == []

    # 겹치는 파일이 없는 세션은 주인이 아니다 — 같은 폴더에서 딴 일을 하는 중일 뿐
    (sess / "sessionC.touched").write_text("unrelated/z.py\n", encoding="utf-8")
    assert touch_owners(root, ".claude/sessions", files) == {"sessionA"}

    # 오래된 기록은 무시(끝난 세션이 영원히 오염으로 남으면 안 된다)
    old = sess / "sessionOld.touched"
    old.write_text("src/theirs.py\n", encoding="utf-8")
    os.utime(old, (time.time() - STALE_SEC - 60,) * 2)
    assert touch_owners(root, ".claude/sessions", files) == {"sessionA"}

    # ── 머지 커밋은 검사 대상이 아니다 ──────────────────────────────────
    git(root, "switch", "-qc", "side")
    commit([f"m{i}/y.py" for i in range(9)], "side work")
    git(root, "switch", "-q", "main")
    git(root, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    assert commit_files(root) is None, "머지는 남의 커밋을 들여오는 게 정상 — 건너뛴다"

    # ── 레지스트리가 없으면 판정 불가(None)이지 0 이 아니다 ─────────────
    assert live_peers(root, "") is None
    assert live_peers(root, "no/such/dir") is None
    # 폴더는 있는데 등록이 없으면 0 이다 — None(판정 불가)과 구분되어야 한다.
    # 0 이면 "혼자" 로 임계가 느슨해지고, None 이면 크기만 본다. 섞이면 임계가 뒤집힌다.
    assert live_peers(root, ".claude/sessions") == 0

    print("commit_sentinel selftest OK (20 cases · 크기·오염·세션교차·stale·머지·한글경로)")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
