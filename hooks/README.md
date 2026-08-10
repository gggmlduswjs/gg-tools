# hooks — Claude Code 공용 훅 엔진

레포 shim(`.claude/hooks/*.py`)이 `runpy` 로 여기를 부른다. **로직은 여기 한 벌.**

## tdd_guard.py

PreToolUse[Write|Edit] — 가드 범위 소스를 고칠 때 테스트 참조가 없으면 `ask`(기본).

환경변수 (shim 이 설정):
- `TDD_GUARDED` — 콤마 구분 path 토큰 (예: `/src/orders/services/`)
- `TDD_TESTS` — 테스트 루트 glob (예: `src/*/tests,tests`)
- `TDD_DECISION` — `ask`(기본) 또는 `deny` (데모 프로젝트식 하드 차단)

self-test: `python ~/claude/hooks/tdd_guard.py --selftest`
