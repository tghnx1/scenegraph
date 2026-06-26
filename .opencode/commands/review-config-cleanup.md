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

### Inventory Freeze hard gate

Inventory Freeze is a blocking read-only phase before any recommendation config migration.

Reject Inventory Freeze unless every listed tuning variable includes:

- exact variable name
- runtime default value
- runtime default source file and function/constant
- type
- validation rule or allowed range
- used-by path or function
- effect type
- proposed config section
- status: active, unresolved alias, or delete-candidate

Allowed runtime default sources:

- `DEFAULT_PROMOTER_RECOMMENDATION_SCORING` in `backend/app/recommendation_scoring.py`
- `DEFAULT_PROMOTER_SEGMENT_QUOTA_RATIOS` in `backend/app/recommendation_scoring.py`
- `DEFAULT_PROMOTER_SEGMENT_WARM_SHARE` in `backend/app/recommendation_scoring.py`
- explicit fallback defaults inside runtime `*_from_env` functions
- `promoter_feedback.py` `DEFAULT_*` constants

Forbidden default sources:

- tests
- `monkeypatch.setenv` values
- docs
- `.env.example`
- inferred values
- previously generated inventories

Tests may be used only for coverage, validation behavior, expected error messages, and override behavior. Tests must never be used as the source of runtime default values.

Hard-reject Inventory Freeze if:

1. Any default value comes from a test, monkeypatch, docs, `.env.example`, or inference.
2. Any listed variable does not exist in runtime code.
3. Any runtime tuning variable is omitted.
4. Any type is wrong.
5. Any validation rule or allowed range is wrong.
6. Any effect type is missing or speculative.
7. Any proposed config section is missing.
8. Any alias read through `env_float_alias` or equivalent is omitted or treated as active without proof.
9. `PROMOTER_REC_API_LIMIT_MAX` is omitted.
10. `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT` is omitted as a legacy alias.
11. `PROMOTER_REC_WARM_NETWORK_WEIGHT` is deleted, renamed, or treated as resolved without explicit proof.
12. `PROMOTER_FEEDBACK_*` names do not exactly match runtime variables loaded in `backend/app/promoter_feedback.py`.
13. `PROMOTER_REC_SEGMENT_QUOTA_*` is treated as int instead of normalized float ratios.
14. Inventory is marked frozen without explicit user acceptance.

Required `PROMOTER_FEEDBACK_*` runtime variables:

- `PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST`
- `PROMOTER_FEEDBACK_SIMILAR_POSITIVE_BOOST`
- `PROMOTER_FEEDBACK_MAX_TOTAL_BOOST`
- `PROMOTER_FEEDBACK_SIMILARITY_MIN`
- `PROMOTER_FEEDBACK_SIMILAR_PROMOTER_LIMIT`

Known alias variables that must be tracked as unresolved unless proven otherwise:

- `PROMOTER_REC_WARM_NETWORK_WEIGHT`
- `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT`

The inventory may only be called accepted/frozen after explicit user acceptance. Do not say `Config cleanup approved.` during Inventory Freeze.

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
