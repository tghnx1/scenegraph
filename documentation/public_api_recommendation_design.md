# Public API Recommendation Module Design

## 1. Purpose

This document defines the module we can delegate to a teammate:

**Build a secured public API that returns ready SceneGraph recommendation results.**

This is not the internal API used by our frontend. The public API is an external
contract for people or services that receive an API key and want to query our
SceneGraph data.

The main product value is not raw database access. The main product value is:

- ranked recommendations
- explanation paths through the graph
- a small graph payload that proves why the recommendation exists

---

## 2. API Boundaries

### Internal app API

Used by our own frontend.

Current examples:

- `GET /api/graph`
- `GET /api/venues`

This API can change more freely because it belongs to our app.

### Public API

Used by external users with API keys.

Recommended namespace:

- `/api/public/...`

Every public route must require:

- `X-API-Key` header
- rate limiting
- documented request and response shape

Do not expose raw write access to core tables such as `events`, `artists`,
`venues`, or `promoters`.

---

## 3. Main Product Contract

### Main endpoint

```http
GET /api/public/recommendations?artistId=4353&limit=10
```

The endpoint receives a seed entity and returns a ready recommendation result.

Initial MVP should support:

- `artistId`

Later it can support:

- `eventId`
- `venueId`
- `promoterId`
- `targetTypes=artist,event,venue,promoter`
- `genre`
- `dateFrom`
- `dateTo`

### Response shape

```json
{
  "seed": {
    "type": "artist",
    "id": 4353,
    "name": "BabaBass3000"
  },
  "recommendations": [
    {
      "type": "venue",
      "id": 91,
      "name": "Example Club",
      "score": 0.87,
      "reason": "This venue repeatedly hosts artists connected through techno events.",
      "signals": {
        "sharedGenres": ["techno"],
        "sharedEvents": 2,
        "sharedVenues": 1,
        "graphDistance": 2
      },
      "path": [
        { "type": "artist", "id": 4353, "name": "BabaBass3000" },
        { "type": "event", "id": 162548, "name": "Example Event" },
        { "type": "venue", "id": 91, "name": "Example Club" }
      ]
    }
  ],
  "graph": {
    "nodes": [],
    "links": []
  }
}
```

The public API should return an already useful result. External users should not
need to reconstruct the graph themselves.

---

## 4. Required Public Endpoints

Minimum set for the module:

```http
GET /api/public/recommendations
POST /api/public/recommendations/query
GET /api/public/graph
GET /api/public/search
GET /api/public/artists/{id}
GET /api/public/events/{id}
GET /api/public/venues/{id}
```

This gives more than the required 5 endpoints and keeps the recommendation
endpoint as the main value.

### Endpoint responsibilities

| Endpoint | Purpose |
| --- | --- |
| `GET /api/public/recommendations` | Main public result endpoint for simple query params. |
| `POST /api/public/recommendations/query` | Same result, but accepts a JSON body for complex filters. It does not mutate core data. |
| `GET /api/public/graph` | Returns a graph neighborhood around a seed entity. |
| `GET /api/public/search` | Finds artists, events, venues, and promoters by text. |
| `GET /api/public/artists/{id}` | Returns public artist details. |
| `GET /api/public/events/{id}` | Returns public event details. |
| `GET /api/public/venues/{id}` | Returns public venue details. |

Optional if the evaluator expects explicit CRUD-like verbs:

```http
POST /api/public/saved-queries
PUT /api/public/saved-queries/{id}
DELETE /api/public/saved-queries/{id}
```

These should save API-client query presets, not edit core scene data.

---

## 5. Backend Logic

### Suggested files

Add small modules instead of growing `backend/app/main.py` forever:

- `backend/app/public_api.py`
- `backend/app/api_keys.py`
- `backend/app/rate_limit.py`
- `backend/app/recommendations.py`

`main.py` should register the public router:

```python
app.include_router(public_router, prefix="/api/public")
```

### API key dependency

Public routes should depend on an API key check:

```http
X-API-Key: sg_live_xxx
```

Rules:

- missing key returns `401`
- invalid or revoked key returns `403`
- valid key allows request
- store only key hashes in the database
- never commit raw keys

Recommended key generation:

- local script or Make target creates a key
- script prints the raw key once
- database stores only the hash

### Rate limiting

MVP is allowed to use in-memory rate limiting:

- key: API key id
- limit: for example `100 requests / minute`
- too many requests returns `429`

Later, if multiple backend containers exist, move limiter state to Redis or
Postgres.

### Recommendation service

The recommendation service should be a normal Python function, not hidden inside
route code.

Example shape:

```python
def build_recommendations(seed_type: str, seed_id: int, limit: int) -> RecommendationResponse:
    ...
```

MVP logic for `artistId`:

1. Load the seed artist.
2. Load seed artist events.
3. Load connected genres, venues, promoters, and co-lineup artists.
4. Generate candidates:
   - venues connected through seed events or similar events
   - promoters connected through seed events or similar events
   - artists sharing events, venues, promoters, or genres
   - events sharing genres, venues, promoters, or connected artists
5. Score candidates with simple explainable signals.
6. Build explanation paths.
7. Return ranked recommendations and graph payload.

No ML is required for MVP. The first version should be explainable and stable.

### Example score ingredients

```text
score =
  0.35 * shared_genre_score
+ 0.25 * shared_event_score
+ 0.20 * shared_venue_or_promoter_score
+ 0.10 * recency_score
+ 0.10 * activity_score
```

The score does not need to be perfect. It needs to be explainable.

---

## 6. Database Logic

### Existing graph tables

Use current imported tables:

- `artists`
- `events`
- `venues`
- `promoters`
- `genres`
- `event_artists`
- `event_promoters`
- `event_genres`

### New tables for public API

Add at least:

```text
api_keys
```

Recommended columns:

- `id`
- `name`
- `key_hash`
- `created_at`
- `revoked_at`
- `last_used_at`

Optional:

```text
api_request_logs
saved_queries
```

Do not store public API keys as plain text.

---

## 7. Frontend Logic

The public API is not primarily for our frontend, but we should still have a demo
surface so evaluators can see it.

Recommended frontend route:

```text
/public-api-demo
```

This page can show:

- API key input field
- seed artist id input
- `limit` input
- "Run recommendation API" button
- response cards
- explanation path
- optional raw JSON preview

Frontend should call:

```http
GET /api/public/recommendations?artistId=...&limit=...
```

with:

```http
X-API-Key: user-entered-key
```

Important:

- Do not hardcode real API keys into frontend source.
- Do not use public API endpoints as the normal internal graph app API.
- The demo page exists to prove the public API works.

---

## 8. Documentation Logic

Update:

- `docs/api.html`
- optionally `documentation/public_api_usage.md`

Docs must include:

- what the public API is for
- how to send `X-API-Key`
- how rate limiting works
- endpoint list
- request examples
- response examples
- error examples

Required error examples:

```http
401 Missing API key
403 Invalid or revoked API key
429 Rate limit exceeded
422 Invalid query params
```

---

## 9. Tests

Minimum backend tests:

- public route without key returns `401`
- public route with invalid key returns `403`
- public route with valid key returns `200`
- rate limit returns `429`
- recommendations endpoint returns:
  - `seed`
  - `recommendations`
  - `graph`
- recommendation links reference existing graph nodes

Manual test examples:

```bash
curl http://localhost:8080/api/public/recommendations?artistId=4353
```

Expected: `401`

```bash
curl \
  -H "X-API-Key: $SCENEGRAPH_API_KEY" \
  "http://localhost:8080/api/public/recommendations?artistId=4353&limit=10"
```

Expected: `200`

---

## 10. Delegation Plan

### Teammate owns

- API key table and migration
- API key validation dependency
- rate limiter
- public API router
- recommendation response contract
- at least 5 public endpoints
- API docs update
- tests

### They should not own

- redesigning the existing frontend graph page
- changing import scripts unless needed for missing data
- adding auth/user accounts
- exposing writes to core scene data
- building perfect recommendation science

---

## 11. Definition of Done

The module is done when:

1. `GET /api/public/recommendations` returns a graph recommendation result from
   real Postgres data.
2. Public API routes require `X-API-Key`.
3. Missing key returns `401`.
4. Invalid key returns `403`.
5. Too many requests returns `429`.
6. At least 5 public endpoints exist.
7. Docs explain every public endpoint.
8. Frontend has a small demo surface or documented curl flow.
9. Tests cover auth and recommendation response shape.

The defense explanation should be:

> Our public API does not expose raw tables as the main product. It exposes a
> ready graph recommendation result: ranked targets, scores, explanation paths,
> and the graph evidence behind the recommendation.
