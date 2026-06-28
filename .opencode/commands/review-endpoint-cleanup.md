---
description: Review endpoint cleanup with verification output
agent: review-gate
---

Review the current endpoint cleanup diff and approve or reject it.

Use the attached command output as evidence. Do not edit files.

### Evidence requirements

Reject claims that are not proven by actual diffs or file contents.

Tracked file changes must be evidenced by `git diff`. Untracked files must be evidenced by direct content output or:

```text
git diff --no-index /dev/null <file> || true
```

If a report claims routes, tests, docs, validation, or cleanup was changed but the actual files do not prove it, reject.

If verification commands are missing, failed, or summarized without output, treat the work as not verified.

## Current Git Status

```text
!`git status --short`
```

## Endpoint Cleanup Diff

```diff
!`git diff -- backend/app/routers/recommendations.py backend/tests/test_graph_api.py backend/tests/test_recommendation_jobs_load.py docs/api.md`
```

## Approved Unrelated Cleanup

```diff
!`git diff --name-status -- future_events`
```

## Python Compile Check

```text
!`python3 -m py_compile backend/app/routers/recommendations.py backend/tests/test_graph_api.py backend/tests/test_recommendation_jobs_load.py 2>&1 || true`
```

## Deleted Public Endpoint Search

```text
!`rg -n "semantic/artists|recommendations/events|similar-events" frontend backend docs README.md 2>&1 || true`
```

## Review Criteria

Approve only if:

- `py_compile` is clean.
- Deleted public endpoints are gone from live routes, tests, and public docs:
  - `/api/semantic/artists`
  - `/api/recommendations/events/{id}`
  - `/api/recommendations/events/{id}/similar-events`
  - `/api/recommendations/artists/{id}/similar-events`
- Remaining `similar-events` references are only internal promoter event-similarity implementation or docs explaining promoter scoring internals.
- No partial leftover tests remain.
- No code uses `response` without making a request in the same test.
- Job lifecycle assertions are preserved:
  - initial read is `queued`
  - final read is `completed`
- No legacy comments, compatibility stubs, or commented-out deleted endpoints remain.
- No unrelated edits are included except approved `future_events/` deletion.

If all checks pass, say exactly:

Endpoint cleanup approved.

If any check fails, reject and list only the blockers that must be fixed before re-review.
