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
    # 무응답으로 잘린 것과 **구별되는지**가 요점이다 (위 테스트는 "출력이 한 줄도 없었다" 를 본다).
    # ⚠️ 문구 대조라 코드가 말을 바꾸면 여기가 깨진다 — 실제로 `천장`→`step 예산` 으로 바뀔 때
    #    이 줄을 안 고쳐 한동안 빨간 채로 있었다(1ec966d).
    assert "step 예산" in err, err


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


def _phase(tmp, exit_code, stderr):
    """error 로 박힌 step 1개짜리 phase 를 만든다."""
    import json
    import tempfile
    d = Path(tempfile.mkdtemp(prefix=tmp))
    (d / "index.json").write_text(json.dumps({"steps": [
        {"step": 0, "name": "x", "status": "error",
         "error_message": "[3회 시도 후 실패] Step did not update status",
         "failed_at": "2026-08-08T22:00:00+09:00"}]}, ensure_ascii=False), encoding="utf-8")
    (d / "step0-output.json").write_text(
        json.dumps({"exitCode": exit_code, "stderr": stderr}, ensure_ascii=False), encoding="utf-8")
    self = ex.StepExecutor.__new__(ex.StepExecutor)
    self._phase_dir = d
    self._index_file = d / "index.json"
    return self, d


def _status(d):
    import json
    return json.loads((d / "index.json").read_text(encoding="utf-8"))["steps"][0]


def test_무응답으로_끊긴_step_은_다시_pending_이_된다():
    """감시가 끊으면 에이전트가 status 를 못 써 error 가 박힌다 → 바깥 재시도가 1초 만에 죽는다.

    2026-08-08 실측: 감독이 재시도 2회를 2분에 태우는 동안 codex 는 한 번도 안 떴다.
    """
    self, d = _phase("wd-kill-", 124, "[harness] 600초 동안 출력이 한 줄도 없었다 (무응답 상한 600초)")
    assert self._unwedge_watchdog_errors(self._read_json(self._index_file)) is True
    s = _status(d)
    assert s["status"] == "pending", s
    assert "error_message" not in s and "failed_at" not in s, s


def test_진짜_실패는_그대로_막는다():
    """오탐만 푼다 — 사람이 봐야 할 실패까지 풀면 게이트가 죽는다."""
    self, d = _phase("wd-real-", 1, "TypeError: 진짜로 터졌다")
    assert self._unwedge_watchdog_errors(self._read_json(self._index_file)) is False
    assert _status(d)["status"] == "error"


def test_게이트에_실제로_배선돼_있다():
    """함수만 있고 `_check_blockers` 가 안 부르면 아무것도 안 고친 것이다.

    (단위 검사는 함수를 직접 부르므로 배선이 빠져도 초록이다 — 그래서 게이트로 확인한다.)
    """
    self, d = _phase("wd-wire-", 124, "[harness] 600초 동안 출력이 한 줄도 없었다 (무응답 상한 600초)")
    try:
        self._check_blockers()                  # 오탐 → 막으면 안 된다
    except SystemExit as e:
        raise AssertionError(f"오탐인데 게이트가 exit({e.code}) 했다 — 배선이 빠졌다")
    assert _status(d)["status"] == "pending"

    self2, d2 = _phase("wd-wire2-", 1, "진짜 실패")
    try:
        self2._check_blockers()
    except SystemExit as e:
        assert e.code == 1, e.code
    else:
        raise AssertionError("진짜 실패인데 게이트가 안 막았다")


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
