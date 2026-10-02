---
name: existing-system-modernization
description: Preserve product decisions, user scenarios, current-system mapping, legacy classification, backend impact, architecture escalation, and detox when changing an already-running product. Use with Superpowers; do not replace its planning/TDD/debugging workflow.
---

# Existing System Modernization

Use this skill when changing an already-running product where old routes, screens, services, scripts, integrations, or duplicated business rules may coexist.

This skill does **not** replace Superpowers. Superpowers remains the development workflow engine. This skill only defines what an existing system must inspect and preserve before a plan is executed.

## 1. Capture product decisions

When the user makes a concrete product decision while discussing a screen or workflow — e.g. default sorting, visibility, permission, state behavior, merge/remove/keep, or required sequence — record it in the project's approved research/spec SSOT.

Give decisions stable IDs when the project supports it, e.g. `D-BOOK-001`, `D-ORDER-003`.

Do not leave important decisions only in chat, screenshots, canvas notes, or temporary agent scratch.

## 2. Define user scenarios when behavior changes

If the change affects a user workflow, document representative scenarios before implementation.

A scenario should identify:
- actor / role
- preconditions
- Given
- When steps
- Then outcomes
- related product decisions
- verification method

Prefer real workflows over exhaustive button combinations. Consider happy path, meaningful alternatives, empty/edge state, permission/state differences, and regression-critical flows only when relevant.

## 3. Map the current system

Before writing new implementation code, trace the current path as far as relevant:

```text
UI / API / CLI / scheduled job / entrypoint
→ controller / view / command
→ service / use case
→ query / repository / ORM
→ domain rule
→ model / table
→ external integration
→ side effect
```

The exact layers vary by project; do not invent layers just to match this diagram.

## 4. Classify legacy paths

Classify related existing routes/screens/services/scripts/integrations as:

- `KEEP` — current canonical path
- `MERGE` — behavior should move into the new canonical path
- `RETIRE` — replacement is complete; candidate for later removal
- `UNKNOWN` — usage evidence is insufficient

Never declare dead code from static references alone. Check runtime routes, scheduled jobs, manual operator workflows, dynamic calls, webhooks, external callbacks, and available usage evidence.

## 5. Triage backend impact

Choose one:

- `KEEP` — backend structure is adequate; do not refactor it
- `LOCAL REFACTOR` — clean only the code path touched by this feature
- `SEPARATE REFACTOR` — structural issue exists but should be handled in a separate backend/architecture plan

Do not let a UI change silently expand into an unrelated system rewrite.

## 6. Escalate architecture only with evidence

Escalate to a dedicated architecture/cartography effort when one or more of these patterns are repeatedly observed:

- competing implementations of the same core business rule/calculation
- a single feature repeatedly requires edits across 3+ domains/apps
- unclear data ownership or multiple competing write paths to the same business data
- persistence, external integration, and business rules are tightly coupled so dry-run/test isolation is impractical
- cyclic dependencies, cross-domain imports, or duplicate services repeatedly block changes
- production/data incidents trace back to boundary failures rather than isolated bugs

When escalated, first map current dependencies and target boundaries. Prefer staged migration and separate PRs over a big-bang rewrite.

## 7. Detox safely

Track paths made obsolete by the new canonical implementation. Delete only with strong evidence. Otherwise keep them marked `RETIRE` or `UNKNOWN` in the project's debt/detox registry or equivalent.

## 8. Verification has three possible axes

Depending on the change, validate separately:

1. **Product/Functional** — business decisions and functional tests
2. **Workflow** — documented user scenario and browser/E2E/acceptance test
3. **Visual** — approved visual contract and rendered comparison

Not every change needs all three. A backend-only change may not need Visual; a pure visual spacing change may reuse an existing workflow scenario.

## 9. Handoff to Superpowers

The approved research/spec should provide Superpowers with the relevant subset of:

- Target
- Product Decisions
- Use Case Scenarios
- Current System Map
- Legacy Classification
- Backend Impact
- Architecture Escalation
- Detox
- project-specific safety constraints

Superpowers then owns planning, TDD, execution, debugging, and verification. Do not recreate those methods here.
