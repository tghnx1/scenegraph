---
description: Start orchestrated cleanup with automatic review-gate control
agent: cleanup-orchestrator
---

Start cleanup orchestration for the requested phase.

The user request is:

```text
$ARGUMENTS
```

Act as the single point of contact. Do not edit files directly.

Delegate scoped edits to `cleanup-implementer`, then review through the appropriate gate.

### Evidence-based completion

Do not report an implementation step as complete unless actual repository evidence proves it.

Require after every implementation step:

```text
git status --short
git diff --stat
focused git diff for modified tracked files
git diff --no-index /dev/null <file> || true  # for untracked files
```

If the evidence is missing or does not prove the claim, report `not verified` or failed instead of `done`.

### Clarified config cleanup rules

- Phase 1 is temporary `.env.example` hygiene only.
- Phase 1 approval does not mean final recommendation config cleanup is complete.
- Removing a key from `.env.example` implies relocation to dedicated recommendation config unless the key is proven to have no effect.
- Final approval requires a dedicated recommendation config as the source of truth.
- Used promoter weights must live there; Python cannot be the permanent tuning source of truth.
- Weights with no effect on ranking, gating, or explainability must be deleted entirely.
- YAML/config-loader changes belong to a later phase.

If the request is endpoint cleanup, coordinate implementation and review through `/review-endpoint-cleanup` until `@review-gate` says exactly:

Endpoint cleanup approved.

If the request is recommendation config cleanup Phase 1, coordinate implementation and review through `/review-config-cleanup` until `@config-gate` says exactly:

Config phase 1 approved.

Do not claim final recommendation config cleanup is complete until a later dedicated-config phase receives:

Config cleanup approved.

If no phase is clear, inspect `git status --short`, summarize the likely next phase, and ask one concise clarification before proceeding.
