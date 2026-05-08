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
Represent scene semantics more accurately than coarse platform genres alone.

### Keep coarse genres
RA / source genres remain useful for:
- simple filtering
- fallback categorization
- cheap coarse segmentation

### Add richer style context
Build text for each entity from available sources.

### Artist text profile
Combine:
- biography
- coarse genres
- titles/descriptions of played events
- recurring promoters
- recurring venues

### Event text profile
Combine:
- title
- description
- lineup names
- promoter names
- venue name
- coarse genres

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

### Offline embedding pipeline
For each entity type:
1. build aggregated text profile
2. generate embedding vector offline
3. store vector with model version and source text hash
4. recompute only when source text changed

### Suggested storage
- `artist_embeddings`
- `event_embeddings`
- `promoter_embeddings`
- `venue_embeddings`

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
- artist-to-promoter affinity
- artist-to-venue affinity

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
- style overlap
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

### User mapping inputs
- known artists
- known past events
- optionally claimed profile / biography
- optionally preferred genres or styles

### Candidate generation rules

#### Candidate artists
From:
- co-lineup artists
- artists on similar events
- artists from nearby promoters/venues

#### Candidate promoters
From:
- promoters connected to artists the user is near
- promoters repeatedly appearing in the user neighborhood

#### Candidate venues
From:
- venues connected to nearby artists/promoters
- venues hosting semantically similar events

#### Candidate events
From:
- future or recent events connected to similar artists/promoters/venues

---

## Phase 8 — Scoring

### High-level scoring formula
`score = proximity + strength + semantic_similarity + relevance + reachability`

### Signals

#### Proximity
- shorter path length is better

#### Strength
- repeated interactions matter more than single encounters

#### Semantic similarity
- embedding similarity between text profiles

#### Relevance
- activity, followers, hosted events, interested counts

#### Reachability
- prefer opportunities close to the user’s current scene level
- penalize jumps that are too large

### Recommendation
Start with a transparent weighted formula, not ML.
This keeps the system explainable and easier to debug.

---

## Phase 9 — Explanation layer

Each recommendation should be able to answer:
- why this node
- through which path
- based on which strong signals

### Example explanations
- `You played with Artist A, Artist A also played two events organized by Promoter P.`
- `Venue V repeatedly hosts artists similar to your recent scene cluster.`
- `Event E is close to your profile through shared artists and high semantic text similarity.`

### Output shape should include
- target entity
- score
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

This means the current implementation is a valid **Phase 2 MVP**.

---

## 6. What is still missing compared to the intended algorithm

The current implementation does **not** yet include:
- real event-first import over the 5-year Berlin dataset
- promoter support in the runtime graph endpoint
- canonical `event_promoters` runtime usage
- coarse genre join-table usage from imported data
- raw payload archive usage
- style extraction
- aggregated entity text profiles
- embeddings
- derived similarity relations
- recommendation scoring
- explanation outputs
- user-to-graph mapping

So the current code matches the **structural graph browsing layer**, but not yet the full recommendation engine.

---

## 7. Recommended implementation order starting tomorrow

1. Replace seed-only graph data with the real normalized import schema.
2. Implement idempotent event-first import for the 5-year Berlin dataset.
3. Add promoter tables and runtime promoter edges to `/api/graph`.
4. Keep coarse source genres as filter and metadata.
5. Compute basic counts and recency metrics offline.
6. Build aggregated text profiles per entity.
7. Add `pgvector` and offline embedding generation.
8. Compute derived similarity tables.
9. Add recommendation candidate generation.
10. Add ranking and explanation responses.

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
- keep coarse genres
- add embeddings for richer meaning
- use graph + embeddings together

### Infrastructure
- keep PostgreSQL
- add `pgvector`
- do not introduce a second vector database yet
