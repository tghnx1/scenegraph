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

### Calibration Run (2026-05-21)

- Scope:
  - 10 artists benchmarked with `GET /api/recommendations/artists/{id}/promoters?limit=20&debug=true`
  - Artist sample: `60, 273, 27, 251, 142, 18, 1796, 892, 277, 253`
- Baseline vs tuned (`.env`) comparison:
  - `avgEventSimilarityContribution`: `0.0409 -> 0.0590` (`+44.3%`)
  - `avgWarmContribution`: `0.0542 -> 0.0725` (`+33.9%`)
  - `warmRecommendationShare`: `0.665 -> 0.740`
  - `eventSimilarityPositiveShare`: `0.825 -> 0.845`
  - `top1` promoter changed only for `1/10` artists in the sample
  - `avg top20 overlap`: `16.1 / 20` (avg Jaccard `0.7402`)
- Filter diagnostics (sum across sample):
  - `excludeExisting`: `70`
  - `eventSimilaritySamePromoter`: `976`
  - `recommendationLimitCutoff`: `3061`
  - `eventSimilarityLimitCutoff`: `0`
- Tuned `.env` weights used in this run:
  - `PROMOTER_REC_SEMANTIC_WEIGHT=0.30`
  - `PROMOTER_REC_STRENGTH_WEIGHT=0.15`
  - `PROMOTER_REC_DIRECT_CONNECTION_WEIGHT=0.15`
  - `PROMOTER_REC_WARM_NETWORK_WEIGHT=0.14`
  - `PROMOTER_REC_EVENT_SIMILARITY_WEIGHT=0.22`
  - `PROMOTER_REC_ACTIVITY_WEIGHT=0.07`
  - `PROMOTER_REC_RECENCY_WEIGHT=0.07`
  - `PROMOTER_REC_EVENT_SIMILARITY_SYMBOLIC_WEIGHT=0.65`
  - `PROMOTER_REC_EVENT_SIMILARITY_EMBEDDING_WEIGHT=0.35`
  - `PROMOTER_REC_EVENT_SIMILARITY_SAME_VENUE_WEIGHT=0.45`
  - `PROMOTER_REC_EVENT_SIMILARITY_SHARED_GENRE_WEIGHT=0.05`
  - `PROMOTER_REC_EVENT_SIMILARITY_SHARED_LINEUP_WEIGHT=0.20`
  - `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT=0.30`

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
