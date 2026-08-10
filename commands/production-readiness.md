---
description: Audit the current repo with the production readiness 5-axis checklist
---

Use the plugin skill `production-readiness-5axis` with `$ARGUMENTS`.

Rules:

- Do not edit files unless the user explicitly asks for fixes after the audit.
- Treat project-local `.claude/skills/*` as more specific than plugin-level skills.
- Distinguish what the plugin provides from what must remain project-local.
- Never run production DB writes, manual migrations, deployment, or external writes.

Output:

1. 5-axis table: performance, security, data safety, observability, harness quality.
2. Existing assets with file paths.
3. Missing or stale assets, ROI ordered.
4. One recommended next action.
