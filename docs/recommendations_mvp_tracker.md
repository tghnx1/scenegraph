# Recommendations MVP Tracker

Last Updated: 2026-05-25
Owner: product + backend
Primary Endpoint: `GET /api/recommendations/artists/{artist_id}/promoters`

## Scope (MVP)

- [x] done: main user-facing flow is `Artist -> Recommended Promoters`
- [x] done: similar artists/events are internal evidence, not final product
- [x] done: endpoint centered on `/api/recommendations/artists/{artist_id}/promoters`
- [x] done: graph evidence layer included in response
- [x] done: same-promoter filtering remains enabled for event-similarity discovery
- [x] done: overfetch before strict filtering to preserve output `limit`
- [x] done: event similarity internal knobs moved to `.env` (no hardcoded candidate/overfetch/api-limit literals)
- [x] done: reasons enriched with names (artists and event titles)
- [x] done: frontend contract stabilization doc in one place (`docs/frontend-recommendations-contract.md`)
- [ ] todo: dedicated PR summary/changelog doc

## Progress Board

### Done

- `021a142`: removed unused promoter mood bonus weight from scoring config and code.
- `c75b9c4`: hybrid recommendation blending (semantic + graph + extracted styles).
- `ac1e301`: same-promoter filtering for event similarity discovery.
- `96b7cf7`: overfetch event candidates before same-promoter filtering.
- `995ed59`: promoter fields in event similarity responses.
- `d39f067`: interested-count size signal in similar-events rerank.
- `64f3dcb`: internal `eventSimilarity` in `Artist -> Promoters` now uses similar-events pipeline.
- `91064a0`: manual artist connections support + warm evidence details.
- `95ebcd2`: candidate/overfetch/API recommendation limits were introduced as runtime knobs; promoter-specific ones now live in `backend/app/recommendations/config.yaml`.
- `c296d77`: promoter reasons now include concrete names/titles instead of counts only.

### In Progress

- [ ] in_progress: calibration of scoring weights from real feedback cycles (config-driven for promoter recommendations, no hardcoded promoter weights).

### Next (Top Priority)

- [x] done: frontend contract doc for promoter recommendations (fields + debug contract + examples).
- [ ] todo: decide if warm-first top-N stays default or becomes mode-toggle.
- [ ] todo: add compact-mode reasons for UI (keep verbose reasons for debug/analyst mode).

### Blocked

- [ ] blocked: none currently.

## Decisions Log

- Keep MVP focused on promoter recommendation outcome, not a full multidirectional recommender.
- Event similarity is hybrid: symbolic overlap + embedding similarity.
- Graph/evidence is required and must explain ranking signals.
- Recommendation behavior keeps direct partner evidence visible, but ranking is driven by semantic, warm, event, scale, activity, and recency signals.
- Promoter recommendation and feedback tuning now live in `backend/app/recommendations/config.yaml`; other recommendation knobs may remain environment-configurable where they are still runtime-backed.

## Validation Snapshot

Recent validations:

- `tests/test_recommendation_scoring.py`: 15 passed
- targeted graph API checks around promoter recommendation debug/warm logic: passing

## Update Rule (How we maintain this)

After each recommendation-engine push:

1. Update `Last Updated` date.
2. Add commit hash + one-line impact to `Done`.
3. Move items between `todo/in_progress/blocked/done`.
4. Keep `Next` to maximum 3 active items.
