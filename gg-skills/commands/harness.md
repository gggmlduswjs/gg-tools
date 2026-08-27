---
description: DEPRECATED — 새 개발 작업은 Superpowers workflow를 사용한다.
---

# /harness — deprecated

이 command는 기존 프로젝트 호환을 위해 임시로 남아 있다. **새 작업에는 사용하지 않는다.**

범용 개발 workflow의 정본은 Superpowers다.

- 아이디어/요구사항 → `brainstorming`
- 구현 계획 → `writing-plans`
- 실행 → `subagent-driven-development` 또는 `executing-plans`
- TDD → `test-driven-development`
- 디버깅 → `systematic-debugging`
- 완료 검증 → `verification-before-completion`

기존 `.dev/harness/phases/*`, `step*.md`, `execute.py` 기반 작업이 아직 진행 중인 경우에만 해당 프로젝트의 기존 문서를 따른다. 새 plan을 phase/step으로 다시 번역하지 않는다.

프로젝트의 `CLAUDE.md`/`AGENTS.md`에 DB·배포·worktree 같은 더 구체적인 안전 규칙이 있으면 그 규칙이 우선한다.
