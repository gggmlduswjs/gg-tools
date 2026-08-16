#!/usr/bin/env python3
"""
Harness Step Executor — phase 내 step을 provider-neutral agent로 순차 실행한다.

Usage:
    python .dev/harness/execute.py <phase-dir> [--provider codex|claude] [--push]
"""

import argparse
import contextlib
from dataclasses import dataclass
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid

# Windows CP949 콘솔에서 유니코드 스피너 문자 출력 보장
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
import time
import types
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ⚠️ 레포 루트는 **런처가 알려준다.** 이 엔진은 플러그인(`~/claude/scripts/`)에 살고
#    레포의 `.dev/harness/execute.py` 가 `runpy` 로 부른다 — 그때 `__file__` 은 엔진 경로라
#    `parents[2]` 로 세면 엉뚱한 루트(`~/claude`)를 잡는다.
#    폴백은 옛 동작(레포 안에 직접 놓고 돌리는 경우) 그대로 둔다.
_env_root = os.environ.get("HARNESS_REPO_ROOT")
ROOT = Path(_env_root).resolve() if _env_root else Path(__file__).resolve().parents[2]
PHASES_REL = ".dev/harness/phases"          # 레포-상대 phase 경로 (git·서브에이전트 프롬프트용)
PREFLIGHT_SENTINEL = ".dev/harness/.preflight"  # 에이전트 셸이 실제로 떴는지 증명하는 자리
VERIFY_REL = ".dev/harness/verify.ps1"      # 레포가 정한 step 검증 명령
# 레포가 정한 preflight 테스트 명령. 없으면 맨 pytest — 그게 정본이 아닌 레포가 있다
# (bookmart 는 Django 라 DJANGO_SETTINGS_MODULE 없이 수집이 233건 죽는다).
PREFLIGHT_TESTS_REL = ".dev/harness/preflight_tests.ps1"

# 테스트가 `os.name` 전역을 못 건드리게 여기서 한 번만 읽는다. 전역을 patch 하면
# pathlib 이 이 플랫폼에 없는 Path 를 골라(`NotImplementedError: cannot instantiate
# 'WindowsPath'`) pytest 세션 전체가 INTERNALERROR 로 죽는다 (2026-08-08 Linux CI).
_IS_WINDOWS = os.name == "nt"


def strip_store_app_shims(path: str) -> str:
    """PATH 에서 Microsoft Store 앱 shim 폴더(`WindowsApps`)를 뺀다.

    codex 는 샌드박스 명령을 `CodexSandboxOnline` 로컬 계정으로
    `CreateProcessAsUserW` 한다. 이 PC 의 `pwsh`·`python` 은 Store 패키지라
    실행 파일이 `C:\\Program Files\\WindowsApps\\...` 에 있고, 패키지가 등록되지
    않은 다른 계정으로는 못 띄운다 → `CreateProcessAsUserW failed: 5`.
    파일 편집은 되고 **셸 명령만** 죽는 이유가 이것이다(bookmart 2026-08-07 실측).

    PATH 에서 빼면 codex 가 `C:\\Windows\\System32\\...\\powershell.exe` 로
    폴백하고, 샌드박스를 켠 채로 셸이 뜬다(실패 0ms → 성공 4,193ms).
    이 레포에도 같은 증상이 났다 — 2026-08-08 `패키지-계층-재설계` step 0 이
    「구현은 됐는데 pytest/ruff 를 못 돌려」 blocked.
    """
    entries = [p for p in path.split(os.pathsep) if p and "windowsapps" not in p.lower()]
    return os.pathsep.join(entries)


@dataclass(frozen=True)
class AgentConfig:
    """Non-interactive coding agent invocation settings."""

    provider: str = "codex"
    model: Optional[str] = None
    # 벽시계는 **폭주 방지 천장**이지 hang 탐지기가 아니다 — 그건 `inactivity` 가 한다.
    # 옛 기본값 1800(30분)은 정당한 작업을 잘랐다:
    #   · bookmart 2026-08-07 — 구현 24분짜리 step 이 검증 6분째에 잘림
    #   · Coupang_v2 2026-08-08 — P2b-3 이 작업을 다 끝내고 커밋 직전에 잘림
    #
    # ★ 이건 **시도당이 아니라 step 당 총예산**이다(재시도 전부의 합). 2026-08-09 까지는
    #   시도당 21,600초였고, MAX_RETRIES=3 이라 **한 step 이 최대 18시간**이었다.
    #   실측(bookmart `인라인셀편집-통일` step1): `retry 3/3` **한 번에만 11,193초(3h06m)**.
    #   codex 가 runserver 를 띄워놓고 계속 출력을 내서 무응답 감시(2,400초)는 한 번도 안 걸렸다 —
    #   침묵하지 않는 hang 은 무응답 감시로 못 잡는다. 그래서 총예산이 필요하다.
    #
    # 5,400 의 근거 = 시도 3회 × 30분. 30분 = 구현 ~10분 + 이 엔진이 실측한 **완주한 셸 호출
    # 최장 1,116.8초(18.6분)**. 정직한 시도 두 번은 통째로 들어가고, 위 3h06m 은 90분에 잘린다.
    timeout: int = 5400           # step 당 총 90분 (시도 전부 합쳐서)
    # 무응답 상한은 「에이전트가 생각하는 시간」이 아니라 **에이전트가 띄운 명령이 도는 시간**으로
    # 잡아야 한다. codex 는 셸 도구가 끝나야 그 출력을 내보내서, 긴 명령 하나가 통째로 침묵이다.
    # 옛 기본값 600(10분)은 정당한 검증을 잘랐다 — bookmart 2026-08-08 밤샘 실측:
    #   · 끊긴 step 8/8 이 전부 `test.ps1 -Postgres orders` 실행 중이었다(전부 exit 124)
    #   · 같은 명령이 **완주한 회차는 903.9초**(15.1분) 걸렸다 → 600 으로는 애초에 못 넘긴다
    #   · 그날 완주한 셸 호출 중 최장은 1,116.8초(18.6분)
    #   · 반면 **생각(reasoning) 침묵은 최대 22.5초**였다 — 「xhigh 라 오래 침묵한다」는 원인이 아니다
    #     (그래서 reasoning summaries 를 켜도 이 오탐은 안 없어진다. 침묵의 주체가 셸이다)
    # 레인 4개가 같은 Postgres·venv 를 물고 도니 위 실측의 2배 여유를 얹었다.
    inactivity: int = 2400        # 40분간 출력 0 = 진짜 hang
    unsafe: bool = False

    def __post_init__(self):
        if self.provider not in {"codex", "claude"}:
            raise ValueError(f"unsupported provider: {self.provider}")


@dataclass(frozen=True)
class VerifyRun:
    """A single `.dev/harness/verify.ps1` run result."""

    available: bool
    returncode: Optional[int] = None
    reason: str = ""
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.available and self.returncode == 0


@contextlib.contextmanager
def progress_indicator(label: str):
    """진행 표시기. with 문으로 사용하며 .elapsed 로 경과 시간을 읽는다.

    출력이 파이프·로그로 가면(`ai.ps1 go` 의 `*>&1 | Tee-Object`) `\\r` 이 커서를
    안 되돌려 스피너 프레임이 전부 파일에 쌓인다 — 2026-08-08 실측 1.75MB 로그의
    **96%**(17,267/17,916줄)가 `◐◓◑◒` 였다. tty 가 아니면 30초에 한 줄만 찍는다.
    """
    tty = sys.stderr.isatty()
    interval = 0.12 if tty else 30.0
    frames = "◐◓◑◒"
    stop = threading.Event()
    t0 = time.monotonic()

    def _animate():
        idx = 0
        while not stop.wait(interval):
            sec = int(time.monotonic() - t0)
            if tty:
                sys.stderr.write(f"\r{frames[idx % len(frames)]} {label} [{sec}s]")
            else:
                sys.stderr.write(f"  ... {label} [{sec}s]\n")
            sys.stderr.flush()
            idx += 1
        if tty:
            sys.stderr.write("\r" + " " * (len(label) + 20) + "\r")
        sys.stderr.flush()

    th = threading.Thread(target=_animate, daemon=True)
    th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        th.join()
        info.elapsed = time.monotonic() - t0


class StepExecutor:
    """Phase 디렉토리 안의 step들을 순차 실행하는 하네스."""

    MAX_RETRIES = 3
    PREFLIGHT_TIMEOUT = 300
    VERIFY_TIMEOUT = 1800
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    CHORE_MSG = "chore({phase}): step {num} output"
    TZ = timezone(timedelta(hours=9))

    def __init__(
        self,
        phase_dir_name: str,
        *,
        auto_push: bool = False,
        agent: Optional[AgentConfig] = None,
        manage_branch: bool = True,
        preflight: bool = True,
    ):
        self._root = str(ROOT)
        self._phases_dir = ROOT / PHASES_REL
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._auto_push = auto_push
        self._agent = agent or AgentConfig()
        self._manage_branch = manage_branch
        self._preflight_enabled = preflight
        self._inactivity = self._agent.inactivity
        self._baseline_paths: set[str] = set()
        self._verify_baseline = VerifyRun(available=False, reason="not measured")
        self._verify_baseline_red = False

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found")
            sys.exit(1)

        self._index_file = self._phase_dir / "index.json"
        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found")
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])
        self._venv_scripts = self._find_venv_scripts()

    def run(self):
        self._print_header()
        self._check_blockers()
        if self._preflight_enabled:
            self._run_preflight()
        if self._manage_branch:
            self._checkout_branch()
        self._baseline_paths = set(self._changed_paths())
        if self._baseline_paths:
            print(f"  Baseline dirty paths ignored: {len(self._baseline_paths)}")
        self._measure_verify_baseline()
        self._baseline_paths |= set(self._changed_paths())
        guardrails = self._load_guardrails()
        self._ensure_created_at()
        self._execute_all_steps(guardrails)
        self._finalize()

    # --- timestamps ---

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    # --- JSON I/O ---

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- git ---

    def _find_venv_scripts(self) -> Optional[Path]:
        """본체 체크아웃의 `.venv/Scripts`. worktree 엔 .venv 가 없어 git 이 알려준 본체를 쓴다
        (`run.ps1` 이 쓰는 것과 같은 방식)."""
        r = self._run_git("rev-parse", "--path-format=absolute", "--git-common-dir")
        if r.returncode != 0 or not isinstance(r.stdout, str) or not r.stdout.strip():
            return None
        scripts = Path(r.stdout.strip()).parent / ".venv" / "Scripts"
        return scripts if scripts.is_dir() else None

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git"] + list(args)
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True)

    @staticmethod
    def _parse_status_paths(raw: str) -> list[str]:
        """Parse `git status --porcelain=v1 -z` into changed path names."""
        parts = raw.split("\0")
        paths: list[str] = []
        i = 0
        while i < len(parts):
            entry = parts[i]
            if not entry:
                i += 1
                continue

            status = entry[:2]
            path = entry[3:]
            if path:
                paths.append(path)

            # In -z porcelain output, rename/copy entries are followed by the
            # original path. Stage the new path and skip the old path token.
            if "R" in status or "C" in status:
                i += 2
            else:
                i += 1

        return sorted(set(paths))

    def _changed_paths(self) -> list[str]:
        r = self._run_git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        if r.returncode != 0:
            print(f"  ERROR: git status 실패: {r.stderr.strip()}")
            sys.exit(1)
        return self._parse_status_paths(r.stdout)

    def _is_stageable(self, path: str) -> bool:
        """Return False for gitignore/runtime paths (incl. tracked-but-ignored legacy files)."""
        r = self._run_git("add", "-n", "--", path)
        if r.returncode != 0:
            return False
        out = f"{r.stdout or ''}{r.stderr or ''}"
        return "ignored by one of your .gitignore" not in out

    def _unstage_paths(self, paths: list[str] | set[str]):
        paths = sorted(set(paths))
        if not paths:
            return
        r = self._run_git("restore", "--staged", "--", *paths)
        if r.returncode != 0:
            print(f"  WARN: unstaged 복원 실패: {r.stderr.strip()}")

    def _stage_paths(self, paths: list[str] | set[str]):
        for path in sorted(set(paths)):
            r = self._run_git("add", "--", path)
            if r.returncode != 0:
                err = r.stderr.strip()
                if "ignored by one of your .gitignore" in err:
                    print(f"  Skip gitignored: {path}")
                    continue
                print(f"  ERROR: git add 실패({path}): {err}")
                sys.exit(1)

    def _new_changed_paths(self) -> set[str]:
        return set(self._changed_paths()) - self._baseline_paths

    def _committable_paths(self, paths: set[str]) -> set[str]:
        stageable = {p for p in paths if self._is_stageable(p)}
        skip = paths - stageable
        if skip:
            print(f"  Skip (gitignore/runtime): {', '.join(sorted(skip))}")
            self._unstage_paths(skip)
        return stageable

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"

        r = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print(f"  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            print(f"  {r.stderr.strip()}")
            sys.exit(1)

        if r.stdout.strip() == branch:
            return

        r = self._run_git("rev-parse", "--verify", branch)
        r = self._run_git("checkout", branch) if r.returncode == 0 else self._run_git("checkout", "-b", branch)

        if r.returncode != 0:
            print(f"  ERROR: 브랜치 '{branch}' checkout 실패.")
            print(f"  {r.stderr.strip()}")
            print(f"  Hint: 변경사항을 stash하거나 commit한 후 다시 시도하세요.")
            sys.exit(1)

        print(f"  Branch: {branch}")

    def _commit_step(self, step_num: int, step_name: str):
        output_rel = f"{PHASES_REL}/{self._phase_dir_name}/step{step_num}-output.json"
        index_rel = f"{PHASES_REL}/{self._phase_dir_name}/index.json"
        housekeeping = {output_rel, index_rel}
        changed = self._committable_paths(self._new_changed_paths())

        self._stage_paths(changed - housekeeping)

        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  Commit: {msg}")
            else:
                print(f"  WARN: 코드 커밋 실패: {r.stderr.strip()}")

        self._stage_paths(changed & housekeeping)
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.CHORE_MSG.format(phase=self._phase_name, num=step_num)
            r = self._run_git("commit", "-m", msg)
            if r.returncode != 0:
                print(f"  WARN: housekeeping 커밋 실패: {r.stderr.strip()}")

    # --- top-level index ---

    def _update_top_index(self, status: str, reason: str = ""):
        if not self._top_index_file.exists():
            return
        top = self._read_json(self._top_index_file)
        ts = self._stamp()
        for phase in top.get("phases", []):
            if phase.get("dir") == self._phase_dir_name:
                break
        else:
            # 등록 안 된 phase 는 조용히 누락되던 자리 — 현황판에 새로 달아준다.
            phase = {"dir": self._phase_dir_name}
            top.setdefault("phases", []).append(phase)
        phase["status"] = status
        ts_key = {"completed": "completed_at", "error": "failed_at", "blocked": "blocked_at"}.get(status)
        if ts_key:
            phase[ts_key] = ts
        if reason:
            phase["reason"] = reason
        self._write_json(self._top_index_file, top)

    # --- guardrails & context ---

    def _load_guardrails(self) -> str:
        sections = []
        claude_md = ROOT / "CLAUDE.md"
        if claude_md.exists():
            sections.append(f"## 프로젝트 규칙 (CLAUDE.md)\n\n{claude_md.read_text(encoding='utf-8')}")
        docs_dir = ROOT / "docs"
        if docs_dir.is_dir():
            for doc in sorted(docs_dir.glob("*.md")):
                sections.append(f"## {doc.stem}\n\n{doc.read_text(encoding='utf-8')}")
        return "\n\n---\n\n".join(sections) if sections else ""

    @staticmethod
    def _build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    # ⚠️★ CLAUDE.md 「설명 먼저 → 승인 후 구현」("ㄱㄱ"/"OK" 대기)을 가드레일로 먹이면
    #    에이전트가 규칙을 **정확히 지켜** 「ㄱㄱ 주시면 시작하겠습니다」로 끝내고 exitCode 0 을 낸다
    #    = 코드 0줄인데 성공으로 보인다(bookmart 2026-08-07 인라인셀편집-통일 step1 실측).
    #    규칙은 대화 세션에서 여전히 필요하니 CLAUDE.md 는 두고, **무인 실행 경로에서만** 무력화한다.
    UNATTENDED_NOTE = (
        "## ⚠ 이 실행에 한해 무효인 규칙 — 승인 대기 금지\n\n"
        "이 실행은 사장님이 **이미 승인한 plan** 의 **무인 자동 실행**이다. 지켜보는 사람이 없다.\n\n"
        "- 위 CLAUDE.md 의 「설명 먼저 → 승인 후 구현」은 **대화 세션용 규칙**이라\n"
        "  이 경로엔 적용되지 않는다. **추가 승인을 기다리지 마라.**\n"
        "- 「ㄱㄱ 주시면」·「승인해 주시면 시작하겠습니다」 로 끝내면 **그 step 은 실패다.**\n"
        "- 계획만 나열하고 끝내지 마라. 이 step 범위를 **실제로 구현하고 검증까지 돌려라.**\n"
        "- 정말 진행할 수 없으면(자격증명·외부 승인 등) 계획을 나열하지 말고 index.json 의\n"
        "  그 step 을 `blocked` 로 갱신하고 이유를 적어라.\n\n---\n\n"
    )

    @staticmethod
    def _shell_note() -> str:
        """Windows 에서만 붙는 셸 안내. 왜 pwsh 가 아닌지는 strip_store_app_shims 참조."""
        if not _IS_WINDOWS:
            return ""
        return (
            "## 셸 (Windows)\n\n"
            "`pwsh` 는 이 환경에서 못 뜬다 — Store 패키지라 샌드박스 계정이 실행할 수 없다.\n"
            "PowerShell 스크립트는 `powershell -NoProfile -File <스크립트> <인자>` 로 돌려라.\n\n---\n\n"
        )

    def _build_preamble(self, guardrails: str, step_context: str,
                        prev_error: Optional[str] = None) -> str:
        retry_section = ""
        if prev_error:
            retry_section = (
                f"\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n"
                f"{prev_error}\n\n---\n\n"
            )
        return (
            f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{self.UNATTENDED_NOTE}"
            f"{self._shell_note()}"
            f"{self.UNATTENDED_NOTE}"
            f"{self._shell_note()}"
            f"{step_context}{retry_section}"
            f"## 작업 규칙\n\n"
            f"1. 이전 step에서 작성된 코드를 확인하고 일관성을 유지하라.\n"
            f"2. 이 step에 명시된 작업만 수행하라. 추가 기능이나 파일을 만들지 마라.\n"
            f"3. 기존 테스트를 깨뜨리지 마라.\n"
            f"4. AC(Acceptance Criteria) 검증을 직접 실행하라.\n"
            f"5. {PHASES_REL}/{self._phase_dir_name}/index.json의 해당 step status를 업데이트하라:\n"
            f"   - AC 통과 → \"completed\" + \"summary\" 필드에 이 step의 산출물을 한 줄로 요약\n"
            f"   - {self.MAX_RETRIES}회 수정 시도 후에도 실패 → \"error\" + \"error_message\" 기록\n"
            f"   - 사용자 개입이 필요한 경우 (API 키, 인증, 수동 설정 등) → \"blocked\" + \"blocked_reason\" 기록 후 즉시 중단\n"
            f"6. 직접 git commit 하지 마라. 하네스가 변경 파일을 명시 pathspec 으로 stage/commit 한다.\n\n---\n\n"
        )

    # --- Agent 호출 ---

    def _agent_command(self) -> list[str]:
        if self._agent.provider == "claude":
            cmd = ["claude", "-p", "--permission-mode", "acceptEdits", "--output-format", "json"]
            if self._agent.model:
                cmd += ["--model", self._agent.model]
            if self._agent.unsafe:
                cmd.append("--dangerously-skip-permissions")
            return cmd

        cmd = ["codex", "exec", "--cd", self._root, "--dangerously-bypass-hook-trust"]
        if self._agent.unsafe:
            # ⛔ `CreateProcessAsUserW failed: 5` 를 봤다고 여기서 샌드박스를 끄지 마라.
            # 원인은 샌드박스가 아니라 PATH 의 Store 앱 shim 이고 strip_store_app_shims 가
            # 고쳤다 — 끄면 그 수정을 무력화하고 보안만 낮춘다(bookmart 가 한 번 했다 되돌렸다).
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            # 샌드박스는 유지하되 네트워크만 연다 — 기본 차단이라 SSH/API 실측 step 이 전부 blocked 된다
            cmd += ["--sandbox", "workspace-write",
                    "-c", "sandbox_workspace_write.network_access=true"]
        if self._agent.model:
            cmd += ["--model", self._agent.model]
        cmd.append("-")
        return cmd

    def _agent_env(self) -> dict:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if not _IS_WINDOWS:
            return env

        path = strip_store_app_shims(env.get("PATH", ""))
        # WindowsApps 를 빼면 Store 판 `python` 도 같이 사라진다(이 PC 엔 그것뿐이다).
        # run.ps1·pytest.ini 가 쓰는 것과 같은 인터프리터를 앞에 붙여 대체한다
        # (pytest.exe·ruff.exe 도 같은 폴더에 있다 — 그 셋이 못 떠서 step 이 blocked 됐다).
        if self._venv_scripts:
            path = f"{self._venv_scripts}{os.pathsep}{path}"
        env["PATH"] = path
        return env

    def _run_agent_watched(self, cmd, prompt: str, env: dict, wall_limit: Optional[float] = None):
        """에이전트를 돌리되 **벽시계가 아니라 「진전 없음」으로** 자른다.

        왜 바꿨나 (2026-08-08):
          벽시계 상한은 나쁜 hang 탐지기다. 멀쩡히 일하던 P2b-3 를 30분에 죽였고
          (작업은 이미 끝나 커밋만 못 했다), 반대로 **아무 진전 없이 빠르게 헛도는 건
          못 잡는다.** 게다가 옛 코드는 `capture_output=True` 라 출력이 끝나야 보여서
          「도는 중인지 멈춘 건지」 알 방법 자체가 없었다 — 그래서 시간으로 자를 수밖에.

        그래서 셋을 바꾼다:
          1. `Popen` 으로 출력을 **흐르는 대로** 받는다 → 마지막 출력 시각을 안다
          2. `inactivity` 초 동안 **한 줄도 안 나오면** 끊는다 (진짜 hang)
          3. `timeout`(벽시계)은 남기되 **폭주 방지용 천장**이다 — 크게 잡는다

        ⛔ 무한대로 두지 않는다. 2026-08-08 에 러너를 죽였는데 자식이 살아남아
           codex 를 계속 재생성했다 — 상한이 없으면 그런 게 아무도 모르게 돈다.

        `wall_limit` 은 **이 시도에 남은 step 예산**이다(`_execute_single_step` 가 넘긴다).
        안 주면 종전대로 `AgentConfig.timeout` 을 그대로 쓴다.
        """
        limit = self._agent.timeout if wall_limit is None else wall_limit
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self._root,
            env=env,
        )

        chunks = {"out": [], "err": []}
        last = {"at": time.monotonic()}
        lock = threading.Lock()

        def _pump(stream, key):
            for raw in iter(stream.readline, b""):
                with lock:
                    chunks[key].append(raw)
                    last["at"] = time.monotonic()   # ← 이게 「진전」의 정의다
            stream.close()

        readers = [
            threading.Thread(target=_pump, args=(proc.stdout, "out"), daemon=True),
            threading.Thread(target=_pump, args=(proc.stderr, "err"), daemon=True),
        ]
        for t in readers:
            t.start()

        try:
            proc.stdin.write(prompt.encode("utf-8"))
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass   # 에이전트가 프롬프트를 다 안 읽고 끝낼 수 있다

        t0 = time.monotonic()
        killed = None
        while proc.poll() is None:
            time.sleep(1.0)
            now = time.monotonic()
            with lock:
                idle = now - last["at"]
            if self._inactivity and idle > self._inactivity:
                killed = f"{int(idle)}초 동안 출력이 한 줄도 없었다 (무응답 상한 {self._inactivity}초)"
                break
            if limit and (now - t0) > limit:
                # ⚠️ 이 문구에 `WATCHDOG_MARK`("무응답 상한")를 넣지 마라. 넣으면
                #    `_unwedge_watchdog_errors` 가 다음 회차에 pending 으로 되돌려
                #    **예산에 걸린 step 을 무한히 다시 돌린다** — 예산을 넣은 이유가 사라진다.
                killed = f"step 예산 {int(limit)}초 초과 — 이 step 에 쓸 시간을 다 썼다"
                break

        if killed:
            self._kill_tree(proc)
            print(f"\n  ERROR: {self._agent.provider} 를 끊었다 — {killed}")
            print(f"  ↳ 무응답 상한은 `-Inactivity <초>`, step 예산은 `-Timeout <초>` 로 조정한다.")

        proc.wait()
        for t in readers:
            t.join(timeout=5)

        out = b"".join(chunks["out"]).decode("utf-8", errors="replace")
        err = b"".join(chunks["err"]).decode("utf-8", errors="replace")
        if killed:
            err = (err + f"\n[harness] {killed}").strip()
        return (proc.returncode if not killed else 124), out, err

    @staticmethod
    def _kill_tree(proc):
        """자식까지 죽인다. 부모만 죽이면 손자가 살아남아 계속 돈다 —
        2026-08-08 에 러너를 죽였는데 codex 가 4분 뒤 새로 떴다."""
        try:
            if _IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True)
            else:
                proc.kill()
        except Exception:
            proc.kill()

    # ── 에이전트가 남긴 개발서버 수확 ──────────────────────────────────────
    # 왜 `_kill_tree` 로 부족한가 (2026-08-11 Coupang_v2 실측):
    #   step 이 화면 AC 를 검증하려고 `manage.py runserver` 를 띄우는데, 그걸 실행한
    #   셸이 명령을 끝내고 먼저 죽으면 서버가 **고아가 되어 프로세스 트리에서 빠진다.**
    #   그래서 나중에 `taskkill /T` 를 해도 안 잡힌다. 게다가 `_kill_tree` 는
    #   `killed`(감시가 끊었을 때)에만 불려서 **정상 종료 경로에는 아예 없다.**
    #   실측: 9시간 동안 runserver 24 프로세스·포트 10개가 쌓였고, 예산 초과로 끊긴
    #   step 이 남긴 서버 하나는 그 뒤로도 CPU 1,447초를 더 먹었다. 좀비가 쌓이면
    #   PC 가 느려지고 → 다음 step 이 더 오래 걸리고 → 잘릴 확률이 오르는 악순환이다.
    # 그래서 PID 트리가 아니라 **전후 스냅샷 차집합**으로 잡는다. 고아가 돼도 잡힌다.
    _STRAY_PATTERNS = ("runserver",)

    @classmethod
    def _snapshot_stray_pids(cls) -> set:
        """지금 떠 있는 '개발서버' PID 집합. Windows 전용, 실패하면 빈 집합(=청소 생략)."""
        if not _IS_WINDOWS:
            return set()
        pat = "|".join(cls._STRAY_PATTERNS)
        ps = (
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            f"Where-Object {{ $_.CommandLine -match '{pat}' }} | "
            "ForEach-Object {{ $_.ProcessId }}"
        ).replace("{{", "{").replace("}}", "}")
        try:
            out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True, timeout=30)
            return {int(x) for x in out.stdout.split() if x.strip().isdigit()}
        except Exception:
            return set()

    @classmethod
    def _reap_strays(cls, before: set, label: str = "") -> int:
        """`before` 이후 새로 생긴 개발서버만 거둔다. 거둔 개수를 돌려준다.

        ⚠️ 차집합이라 **이 step 이 만든 것만** 죽는다 — 사람이 미리 띄워둔 서버는
           `before` 에 들어 있어 안전하다. 무엇을 죽였는지 반드시 출력한다(조용한 kill 금지).
        """
        if not _IS_WINDOWS or not before and not cls._snapshot_stray_pids():
            return 0
        new = cls._snapshot_stray_pids() - before
        if not new:
            return 0
        print(f"  ↳ {label}이(가) 남긴 개발서버 {len(new)}개를 거둔다: "
              f"{', '.join(str(p) for p in sorted(new))}")
        for pid in new:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True, timeout=30)
            except Exception:
                pass
        return len(new)

    def _invoke_agent(self, step: dict, preamble: str, wall_limit: Optional[float] = None) -> dict:
        step_num, step_name = step["step"], step["name"]
        step_file = self._phase_dir / f"step{step_num}.md"

        if not step_file.exists():
            print(f"  ERROR: {step_file} not found")
            sys.exit(1)

        prompt = preamble + step_file.read_text(encoding='utf-8')
        env = self._agent_env()
        cmd = self._agent_command()
        # step 이 띄운 개발서버는 고아가 되어 트리에서 빠지므로 전후 차집합으로 거둔다.
        strays_before = self._snapshot_stray_pids()
        try:
            returncode, stdout, stderr = self._run_agent_watched(cmd, prompt, env, wall_limit)
        except FileNotFoundError:
            print(f"  ERROR: provider CLI not found: {self._agent.provider}")
            sys.exit(1)
        finally:
            # 끊겼든 정상 종료든 **항상** 거둔다 (`sys.exit` 도 finally 를 탄다).
            self._reap_strays(strays_before, f"step {step_num}")

        if returncode != 0:
            print(f"\n  WARN: {self._agent.provider}가 비정상 종료됨 (code {returncode})")
            if stderr:
                print(f"  stderr: {stderr[:500]}")

        result_raw = types.SimpleNamespace(returncode=returncode)

        output = {
            "step": step_num, "name": step_name,
            "provider": self._agent.provider,
            "model": self._agent.model,
            "exitCode": result_raw.returncode,
            "stdout": stdout, "stderr": stderr,
        }
        out_path = self._phase_dir / f"step{step_num}-output.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output

    # --- 헤더 & 검증 ---

    def _print_header(self):
        print(f"\n{'='*60}")
        print(f"  Harness Step Executor")
        print(f"  Phase: {self._phase_name} | Steps: {self._total}")
        print(f"  Provider: {self._agent.provider}")
        if self._agent.model:
            print(f"  Model: {self._agent.model}")
        if not self._manage_branch:
            print(f"  Branch management: disabled")
        if self._auto_push:
            print(f"  Auto-push: enabled")
        if not self._preflight_enabled:
            print(f"  Preflight: skipped")
        print(f"{'='*60}")

    WATCHDOG_MARK = "무응답 상한"

    def _unwedge_watchdog_errors(self, index) -> bool:
        """무응답 감시가 **끊어서** error 가 된 step 만 pending 으로 되돌린다.

        감시가 끊으면 에이전트가 index 의 status 를 못 써서 「Step did not update
        status」로 error 가 박힌다. 그 뒤로는 바로 아래 게이트가 1초 만에 exit(1) 해서
        **바깥(감독)의 재시도가 통째로 무의미해진다** — 2026-08-08 22:11~22:14 실측:
        감독이 `매입률-소급차단` 재시도 2회를 2분에 다 태웠고 codex 는 한 번도 안 떴다.
        그래서 오탐 하나가 phase 를 그날 밤 통째로 죽인다.

        ⛔ 사람이 봐야 할 진짜 실패(다른 exitCode)는 손대지 않는다 — 게이트는 그대로다.
        """
        changed = False
        for s in index["steps"]:
            if s.get("status") != "error":
                continue
            out = self._phase_dir / f"step{s['step']}-output.json"
            if not out.exists():
                continue
            try:
                d = json.loads(out.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if d.get("exitCode") != 124 or self.WATCHDOG_MARK not in (d.get("stderr") or ""):
                continue
            s["status"] = "pending"
            s.pop("error_message", None)
            s.pop("failed_at", None)
            changed = True
            print(f"  ↻ Step {s['step']}: 무응답 감시에 끊긴 흔적 — pending 으로 되돌려 다시 시도한다")
        if changed:
            self._write_json(self._index_file, index)
        return changed

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        self._unwedge_watchdog_errors(index)
        for s in reversed(index["steps"]):
            if s["status"] == "error":
                print(f"\n  ✗ Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print(f"  Fix and reset status to 'pending' to retry.")
                sys.exit(1)
            if s["status"] == "blocked":
                print(f"\n  ⏸ Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print(f"  Resolve and reset status to 'pending' to retry.")
                sys.exit(2)
            if s["status"] != "pending":
                break

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    # --- preflight ---
    #
    # 2026-08-08 에 phase 3개가 5회 헛돌고 완주 0회였는데, blocked_reason 은 전부
    # 엉뚱한 원인을 가리켰다("pytest 실행 차단"·"로컬 Python 런타임 없음"). 진짜
    # 원인은 codex 샌드박스가 Store 판 pwsh 를 못 띄운 것(`CreateProcessAsUserW
    # failed: 5`)이었고, 사람이 그 사유를 믿고 파이썬 쪽을 네 번 팠다.
    # step 을 부르기 전에 러너와 에이전트를 각각 한 번 직접 돌려, 실패면 사유를
    # 하네스가 적는다 — 에이전트의 추측 대신.

    def _preflight_python(self) -> Path:
        """pytest 를 돌릴 인터프리터. worktree 엔 .venv 가 없어 본체 것을 쓴다(`_venv_scripts`)."""
        if self._venv_scripts:
            exe = self._venv_scripts / ("python.exe" if os.name == "nt" else "python")
            if exe.exists():
                return exe
        return Path(sys.executable)

    def _preflight_tests(self) -> Optional[str]:
        """(a) 테스트 러너가 사나 — 수집 에러가 있으면 러너가 0 이 아닌 코드를 준다.

        ⚠️ **맨 `pytest` 가 모든 레포의 정본은 아니다.** 이 엔진은 여러 레포가 공용으로 쓴다.
           Coupang_v2 는 Django ORM 이 0개라 맨 pytest 가 맞지만, bookmart 는 Django 앱이라
           `DJANGO_SETTINGS_MODULE` 없이는 **수집 단계에서 233건이 죽는다**
           (`ImproperlyConfigured: Requested setting INSTALLED_APPS`, 2026-08-08 실측).
           그 레포 정본은 `pwsh _scripts/test.ps1`(config.settings_test·SQLite)이다.

        그래서 레포가 자기 검사 명령을 정할 수 있게 한다 — `verify.ps1` 과 같은 방식.
        `.dev/harness/preflight_tests.ps1` 이 있으면 그걸 쓰고, 없으면 종전대로 맨 pytest.
        """
        custom = ROOT / PREFLIGHT_TESTS_REL
        if custom.exists():
            cmd = ["powershell", "-NoProfile", "-File", str(custom)]
            label = "preflight_tests.ps1"
        else:
            py = self._preflight_python()
            cmd = [str(py), "-m", "pytest", "--collect-only", "-q"]
            label = f"{py.name} -m pytest --collect-only -q"
        try:
            r = subprocess.run(cmd, cwd=self._root, capture_output=True, text=True,
                               timeout=self.PREFLIGHT_TIMEOUT)
        except FileNotFoundError:
            return f"테스트 러너를 찾을 수 없다: {cmd[0]}"
        except subprocess.TimeoutExpired:
            return f"{label} 이 {self.PREFLIGHT_TIMEOUT}s 안에 안 끝났다"
        if r.returncode != 0:
            tail = (r.stdout or "") + (r.stderr or "")
            return (f"테스트 러너가 죽어 있다 — `{label}`"
                    f" exit {r.returncode}: {tail.strip()[-400:]}")
        return None

    def _preflight_agent(self) -> Optional[str]:
        """(b) 에이전트가 명령을 돌릴 수 있나.

        returncode 만으로는 못 잡는다 — 08-08 사고에서 codex 는 0 으로 끝나면서
        셸만 못 띄웠다. 그래서 셸에게 파일을 쓰게 하고 그 파일을 우리가 확인한다.
        """
        if self._agent.provider != "codex":
            return None  # claude 경로는 이 관문을 새로 채우지 않는다

        token = uuid.uuid4().hex[:12]
        sentinel = Path(self._root) / PREFLIGHT_SENTINEL
        sentinel.unlink(missing_ok=True)
        prompt = (
            "Harness preflight check. Do exactly one thing, then stop:\n"
            f"run the shell command `echo {token} > {PREFLIGHT_SENTINEL}` from the repo root.\n"
            "Do not read, edit, or explain anything else."
        )
        try:
            r = subprocess.run(self._agent_command(), input=prompt.encode("utf-8"),
                               cwd=self._root, capture_output=True,
                               timeout=self.PREFLIGHT_TIMEOUT, env=self._agent_env())
        except FileNotFoundError:
            return f"provider CLI 를 찾을 수 없다: {self._agent.provider}"
        except subprocess.TimeoutExpired:
            return f"{self._agent.provider} 가 {self.PREFLIGHT_TIMEOUT}s 안에 응답하지 않았다"

        got = ""
        if sentinel.exists():
            # pwsh 5 의 `>` 는 UTF-16LE 로 쓴다 — 널바이트를 걷어내고 본다.
            got = sentinel.read_bytes().replace(b"\x00", b"").decode("utf-8", "replace")
        sentinel.unlink(missing_ok=True)
        if token in got:
            return None

        out = (r.stderr or b"").decode("utf-8", "replace").strip() \
            or (r.stdout or b"").decode("utf-8", "replace").strip()
        return (f"{self._agent.provider} 가 셸 명령을 실행하지 못했다 (exit {r.returncode}) — "
                f"`{PREFLIGHT_SENTINEL}` 이 안 생겼다. 출력 꼬리: {out[-400:]}")

    def _run_preflight(self):
        print("  Preflight: 테스트 러너 · 에이전트 셸")
        reason = self._preflight_tests() or self._preflight_agent()
        if reason is None:
            return

        reason = f"preflight: {reason}"
        ts = self._stamp()
        index = self._read_json(self._index_file)
        index["blocked_reason"] = reason
        index["blocked_at"] = ts
        self._write_json(self._index_file, index)
        self._update_top_index("blocked", reason)

        print(f"\n  ⏸ Preflight 실패 — step 을 하나도 시작하지 않았다.")
        print(f"    Reason: {reason}")
        self._emit_reason(reason)
        sys.exit(2)

    # --- verification baseline ---

    def _verify_script_path(self) -> Path:
        return Path(self._root) / VERIFY_REL

    def _verify_command(self) -> list[str]:
        shell = "powershell.exe" if _IS_WINDOWS else "pwsh"
        cmd = [shell, "-NoProfile"]
        if _IS_WINDOWS:
            cmd += ["-ExecutionPolicy", "Bypass"]
        cmd += ["-File", str(self._verify_script_path())]
        return cmd

    @staticmethod
    def _coerce_process_output(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return str(value)

    def _run_verify_ps1(self) -> VerifyRun:
        script = self._verify_script_path()
        if not script.exists():
            return VerifyRun(available=False, reason="verify.ps1 없음")

        try:
            r = subprocess.run(
                self._verify_command(),
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=self.VERIFY_TIMEOUT,
            )
        except FileNotFoundError:
            return VerifyRun(
                available=True,
                returncode=127,
                reason="PowerShell 실행 파일을 찾을 수 없다",
            )
        except subprocess.TimeoutExpired as exc:
            return VerifyRun(
                available=True,
                returncode=124,
                reason=f"verify.ps1 이 {self.VERIFY_TIMEOUT}s 안에 안 끝났다",
                stdout=self._coerce_process_output(exc.stdout),
                stderr=self._coerce_process_output(exc.stderr),
            )

        return VerifyRun(
            available=True,
            returncode=r.returncode,
            stdout=r.stdout or "",
            stderr=r.stderr or "",
        )

    def _measure_verify_baseline(self):
        result = self._run_verify_ps1()
        self._verify_baseline = result
        self._verify_baseline_red = result.available and not result.ok

        if not result.available:
            return
        if result.ok:
            print("  Verification baseline: green")
            return

        detail = result.reason or f"verify.ps1 exit {result.returncode}"
        print(f"  Verification baseline: baseline 이 이미 빨강 — {detail}")

    @staticmethod
    def _verify_result_detail(result: VerifyRun) -> str:
        if result.reason:
            return result.reason

        output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part and part.strip()
        )
        if output:
            return f"verify.ps1 exit {result.returncode}: {output[-800:]}"
        return f"verify.ps1 exit {result.returncode}"

    def _verify_completed_step(self, index: dict, step_num: int, ts: str) -> Optional[str]:
        """Run repository verification after a step self-reports `completed`.

        Returns an error message when the step should be pushed back through the
        existing retry path. Missing verify.ps1 and already-red baselines keep
        the previous harness behavior.
        """
        if self._verify_baseline_red:
            detail = self._verify_result_detail(self._verify_baseline)
            print(f"  Verification: skipped — baseline 이 이미 빨강 ({detail})")
            return None

        result = self._run_verify_ps1()
        if not result.available:
            return None
        if result.ok:
            print("  Verification: green")
            return None

        err_msg = f"step 후 검증 실패 — {self._verify_result_detail(result)}"
        for s in index["steps"]:
            if s["step"] == step_num:
                s["status"] = "error"
                s["error_message"] = err_msg
                s["failed_at"] = ts
                s.pop("completed_at", None)
        self._write_json(self._index_file, index)
        # ⚠️ 여기서 AI_REASON 을 찍지 않는다. 이건 **중간** 실패일 수 있고, 재시도가 성공해도
        #    로그에 남은 마커를 `run_record.py` 가 주워가 성공한 회차를 실패로 기록한다.
        #    최종 실패 판정은 호출자(`_execute_single_step`)가 재시도를 다 쓴 뒤에 한다.
        return err_msg

    @staticmethod
    def _emit_reason(reason: str):
        """회차 기록(`run_record.py`)이 로그에서 주워갈 한 줄 마커."""
        print("AI_REASON=" + " ".join(reason.split()))

    # --- 실행 루프 ---

    def _execute_single_step(self, step: dict, guardrails: str) -> bool:
        """단일 step 실행 (재시도 포함). 완료되면 True, 실패/차단이면 False."""
        step_num, step_name = step["step"], step["name"]
        done = sum(1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed")
        prev_error = None
        # ★ 예산은 **step 하나 전체**에 준다 — 시도마다 새로 주면 상한이 사실상 없다.
        budget, t_step = self._agent.timeout, time.monotonic()

        for attempt in range(1, self.MAX_RETRIES + 1):
            left = (budget - (time.monotonic() - t_step)) if budget else None
            if left is not None and left <= 0:
                # 남은 예산 0 으로 새 시도를 띄우면 즉시 잘려 로그만 더럽힌다. 여기서 접는다.
                self._give_up_step(
                    step_num, step_name,
                    f"step 예산 {budget}초 소진 — {attempt - 1}회 시도 후 중단. "
                    f"직전 실패: {prev_error or '없음'}",
                )

            index = self._read_json(self._index_file)
            step_context = self._build_step_context(index)
            preamble = self._build_preamble(guardrails, step_context, prev_error)

            tag = f"Step {step_num}/{self._total - 1} ({done} done): {step_name}"
            if attempt > 1:
                tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

            with progress_indicator(tag) as pi:
                self._invoke_agent(step, preamble, left)
            elapsed = int(pi.elapsed)  # progress_indicator 는 finally 에서 채운다 — with 안이면 항상 0

            index = self._read_json(self._index_file)
            status = next((s.get("status", "pending") for s in index["steps"] if s["step"] == step_num), "pending")
            ts = self._stamp()

            if status == "completed":
                verify_error = self._verify_completed_step(index, step_num, ts)
                if verify_error is None:
                    for s in index["steps"]:
                        if s["step"] == step_num:
                            s["completed_at"] = ts
                            # 앞선 시도가 남긴 실패 흔적을 지운다 — 안 지우면 성공한 step 이
                            # `failed_at` 을 달고 남아 다음 세션이 「실패했었다」로 읽는다.
                            s.pop("failed_at", None)
                            s.pop("error_message", None)
                    self._write_json(self._index_file, index)
                    self._commit_step(step_num, step_name)
                    print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                    return True
                status = "error"

            if status == "blocked":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["blocked_at"] = ts
                self._write_json(self._index_file, index)
                reason = next((s.get("blocked_reason", "") for s in index["steps"] if s["step"] == step_num), "")
                print(f"  ⏸ Step {step_num}: {step_name} blocked [{elapsed}s]")
                print(f"    Reason: {reason}")
                self._emit_reason(reason)
                self._update_top_index("blocked", reason)
                sys.exit(2)

            err_msg = next(
                (s.get("error_message", "Step did not update status") for s in index["steps"] if s["step"] == step_num),
                "Step did not update status",
            )

            if attempt < self.MAX_RETRIES:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "pending"
                        s.pop("error_message", None)
                        # `failed_at` 도 같이 지운다 — 예전엔 error_message 만 지워서,
                        # 재시도가 성공해도 실패 시각이 남아 기록이 오염됐다.
                        s.pop("failed_at", None)
                self._write_json(self._index_file, index)
                prev_error = err_msg
                print(f"  ↻ Step {step_num}: retry {attempt}/{self.MAX_RETRIES} — {err_msg}")
            else:
                self._give_up_step(step_num, step_name,
                                   f"[{self.MAX_RETRIES}회 시도 후 실패] {err_msg}", elapsed)

        return False  # unreachable

    def _give_up_step(self, step_num: int, step_name: str, err_msg: str,
                      elapsed: Optional[int] = None):
        """이 step 을 최종 실패로 적고 런을 끝낸다 (재시도 소진 · 예산 소진 공용).

        ⛔ 여기서 조용히 다음 step 으로 넘어가지 않는다. step 은 앞 step 산출물 위에
           쌓이므로, 실패한 것을 건너뛰고 이어가면 뒤가 전부 헛돈다. 대신 사유를
           index 에 남기고 exit(1) 해서 **바깥 감독이 유한 횟수만 재시도**하게 한다
           (`harness_overnight.ps1` 의 `-MaxRetries`).
        """
        index = self._read_json(self._index_file)
        ts = self._stamp()
        for s in index["steps"]:
            if s["step"] == step_num:
                s["status"] = "error"
                s["error_message"] = err_msg
                s["failed_at"] = ts
        self._write_json(self._index_file, index)
        self._commit_step(step_num, step_name)
        took = f" [{elapsed}s]" if elapsed is not None else ""
        print(f"  ✗ Step {step_num}: {step_name} failed{took}")
        print(f"    Error: {err_msg}")
        self._emit_reason(err_msg)
        self._update_top_index("error", err_msg)
        sys.exit(1)

    def _execute_all_steps(self, guardrails: str):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s["status"] == "pending"), None)
            if pending is None:
                print("\n  All steps completed!")
                return

            step_num = pending["step"]
            for s in index["steps"]:
                if s["step"] == step_num and "started_at" not in s:
                    s["started_at"] = self._stamp()
                    self._write_json(self._index_file, index)
                    break

            self._execute_single_step(pending, guardrails)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index("completed")

        self._stage_paths(self._new_changed_paths())
        self._archive_phase_dir()
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = f"chore({self._phase_name}): mark phase completed"
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  ✓ {msg}")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode != 0:
                print(f"\n  ERROR: git push 실패: {r.stderr.strip()}")
                sys.exit(1)
            print(f"  ✓ Pushed to origin/{branch}")

        print(f"\n{'='*60}")
        print(f"  Phase '{self._phase_name}' completed!")
        print(f"{'='*60}")
        self._report_parent_plan(index)

    ARCHIVE_REL = ".dev/_archive/harness_phases"

    def _archive_phase_dir(self):
        """끝난 phase 폴더를 아카이브로 내린다 — `phases/` 에는 **진행 중인 것만** 남긴다.

        만들기(`plan_to_phase.py`)와 끝내기(여기)는 있는데 **치우기가 없었다.** `_finalize` 가
        자기 손으로 커밋하니 완료분이 main 으로 가고, 새 워크트리를 딸 때마다 끝난 일이 통째로
        딸려온다(2026-08-16 실측: 15개 전부 completed/폐기, 3.6M). 같은 걸 08-08 에 손으로 한 번
        치웠지만 **절차를 안 만들어** 8일 만에 재발했다 — 그래서 사람 손이 아니라 여기서 한다.

        ⚠️ 지우지 않는다. 최상위 `index.json` 의 항목과 `note`(「왜 기각했나」 같은 판단)도
        건드리지 않으므로, 목록과 이유는 그대로 남고 **폴더만** 시야에서 빠진다.

        `_stage_paths` **뒤**에 불러야 한다 — 그때 파일이 추적 상태라 `git mv` 가 먹고,
        이동이 그대로 같은 커밋에 담긴다.
        """
        dest_rel = f"{self.ARCHIVE_REL}/{self._phase_dir_name}"
        if (ROOT / dest_rel).exists():
            print(f"  Skip 아카이브: {dest_rel} 이 이미 있다")
            return
        arch_dir = ROOT / self.ARCHIVE_REL
        arch_dir.mkdir(parents=True, exist_ok=True)
        # ⚠️ 레포 `.gitignore` 는 `.dev/harness/phases/**/*-output.json` 만 막는다. 산출물을
        # 아카이브로 옮기면 그 규칙 **밖으로 나가** 수 MB 짜리 실행 로그가 커밋에 딸려간다.
        # 레포마다 .gitignore 를 손보게 하면 잊는 곳이 생기니, 아카이브 자리가 스스로 막는다.
        gitignore = arch_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("*-output.json\n", encoding="utf-8")
            self._run_git("add", "--", f"{self.ARCHIVE_REL}/.gitignore")
        r = self._run_git("mv", f"{PHASES_REL}/{self._phase_dir_name}", dest_rel)
        if r.returncode != 0:
            # 실패해도 phase 완료는 유효하다 — 아카이브만 못 한 것이니 알리고 넘어간다.
            print(f"  Skip 아카이브({dest_rel}): {r.stderr.strip()}")
            return

        # ⚠️ `git mv` 는 **추적 파일만** 옮긴다. gitignore 된 실행 산출물
        # (`step*-output.json` — 회차당 수 MB 다)이 그대로 남아 **빈 껍데기 폴더**가 된다.
        # 그러면 정리한 표시가 안 나고, 목록에 이름만 남아 「진행 중인 것뿐」이라는 약속이 깨진다.
        # 2026-08-16 본체 실측: 그렇게 남은 폴더 5개 · 9.7MB.
        src = ROOT / PHASES_REL / self._phase_dir_name
        if src.is_dir():
            for leftover in list(src.iterdir()):
                shutil.move(str(leftover), str(ROOT / dest_rel / leftover.name))
            src.rmdir()
        print(f"  ✓ 아카이브: {PHASES_REL}/{self._phase_dir_name} → {dest_rel}")

    # 진행판 마커. 상태는 네 가지다 — `[ ]` 미착수 · `[~]` 진행 · `[x]` 완료 · `[!]` 막힘.
    # ⚠️ 리스트(`- [x]`)만 세면 안 된다. 이 레포의 정본 진행판은 **마크다운 표**이고 셀이
    #    `**[x]**` · `` `[~]` `` 처럼 꾸며져 있다(2026-08-16: 리스트만 세다 실제 진행판을
    #    「체크박스 없음」으로 읽었다). 범례 줄(한 줄에 마커 넷)은 표도 리스트도 아니라 자동 제외된다.
    _LIST_MARK_RE = re.compile(r"^\s*[-*]\s*\[([ x~!X])\]")

    @classmethod
    def _progress_marks(cls, text: str) -> list[str]:
        marks: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                for cell in stripped.strip("|").split("|"):
                    cell = cell.strip().strip("*`").strip()
                    if len(cell) == 3 and cell[0] == "[" and cell[2] == "]" and cell[1] in " x~!X":
                        marks.append(cell[1])
            else:
                m = cls._LIST_MARK_RE.match(line)
                if m:
                    marks.append(m.group(1))
        return marks

    def _report_parent_plan(self, index: dict):
        """phase 를 닫은 뒤 **상위 계획으로 돌려보낸다.**

        하네스의 완료(=step 을 다 돌았다)와 레포의 완료(=상위 계획에 남은 건수 0)는 다르다.
        이 출력이 없으면 `Phase completed!` 가 마지막 줄이 되고, phase 하나가 끝나는 순간
        전체 계획이 시야에서 사라진다 — 2026-08-16 지적: "하네스를 굴리면 전체 계획을 잃고
        세부만 개발하다 끝난다". 숫자를 여기서 찍어야 사람도 다음 세션도 어디에 있는지 안다.
        """
        source_plan = index.get("source_plan")
        if not source_plan:
            print("\n  ⚠️ 상위 계획 미기재 — 이 phase 의 index.json 에 `source_plan` 이 없다.")
            print("     상위를 모르는 phase 는 끝나는 순간 맥락이 증발한다. 먼저 채워라.")
            return

        print(f"\n  └ 상위 계획: {source_plan}")
        plan_path = ROOT / source_plan
        if not plan_path.exists():
            print("     ⚠️ 그 파일이 없다(이사·삭제·오타). 경로부터 고쳐라 — 링크가 끊긴 phase다.")
            return

        marks = self._progress_marks(plan_path.read_text(encoding="utf-8"))
        if not marks:
            print("     진행판(체크박스)이 없다 — 남은 일은 사람이 눈으로 세야 한다.")
            return

        done = sum(1 for m in marks if m in "xX")
        blocked = marks.count("!")
        left = len(marks) - done
        print(f"     진행판: {done}/{len(marks)} 완료 · 남은 항목 {left}건" +
              (f" (그중 막힘 {blocked}건)" if blocked else ""))
        if left:
            print(f"     ⛔ 아직 끝이 아니다. 이 phase 로 닫힌 항목을 체크하고, 남은 {left}건 중에서 다음을 골라라.")
        else:
            print("     ✅ 남은 건수 0 — 상위 계획이 닫혔다. 사장님께 보고하라.")


def main():
    parser = argparse.ArgumentParser(description="Harness Step Executor")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument(
        "--provider",
        choices=["codex", "claude"],
        default=os.environ.get("BM_HARNESS_PROVIDER", "codex"),
        help="Non-interactive coding agent provider (default: codex)",
    )
    parser.add_argument("--model", help="Provider model alias/name")
    parser.add_argument("--timeout", type=int, default=AgentConfig.timeout,
                        help=f"벽시계 천장(초) — 폭주 방지용. 기본 {AgentConfig.timeout}")
    parser.add_argument("--inactivity", type=int, default=AgentConfig.inactivity,
                        help=f"이 초 동안 출력이 0줄이면 hang 으로 보고 끊는다. 기본 {AgentConfig.inactivity}")
    parser.add_argument(
        "--unsafe",
        action="store_true",
        help="Use provider-specific permission bypass flags. Only for externally sandboxed runs.",
    )
    parser.add_argument("--no-branch", action="store_true", help="Do not checkout/create feat-<phase> branch")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the runner/agent preflight gate. Only for environments that cannot run them anyway.",
    )
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    args = parser.parse_args()

    agent = AgentConfig(
        provider=args.provider,
        model=args.model,
        timeout=args.timeout,
        inactivity=args.inactivity,
        unsafe=args.unsafe,
    )
    StepExecutor(
        args.phase_dir,
        auto_push=args.push,
        agent=agent,
        manage_branch=not args.no_branch,
        preflight=not args.skip_preflight,
    ).run()


if __name__ == "__main__":
    main()
