---
description: Run endpoint cleanup with automatic review-gate iterations
agent: build
---

Run the endpoint cleanup loop until the Review Gate approves it.

You are the main implementation agent. The reviewer is `@review-gate`.

## Scope

Only work on endpoint cleanup blockers for the promoter recommendation product path.

Allowed work:

- Fix endpoint-cleanup test leftovers.
- Fix endpoint-cleanup docs leftovers.
- Fix syntax or indentation errors caused by endpoint cleanup.
- Clean formatting gaps caused by endpoint removal.
- Preserve approved `future_events/` deletion.

Forbidden work:

- Do not start weight cleanup.
- Do not refactor recommendation scoring.
- Do not weaken job lifecycle tests.
- Do not add compatibility stubs or legacy comments.
- Do not change frontend behavior.
- Do not touch unrelated files unless the user explicitly approved them.

## Required Loop

Repeat this loop until `@review-gate` says exactly:

Endpoint cleanup approved.

1. Inspect the current diff and Review Gate blockers.
2. Fix only the reported blockers.
3. Run:

```bash
python3 -m py_compile backend/app/routers/recommendations.py backend/tests/test_graph_api.py backend/tests/test_recommendation_jobs_load.py
```

4. Run:

```bash
rg "semantic/artists|recommendations/events|similar-events" frontend backend docs README.md
```

5. Run `/review-endpoint-cleanup` so `@review-gate` receives the current diff and verification output.
6. If `@review-gate` rejects, go back to step 1 and fix only the rejection reasons.
7. If `@review-gate` approves, stop immediately and report the final status.

## Deleted Public Endpoints

These public endpoints must not remain in live routes, docs, or tests:

- `/api/semantic/artists`
- `/api/recommendations/events/{id}`
- `/api/recommendations/events/{id}/similar-events`
- `/api/recommendations/artists/{id}/similar-events`

Allowed remaining references:

- Internal promoter event-similarity implementation.
- Docs explaining internal promoter event-similarity scoring for promoter recommendations.

## Contract Rules

- Initial recommendation job read must remain `queued`.
- Final recommendation job read must remain `completed`.
- Promoter recommendation tests must stay intact.
- Admin/debug surfaces are in scope only when they support promoter recommendation explainability.

Do not ask the user for approval between loop iterations unless a blocker falls outside this command scope.
