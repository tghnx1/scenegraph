# Recommendations MVP Tracker

Last Updated: 2026-05-21
Owner: product + backend
Primary Endpoint: `GET /api/recommendations/artists/{artist_id}/promoters`

## Scope (MVP)

- [x] done: main user-facing flow is `Artist -> Recommended Promoters`
- [x] done: similar artists/events are internal evidence, not final product
- [x] done: endpoint centered on `/api/recommendations/artists/{artist_id}/promoters`
- [x] done: graph evidence layer included in response
- [x] done: defaults favor new opportunities (`exclude_existing=true`, `exclude_same_promoter=true`)
- [x] done: overfetch before strict filtering to preserve output `limit`
- [ ] todo: frontend contract stabilization doc in one place
- [ ] todo: dedicated PR summary/changelog doc

## Progress Board

### Done

- `12772d5`: default to new opportunities via `exclude_existing`.
- `c75b9c4`: hybrid recommendation blending (semantic + graph + extracted styles).
- `ac1e301`: same-promoter filtering for event similarity discovery.
- `96b7cf7`: overfetch event candidates before same-promoter filtering.
- `995ed59`: promoter fields in event similarity responses.
- `d39f067`: interested-count size signal in similar-events rerank.
- `64f3dcb`: internal `eventSimilarity` in `Artist -> Promoters` now uses the same `Similar Events` pipeline (no separate 1:1 path).

### In Progress

- [ ] in_progress: calibration of scoring weights from real feedback cycles (`.env`-driven, no hardcoded weights).

### Next (Top Priority)

- [ ] todo: add explicit debug counters for filtered candidates (`filteredOut`) in similar-events and promoter flow.
- [ ] todo: decide whether to keep/remove `GET /api/recommendations/artists/{artist_id}/similar-events` in strict MVP surface.
- [ ] todo: expose multi-promoter event context in response/debug (today response picks one promoter via lateral `LIMIT 1`).

### Blocked

- [ ] blocked: none currently.

## Decisions Log

- Keep MVP focused on promoter recommendation outcome, not a full multidirectional recommender.
- Event similarity is hybrid: symbolic overlap + embedding similarity.
- Graph/evidence is required and must explain ranking signals.
- Recommendation behavior should bias toward net-new opportunities by default.
- All scoring knobs should remain configurable through environment variables.

## Validation Snapshot

- API test suite validated after latest scoring refactor:
  - `tests/test_graph_api.py`: 28 passed
  - `tests/test_recommendation_scoring.py`: 23 passed (with text profile tests in same run)

## Update Rule (How we maintain this)

After each backend recommendation push:

1. Update `Last Updated` date.
2. Add commit hash + one-line impact to `Done`.
3. Move items between `todo/in_progress/blocked/done`.
4. Keep `Next` to maximum 3 active items.
