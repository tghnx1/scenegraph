# Recommendation Config Slice 1 Frozen Inventory

Status: accepted/frozen by user.

Purpose: authoritative baseline for recommendation config migration. Slice 2 and later must use this inventory as the source of truth. Runtime defaults must come from code, not tests, docs, `.env.example`, or generated summaries.

## Runtime Default Sources

- `backend/app/recommendations/scoring.py`
  - `DEFAULT_PROMOTER_RECOMMENDATION_SCORING`
  - `DEFAULT_PROMOTER_SEGMENT_QUOTA_RATIOS`
  - `DEFAULT_PROMOTER_SEGMENT_WARM_SHARE`
  - `promoter_recommendation_api_limit_max_from_env()`
- `backend/app/recommendations/promoter_feedback.py`
  - `DEFAULT_*` feedback constants
  - hardcoded promoter feedback tuning constants

## Promoter Recommendation Active Config Values

All entries belong to config section `promoter_recommendations` unless stated otherwise.

| Variable | Default | Type | Validation | Effect | Status |
|---|---:|---|---|---|---|
| `PROMOTER_REC_SEMANTIC_WEIGHT` | `0.25` | float | `>= 0`, normalized group | ranking, explainability | active |
| `PROMOTER_REC_STRENGTH_WEIGHT` | `0.16` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_CO_PLAYED_CONNECTION_WEIGHT` | `0.16` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_MANUAL_CONNECTION_WEIGHT` | `0.09` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_WEIGHT` | `0.10` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_SCALE_FIT_WEIGHT` | `0.08` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_ACTIVITY_WEIGHT` | `0.02` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_RECENCY_WEIGHT` | `0.01` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_STRENGTH_MATCHED_ARTIST_WEIGHT` | `0.60` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_STRENGTH_EVENT_WEIGHT` | `0.40` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_STRENGTH_MATCHED_ARTIST_CAP` | `5` | int | `> 0` | cap | active |
| `PROMOTER_REC_STRENGTH_EVENT_CAP` | `20` | int | `> 0` | cap | active |
| `PROMOTER_REC_WARM_CONNECTION_CAP` | `3` | int | `> 0` | cap | active |
| `PROMOTER_REC_MANUAL_WARM_CONNECTION_CAP` | `1` | int | `> 0` | cap | active |
| `PROMOTER_REC_MANUAL_WARM_MIN_ARTIST_SEMANTIC_SCORE` | `0.45` | float | `0 <= value <= 1` | gating | active |
| `PROMOTER_REC_EVENT_SIMILARITY_COUNT_CAP` | `8` | int | `> 0` | cap | active |
| `PROMOTER_REC_EVENT_SIMILARITY_MIN_TOTAL_SCORE` | `0.45` | float | `0 <= value <= 1` | gating | active |
| `PROMOTER_REC_EVENT_SIMILARITY_MIN_EMBEDDING_SCORE` | `0.0` | float | `0 <= value <= 1` | gating | active |
| `PROMOTER_REC_EVENT_SIMILARITY_PER_PROMOTER_LIMIT` | `20` | int | `> 0` | limit | active |
| `PROMOTER_REC_EVENT_SIMILARITY_SEMANTIC_ONLY` | `false` | bool | bool | behavior switch | active |
| `PROMOTER_REC_EVENT_SIMILARITY_SYMBOLIC_WEIGHT` | `0.6` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_EMBEDDING_WEIGHT` | `0.4` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_SAME_VENUE_WEIGHT` | `0.5` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_SHARED_GENRE_WEIGHT` | `0.1` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_SHARED_LINEUP_WEIGHT` | `0.2` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_GENRE_WEIGHT` | `0.3` | float | `>= 0`, normalized group | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_SHARED_MOOD_BONUS` | `0.02` | float | `>= 0` | ranking | active |
| `PROMOTER_REC_ACTIVITY_EVENT_CAP` | `25` | int | `> 0` | cap | active |
| `PROMOTER_REC_WARM_RELEVANT_CONNECTION_MIN` | `1` | int | `> 0` | gating | active |
| `PROMOTER_REC_WARM_EDGE_STRENGTH_MIN` | `0.5` | float | `0 <= value <= 1`, min <= max | ranking | active |
| `PROMOTER_REC_WARM_EDGE_STRENGTH_MAX` | `0.8` | float | `0 <= value <= 1`, min <= max | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MIN` | `0.2` | float | `0 <= value <= 1`, min <= max | ranking | active |
| `PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MAX` | `0.7` | float | `0 <= value <= 1`, min <= max | ranking | active |
| `PROMOTER_REC_SCALE_FIT_ALPHA` | `75.0` | float | `> 0` | ranking | active |
| `PROMOTER_REC_SCALE_FIT_TAU` | `0.55` | float | `> 0` | ranking | active |
| `PROMOTER_REC_SQL_CANDIDATE_LIMIT` | `200` | int | `> 0` | limit | active |
| `PROMOTER_REC_SEMANTIC_ARTIST_POOL_LIMIT` | `20` | int | `> 0` | limit | active |
| `PROMOTER_REC_SEMANTIC_ARTIST_MIN_SCORE` | `0.45` | float | `0 <= value <= 1` | gating | active |
| `PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MULTIPLIER` | `20` | int | `> 0` | limit | active |
| `PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MIN` | `500` | int | `> 0` | limit | active |
| `PROMOTER_REC_SOURCE_EVENT_RELEVANCE_GATE_ENABLED` | `true` | bool | bool | behavior switch | active |
| `PROMOTER_REC_SOURCE_EVENT_RELEVANCE_MIN_EMBEDDING_SCORE` | `0.45` | float | `0 <= value <= 1` | gating | active |
| `PROMOTER_REC_SOURCE_EVENT_RELEVANCE_TOP_K` | `6` | int | `> 0` | limit | active |
| `PROMOTER_REC_API_LIMIT_MAX` | `50` | int | `> 0` | API limit | active |
| `PROMOTER_REC_SEGMENT_WARM_SHARE` | `0.70` | float | `0 <= value <= 1` | quota | active |

## Segment Quota Matrix

Segment quota keys are exact generated runtime keys. They are float ratios, not ints. Runtime normalizes rows, so validation is: every value `>= 0` and each source row total `> 0`.

| Variable | Default |
|---|---:|
| `PROMOTER_REC_SEGMENT_QUOTA_SMALL_SMALL` | `0.50` |
| `PROMOTER_REC_SEGMENT_QUOTA_SMALL_MEDIUM` | `0.35` |
| `PROMOTER_REC_SEGMENT_QUOTA_SMALL_LARGE` | `0.15` |
| `PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_SMALL` | `0.15` |
| `PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_MEDIUM` | `0.50` |
| `PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_LARGE` | `0.35` |
| `PROMOTER_REC_SEGMENT_QUOTA_LARGE_SMALL` | `0.15` |
| `PROMOTER_REC_SEGMENT_QUOTA_LARGE_MEDIUM` | `0.35` |
| `PROMOTER_REC_SEGMENT_QUOTA_LARGE_LARGE` | `0.50` |

## Promoter Feedback Config Values

All entries belong to config section `promoter_feedback`.

| Variable | Default | Type | Validation | Effect | Status |
|---|---:|---|---|---|---|
| `PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST` | `0.10` | float | `>= 0` | reranking | active |
| `PROMOTER_FEEDBACK_SIMILAR_POSITIVE_BOOST` | `0.03` | float | `>= 0` | reranking | active |
| `PROMOTER_FEEDBACK_MAX_TOTAL_BOOST` | `0.15` | float | `>= 0` | reranking cap | active |
| `PROMOTER_FEEDBACK_SIMILARITY_MIN` | `0.30` | float | `0 <= value <= 1` | reranking gate | active |
| `PROMOTER_FEEDBACK_SIMILAR_PROMOTER_LIMIT` | `10` | int | `>= 1` | reranking scope | active |

## Hardcoded Promoter Feedback Tuning Constants

These are not env vars, but they affect promoter feedback similarity/reranking and must not be silently excluded from the no-hardcoded-tuning migration plan.

| Constant | Default | Type | Validation | Effect | Status |
|---|---:|---|---|---|---|
| `PROMOTER_PROFILE_EVENT_LIMIT` | `20` | int | `>= 1` | profile scope limit | active |
| `SHARED_ARTISTS_WEIGHT` | `0.45` | float | `>= 0`, normalized group | reranking similarity | active |
| `SHARED_GENRES_TAGS_WEIGHT` | `0.25` | float | `>= 0`, normalized group | reranking similarity | active |
| `SIMILAR_EVENTS_WEIGHT` | `0.20` | float | `>= 0`, normalized group | reranking similarity | active |
| `SHARED_VENUES_WEIGHT` | `0.10` | float | `>= 0`, normalized group | reranking similarity | active |

## Metadata-Only Unresolved Aliases

These must be tracked but not exposed as active scoring fields in Slice 2.

| Alias | Alias for | Status |
|---|---|---|
| `PROMOTER_REC_WARM_NETWORK_WEIGHT` | `PROMOTER_REC_CO_PLAYED_CONNECTION_WEIGHT` | unresolved alias |
| `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT` | `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_GENRE_WEIGHT` | unresolved alias |
