"""무응답 감시 검사 — 시간이 아니라 「진전 없음」으로 자르는지.

벽시계로 자르면 멀쩡한 장시간 작업을 죽이고(2026-08-08 P2b-3), 빠르게 헛도는 건 못 잡는다.
그래서 셋을 본다: ① 조용하면 자른다 ② 떠들면 오래 돌아도 안 자른다 ③ 천장은 남아 있다.
"""
import subprocess
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_execute as ex


def _executor(inactivity, timeout):
    """StepExecutor.__init__ 는 phase 디렉터리를 요구한다 — 감시 로직만 쓰므로 우회한다."""
    self = ex.StepExecutor.__new__(ex.StepExecutor)
    self._root = str(Path(__file__).resolve().parent)
    self._agent = ex.AgentConfig(timeout=timeout, inactivity=inactivity)
    self._inactivity = inactivity
    return self


PY = sys.executable


def test_조용하면_자른다():
    """출력 없이 자기만 하는 프로세스 → 무응답 상한에 걸려야 한다."""
    self = _executor(inactivity=3, timeout=600)
    t0 = time.monotonic()
    rc, out, err = self._run_agent_watched([PY, "-c", "import time; time.sleep(60)"], "", None)
    elapsed = time.monotonic() - t0
    assert rc == 124, f"끊겼어야 한다 (rc={rc})"
    assert "출력이 한 줄도 없었다" in err, err
    assert elapsed < 15, f"3초 상한인데 {elapsed:.0f}초나 걸렸다"


def test_떠들면_상한을_넘겨도_안_자른다():
    """무응답 상한(2초)보다 오래(6초) 돌아도, 1초마다 출력하면 살아남아야 한다.

    ★ 이게 핵심이다 — 옛 벽시계 방식이면 여기서 죽었다."""
    self = _executor(inactivity=2, timeout=600)
    code = "import time,sys\nfor i in range(6):\n    print(i, flush=True)\n    time.sleep(1)\n"
    rc, out, err = self._run_agent_watched([PY, "-c", code], "", None)
    assert rc == 0, f"살아남았어야 한다 (rc={rc}, err={err[:200]})"
    assert "5" in out, out


def test_천장은_남아있다():
    """진전이 있어도 벽시계 천장을 넘으면 자른다 — 폭주 방지."""
    self = _executor(inactivity=600, timeout=3)
    code = "import time,sys\nfor i in range(60):\n    print(i, flush=True)\n    time.sleep(0.2)\n"
    rc, out, err = self._run_agent_watched([PY, "-c", code], "", None)
    assert rc == 124, f"천장에 걸렸어야 한다 (rc={rc})"
    assert "천장" in err, err


def test_무응답_기본값이_긴_검증명령을_덮는다():
    """600(10분)으로 되돌리면 빨개진다.

    codex 는 셸 도구가 **끝나야** 출력을 낸다 — 긴 명령 하나가 통째로 침묵이다.
    bookmart 2026-08-08 밤샘: 끊긴 step 8/8 이 `test.ps1 -Postgres orders` 실행 중이었고
    같은 명령이 완주한 회차는 903.9초였다. 그날 최장 완주 셸 호출은 1,116.8초.
    """
    assert ex.AgentConfig.inactivity >= 1200


def test_정상종료는_그대로():
    self = _executor(inactivity=30, timeout=600)
    rc, out, err = self._run_agent_watched([PY, "-c", "print('done')"], "", None)
    assert rc == 0 and "done" in out


def test_stdin_으로_프롬프트를_넘긴다():
    self = _executor(inactivity=30, timeout=600)
    rc, out, err = self._run_agent_watched([PY, "-c", "import sys; print(sys.stdin.read().strip())"], "안녕", None)
    assert rc == 0 and "안녕" in out, (rc, out, err)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                fails += 1
                print(f"  FAIL  {name} -- {e}")
    print(f"\n===== 실패 {fails} 건 =====")
    sys.exit(fails)
