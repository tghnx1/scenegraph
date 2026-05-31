# Berlin Scene Graph — Algorithm Implementation Plan

## Why this file exists
This document turns the high-level scene graph idea into a concrete implementation order.

It answers four practical questions:
- what the canonical graph is
- what should be computed offline vs at request time
- where embeddings fit into the system
- how the current implementation compares to the intended design

---

## 1. Core Product Logic

We are not building a generic social graph.
We are building a Berlin nightlife graph that helps answer:

- which artists are actually close to my scene
- which promoters are realistic next targets
- which venues fit my style and current level
- which events are reachable opportunities, not only popular ones

The core principle stays:

**event-first, context-preserving, recommendation-ready**

---

## 2. Canonical Graph Model

### Canonical entities
- `Artist`
- `Event`
- `Promoter`
- `Venue`

### Canonical factual edges
- `Artist -> played_at -> Event`
- `Promoter -> organizes -> Event`
- `Event -> takes_place_at -> Venue`

These are the only first-class graph edges we should treat as source-of-truth in the first implementation.

### Important rule
Do **not** make `Artist -> Artist` a canonical stored edge in the initial graph.

Artist-to-artist similarity is a **derived relation**, not a source relation.
It should be computed later from:
- shared events
- shared promoters
- shared venues
- overlapping styles
- embedding similarity

---

## 3. Data Model Layers

The system should be thought of as four layers.

### Layer A — Source ingestion
Import real event data and preserve source fidelity.

### Layer B — Canonical graph
Build normalized entities and factual edges.

### Layer C — Enrichment
Add metrics, style signals, aggregated text, and embeddings.

### Layer D — Recommendation runtime
Use graph paths + similarity + ranking to produce opportunities and explanations.

---

## 4. Phase-by-Phase Algorithm

## Phase 1 — Event-first import

### Input
- Berlin events dataset
- artist biographies dataset

### Algorithm
For each event:
1. read event object
2. upsert venue by RA venue id
3. upsert artists by RA artist id
4. upsert promoters by RA promoter id
5. upsert genres by RA genre id
6. upsert event by RA event id
7. upsert join rows:
   - `event_artists`
   - `event_promoters`
   - `event_genres`
8. upsert event images
9. upsert raw event payload archive

After event import:
10. load artist biographies
11. enrich matching artists by RA artist id

### Output
- normalized relational graph tables
- idempotent import behavior
- preserved raw payloads and text fields

---

## Phase 2 — Canonical graph API

### Goal
Expose graph-shaped scene data for visualization and basic filtering.

### API shape
`GET /api/graph`

### Filters
- `genre`
- `dateFrom`
- `dateTo`
- `limit`
- later:
  - `promoter`
  - `venue`
  - `district`
  - `nodeTypes`

### Output contract
- `nodes`
- `links`

### Node types
- artist
- event
- promoter
- venue

### Initial graph behavior
Return:
- filtered events
- connected artists
- connected promoters
- connected venues
- factual links only

This phase is for **graph browsing**, not full recommendation logic yet.

---

## Phase 3 — Metrics and graph signals

### Goal
Compute cheap, explainable ranking ingredients.

### Per-artist metrics
- `events_count`
- `first_seen_at`
- `last_seen_at`
- `promoter_count`
- `venue_count`
- `coappearance_count`

### Per-promoter metrics
- `hosted_events_count`
- `active_months_count`
- `recurring_artists_count`

### Per-venue metrics
- `hosted_events_count`
- `active_months_count`
- `unique_promoters_count`
- `unique_artists_count`

### Per-event metrics
- `lineup_size`
- `interested_count`
- `recency_weight`

### Graph structural signals
- degree
- unique neighbors
- repeated pair strength
- recency-adjusted connection strength

These metrics should be precomputed offline where possible, then exposed through runtime ranking.

---

## Phase 4 — Style and text enrichment

### Goal
Represent scene semantics through text, not through coarse genre labels.

### Genre decision for MVP recommendations
Do **not** use genres as a recommendation scoring signal in the first version.

Genres can still exist as:
- simple filtering
- display metadata
- debugging context

But the recommendation algorithm should not say:

`same genre = similar`

For MVP scoring, similarity should come from:
- factual graph proximity
- event description embeddings
- artist biography embeddings

### Add richer style context
Build text profiles from fields that carry scene meaning.

### Artist text profile
Combine:
- biography
- fallback: titles/descriptions/lineup text from events the artist played
- recurring venue names
- recurring promoter names

### Event text profile
Combine:
- title
- description_text
- lineup_raw
- promoter names
- venue name

### Promoter text profile
Combine:
- promoter name
- hosted event titles/descriptions
- recurring artists
- recurring venues

### Venue text profile
Combine:
- venue name
- event titles/descriptions hosted there
- recurring promoters
- recurring artists

---

## Phase 5 — Embeddings and semantic similarity

### Recommendation
Do **not** introduce a second database for MVP.

Use:
- PostgreSQL for relational graph data
- `pgvector` in PostgreSQL for embeddings

### Why
- simpler infrastructure
- easier joins with graph tables
- enough for current project scale
- keeps algorithm logic in one database

### Important rule
Do **not** replace graph logic with embeddings.

Use a **hybrid model**:
- graph = factual structure
- embeddings = semantic similarity signal

### MVP embedding scope
Start with only:
- `event_embeddings`
- `artist_embeddings`

Promoter and venue recommendations can be derived from the events and artists
connected to them. Dedicated promoter and venue embeddings can come later.

### Offline embedding pipeline
For each event and artist:
1. build aggregated text profile
2. generate embedding vector offline
3. store vector with model version and source text hash
4. recompute only when source text changed

### Suggested storage
- `artist_embeddings`
- `event_embeddings`
- later: `promoter_embeddings`
- later: `venue_embeddings`

Each row should include:
- entity id
- source text
- embedding vector
- model name
- source hash
- updated at

### First similarity products
- artist-to-artist similarity
- event-to-event similarity
- artist-to-event affinity
- later: artist-to-promoter affinity
- later: artist-to-venue affinity

These should be treated as **derived relations**, not canonical ingestion edges.

---

## Phase 6 — Derived relations

### Derived relation examples
- `artist_similar_to_artist`
- `event_similar_to_event`
- `artist_affine_to_promoter`
- `artist_affine_to_venue`

### How they are produced
From weighted combinations of:
- shared events
- repeated co-lineups
- shared promoters
- shared venues
- embedding cosine similarity
- recency/activity adjustments

### Important design rule
Keep these derived relations in separate tables or views.

Do not mix them with canonical source edges, because they answer different questions:
- canonical edge = what happened
- derived edge = what seems close / relevant

---

## Phase 7 — Recommendation candidate generation

### Goal
Generate realistic candidate opportunities for a user.

### MVP input
Start with one seed artist:

`artistId`

The seed artist becomes the starting point for graph traversal and semantic
matching.

### Step 1 — build seed artist context

For seed artist `A`, collect factual graph context:

- events where `A` played
- co-lineup artists from those events
- venues of those events
- promoters of those events

Then collect semantic context:

- artist biography for `A`
- descriptions of events where `A` played
- lineup text from events where `A` played

This is the seed artist's scene neighborhood.

### Step 2 — controlled graph traversal

Do **not** run an unlimited graph search.

The graph can expand forever:

`Artist -> Event -> Venue -> Event -> Artist -> Event -> ...`

After a few hops, almost every artist can become connected through a popular
venue or promoter. That makes recommendations noisy.

For MVP, use controlled traversal with these rules:

#### Default max depth

`maxDepth = 3`

The endpoint may expose this as a tuning parameter:

```http
GET /api/recommendations?artistId=4353&limit=10&maxDepth=3
```

#### Allowed paths

Allow:

- `Artist A -> Event -> Artist`
- `Artist A -> Event -> Venue`
- `Artist A -> Event -> Promoter`
- `Artist A -> Event -> Venue -> Event`
- `Artist A -> Event -> Promoter -> Event`
- `Artist A -> Event -> Venue -> Event -> Artist`
- `Artist A -> Event -> Promoter -> Event -> Artist`

Stop after that.

Do not allow repeated artist expansion:

- `Artist -> Event -> Artist -> Event -> Artist -> ...`

This path grows too fast and becomes hard to explain.

#### Fan-out limits

Popular venues and promoters can explode the candidate set. Limit expansion:

- max events per venue: `20`
- max events per promoter: `20`
- max artists per expanded event: `30`

Use recency and embedding similarity to choose which events survive the fan-out
limit.

#### Embedding threshold

When expanding through venues or promoters, keep only semantically related
events:

- compare candidate event description embedding with the seed event profile
- default threshold: `minEventSimilarity = 0.72`

This means graph expansion creates possible candidates, and embeddings decide
which ones remain relevant.

### Step 3 — embedding candidate search

In parallel with graph traversal, use embeddings directly:

- find events with descriptions similar to the seed artist's event profile
- find artists with biographies similar to the seed artist biography/profile

This allows useful recommendations even when there is no direct co-lineup path.

### Candidate generation rules

#### Candidate artists
From:
- co-lineup artists
- artists from venue/promoter-expanded events
- artists with similar biography embeddings
- artists connected to semantically similar events

#### Candidate promoters
From:
- promoters from seed artist events
- promoters from semantically similar events
- promoters repeatedly appearing in the controlled neighborhood

#### Candidate venues
From:
- venues from seed artist events
- venues hosting semantically similar events
- venues repeatedly appearing in the controlled neighborhood

#### Candidate events
From:
- events from seed venues/promoters that pass semantic similarity threshold
- events with descriptions similar to seed artist events
- future or recent events connected to similar artists/promoters/venues

---

## Phase 8 — Scoring

### High-level scoring formula
For MVP:

`score = graph_score + embedding_similarity + activity_or_recency`

Recommended first weights:

```text
score =
  0.45 * graph_score
+ 0.40 * embedding_similarity
+ 0.15 * activity_or_recency
```

Do not include genre matching in this score yet.

### Signals

#### Graph score
Use:
- direct shared event
- shared venue through controlled traversal
- shared promoter through controlled traversal
- shorter path length
- repeated appearances in the seed neighborhood

Apply distance decay:

```text
depth 1: 1.00
depth 2: 0.70
depth 3: 0.40
```

Candidates below the useful depth/score threshold should be dropped.

#### Semantic similarity
Use:
- event description embedding similarity
- artist biography/profile embedding similarity

#### Activity or recency
Use as a small tie-breaker:
- recent events
- hosted events count
- artist event count
- event interested_count when present

Do not let popularity dominate the ranking.

### Recommendation
Start with a transparent weighted formula, not ML.
This keeps the system explainable and easier to debug.

### Tunable config

The first implementation should return the config used:

```json
{
  "config": {
    "maxDepth": 3,
    "maxEventsPerVenue": 20,
    "maxEventsPerPromoter": 20,
    "minEventSimilarity": 0.72,
    "graphWeight": 0.45,
    "embeddingWeight": 0.40,
    "recencyWeight": 0.15
  }
}
```

This makes the algorithm easy to adjust after we see real results.

---

## Phase 9 — Explanation layer

Each recommendation should be able to answer:
- why this node
- through which path
- based on which strong signals

### Example explanations
- `You played with Artist A, Artist A also played two events organized by Promoter P.`
- `Venue V hosts events whose descriptions are semantically similar to your recent event context.`
- `Artist B is close through a shared promoter and has a similar biography profile.`
- `Event E is close through Venue V and high event-description similarity.`

### Output shape should include
- target entity
- score
- config used
- explanation path
- top contributing signals

---

## 5. What the current implementation already matches

The current backend/frontend slice already matches the design in these ways:

- it is event-centered
- it returns graph-shaped `nodes` and `links`
- it already models factual `artist -> event` and `event -> venue` connectivity
- it supports filtering by genre and date
- it exposes graph data to the frontend, not just tables
- it has a first lightweight metric: `eventCount`
- it has normalized imported tables for artists, events, venues, promoters, and joins

This means the current implementation is a valid **Phase 2 MVP**.

---

## 6. What is still missing compared to the intended algorithm

The current implementation does **not** yet include:
- promoter support in the runtime graph endpoint
- canonical `event_promoters` runtime usage
- aggregated entity text profiles
- event description embeddings
- artist biography embeddings
- derived similarity relations
- controlled recommendation traversal
- recommendation scoring
- explanation outputs
- user-to-graph mapping

So the current code matches the **structural graph browsing layer**, but not yet the full recommendation engine.

---

## 7. Recommended implementation order starting tomorrow

1. Add promoter edges to `/api/graph` so runtime graph browsing matches the canonical graph.
2. Build event text profiles from title, description, lineup, venue, and promoter names.
3. Build artist text profiles from biography, with event text fallback when biography is missing.
4. Add `pgvector` and store `event_embeddings` plus `artist_embeddings`.
5. Implement controlled traversal from a seed artist with `maxDepth`, path rules, fan-out limits, and semantic thresholds.
6. Add recommendation candidate generation from graph candidates and embedding candidates.
7. Add transparent scoring without genre matching.
8. Add explanation paths and response config.
9. Add `GET /api/recommendations?artistId=...&limit=...&maxDepth=...`.
10. Tune weights after inspecting real results.

---

## 8. Final decision summary

### Canonical graph
- event-first
- artist/event/promoter/venue
- factual edges only

### Derived layer
- similarity and affinity edges come later
- artist-to-artist is derived, not canonical

### Semantics
- keep coarse genres as metadata/filter only
- do not use genres in MVP recommendation scoring
- use event description embeddings and artist biography embeddings for similarity
- use graph + embeddings together

### Traversal
- default `maxDepth = 3`
- expand only through allowed path types
- limit venue/promoter fan-out
- use embedding similarity to filter expanded events
- stop before repeated artist-to-event expansion

### Infrastructure
- keep PostgreSQL
- add `pgvector`
- do not introduce a second vector database yet
