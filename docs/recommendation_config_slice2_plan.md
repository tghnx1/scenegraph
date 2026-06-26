# Recommendation Config Slice 2 Plan

Status: accepted plan. Implementation may begin only when explicitly authorized by the user.

Purpose: introduce a dedicated recommendation config file and strict loader without changing runtime behavior.

Slice 2 is config introduction only. Existing env/runtime code remains authoritative until later slices.

## Allowed Files

Slice 2 may touch only:

- `backend/app/recommendation_config.yaml`
- `backend/app/recommendation_config_loader.py`
- `backend/tests/test_recommendation_config_loader.py`
- `backend/requirements.txt`

Slice 2 must not edit:

- `backend/app/recommendation_scoring.py`
- `backend/app/promoter_feedback.py`
- `backend/app/recommendation_services.py`
- routers
- `.env.example`
- runtime consumers

## Dependency

The config format is YAML. `backend/requirements.txt` must include PyYAML.

## YAML Requirements

`backend/app/recommendation_config.yaml` must mirror the frozen Slice 1 inventory exactly.

Top-level sections:

- `promoter_recommendations`
- `promoter_feedback`
- `metadata`

`promoter_recommendations` must include:

- active `PROMOTER_REC_*` values from the frozen inventory
- all 9 exact `PROMOTER_REC_SEGMENT_QUOTA_*` keys
- `PROMOTER_REC_API_LIMIT_MAX`

`promoter_feedback` must include:

- all `PROMOTER_FEEDBACK_*` values from `backend/app/promoter_feedback.py`
- hardcoded promoter feedback tuning constants:
  - `PROMOTER_PROFILE_EVENT_LIMIT`
  - `SHARED_ARTISTS_WEIGHT`
  - `SHARED_GENRES_TAGS_WEIGHT`
  - `SIMILAR_EVENTS_WEIGHT`
  - `SHARED_VENUES_WEIGHT`

`metadata.legacy_aliases` must track:

- `PROMOTER_REC_WARM_NETWORK_WEIGHT` -> `PROMOTER_REC_CO_PLAYED_CONNECTION_WEIGHT`
- `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT` -> `PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_GENRE_WEIGHT`

Legacy aliases are metadata only. The loader must not expose them as active scoring fields.

## Loader Requirements

`backend/app/recommendation_config_loader.py` must:

- load YAML with PyYAML
- validate exact schema
- reject missing keys
- reject extra keys
- reject wrong types
- reject invalid ranges
- return typed/frozen config objects or equivalent immutable structures
- not read env
- not change runtime behavior
- not be consumed by runtime logic in Slice 2

Segment quota validation:

- each quota ratio must be `>= 0`
- each source segment row total must be `> 0`
- do not require rows to sum to exactly `1.0`

## Tests

`backend/tests/test_recommendation_config_loader.py` must use real schema keys only.

Required tests:

- happy path loads canonical config
- missing key is rejected
- extra key is rejected
- wrong type is rejected
- invalid range is rejected
- segment quota row total `0` is rejected
- legacy aliases are metadata and not active fields

## Verification

Run:

```bash
python3 -m py_compile backend/app/recommendation_config_loader.py backend/tests/test_recommendation_config_loader.py
docker compose exec backend pytest tests/test_recommendation_config_loader.py -q
```

After implementation, show:

```bash
git status --short
git diff --stat
git diff -- backend/requirements.txt
git diff --no-index /dev/null backend/app/recommendation_config.yaml || true
git diff --no-index /dev/null backend/app/recommendation_config_loader.py || true
git diff --no-index /dev/null backend/tests/test_recommendation_config_loader.py || true
```

If the evidence does not prove the implementation, report `not verified` instead of `done`.

## Hard Stop

Do not proceed to Slice 3.

Do not request final config approval.

