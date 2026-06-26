---
description: Review recommendation config cleanup with verification output
agent: config-gate
---

Review the current recommendation config cleanup diff and approve or reject it.

Use the attached command output as evidence. Do not edit files.

### Clarified rules enforced in this review

- This command reviews Phase 1 only: temporary `.env.example` hygiene.
- Phase 1 approval does not mean final recommendation config cleanup is complete.
- Removing a key from `.env.example` implies later relocation to dedicated recommendation config unless the key is proven to have no effect.
- Final config cleanup requires a dedicated recommendation config as the source of truth.
- Used promoter weights must live there; Python cannot be the permanent tuning source of truth.
- Weights with no effect on ranking, gating, or explainability must be deleted entirely.
- YAML/config-loader changes are not part of Phase 1.

## Current Git Status

```text
!`git status --short`
```

## Focused Config Cleanup Diff

```diff
!`git diff -- .env.example backend/app/recommendation_scoring.py backend/tests/test_recommendation_scoring.py`
```

## Warm Network Alias Search

```text
!`rg -n "PROMOTER_REC_WARM_NETWORK_WEIGHT" . 2>&1 || true`
```

## Recommendation Env Weight Search

```text
!`rg -n "PROMOTER_REC_|SEMANTIC_ARTIST_|RECOMMENDATION_|EVENT_RERANK|EVENT_GRAPH_|ARTIST_GRAPH_|ARTIST_REC_MIN_SEMANTIC_SCORE|PROMOTER_FEEDBACK_" .env.example 2>&1 || true`
```

## Python Compile Check

```text
!`python3 -m py_compile backend/app/recommendation_scoring.py 2>&1 || true`
```

## Review Criteria

Approve only if:

- Scope is limited to `.env.example` cleanup and proven alias-only removal.
- No YAML config or loader architecture was introduced.
- No ranking formula, gating threshold, cap, or scoring behavior was refactored.
- `.env.example` no longer exposes promoter/recommendation scoring weight noise.
- Operator-required env vars remain documented.
- `PROMOTER_REC_SCALE_FIT_WEIGHT=0.00` is gone from `.env.example`.
- `PROMOTER_REC_WARM_NETWORK_WEIGHT` is either untouched or fully removed after alias-only proof.
- Touched Python files compile.
- Relevant test status is reported.

If all Phase 1 checks pass, say exactly:

Config phase 1 approved.

Do not say `Config cleanup approved.` in this review. That phrase is reserved for the final dedicated-config phase.

If any check fails, reject and list only the blockers that must be fixed before re-review.
