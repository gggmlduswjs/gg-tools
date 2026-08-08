---
description: Plan only; create research/plan with Codex handoff, no implementation
---

Follow the `/기획` command with the same `$ARGUMENTS`.

Important:

- Do not edit source code.
- Do not run tests or formatters.
- Do not use `git add`, `git commit`, or `git push`.
- First invoke the plugin skill `/grill-me` with the same `$ARGUMENTS`; if it is not available, stop and report that the plugin skill is not loaded.
- Produce or update `.dev/plans/{fe|be|arch}/<task>_plan.md`.
- Include complete `## Grill-me 결과` and `## Codex 인수인계` sections.
- End with `/실행 <plan-name>`, not raw PowerShell.
