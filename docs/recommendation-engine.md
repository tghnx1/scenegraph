# Recommendation Engine

This document describes the current recommendation-engine work in the `codex/recommendation-engine` branch.

The current implementation is a backend foundation for recommendation logic. It is not yet the final user-facing recommendation product.

## Current implementation

The current branch implements several building blocks:

- normalized text profiles for artists and events
- OpenAI / Azure OpenAI embedding generation
- stored entity embeddings
- semantic similarity ranking
- LLM-based artist biography tag extraction
- style overlap scoring
- graph overlap scoring
- artist-to-artist recommendations
- artist-to-promoter recommendations
- recommendation feedback storage
- graph evidence output for promoter recommendations

## Data model

The recommendation system currently uses these main entities:

- Artist
- Event
- Venue
- Promoter
- Genre
- EntityEmbedding
- ArtistExtractedTag
- ArtistTagExtractionRun
- RecommendationFeedback

Core graph relations:

- EventArtist: connects events and artists
- EventPromoter: connects events and promoters
- EventGenre: connects events and genres
- Event.venueId: connects events and venues

## Text profiles

Recommendation inputs are built from normalized text profiles.

Artist profiles may include:

- artist name
- biography
- normalized biography
- extracted style information
- extracted tags

Event profiles may include:

- event title
- description
- lineup text
- venue information
- genre information
- promoter information

These text profiles are used as embedding inputs and are stored with a hash so embeddings can be regenerated only when the source text changes.

## Embeddings

Embeddings are stored in the `entity_embeddings` table.

Each embedding is identified by:

- entity type
- entity id
- model key
- dimensions
- text hash

The model key includes the provider, for example:

```text
openai:text-embedding-3-small
azure:<deployment-name>
```

Supported providers:

- OpenAI
- Azure OpenAI

Embedding generation is run through:

```bash
make generate-embeddings
```

## Artist tag extraction

Artist biographies can be processed with an LLM to extract structured tags.

Supported tag types:

- style
- label
- collective
- role
- residency
- alias

Each extracted tag stores:

- artist id
- tag type
- tag value
- source
- confidence
- extractor key
- optional evidence phrase

Extraction is run through:

```bash
make extract-artist-tags
```

The extraction layer supports:

- OpenAI Chat Completions
- Azure OpenAI Chat Completions
- Azure OpenAI Responses API

## Current recommendation endpoints

### Semantic artist similarity

```text
GET /api/semantic/artists/{artist_id}
```

Returns artists ranked by semantic profile similarity.

Signals include:

- embedding similarity
- style overlap
- extracted tag overlap

### Artist recommendations

```text
GET /api/recommendations/artists/{artist_id}
```

Returns artist recommendations for a source artist.

Current scoring combines:

- semantic score
- graph overlap score
- style score
- extracted tag score
- embedding score

### Promoter recommendations for an artist

```text
GET /api/recommendations/artists/{artist_id}/promoters
```

Returns promoters connected to semantically similar artists.

Current scoring combines:

- semantic similarity to related artists
- number of matched artists
- related event count
- promoter activity score
- recency score

The response also includes graph evidence connecting:

```text
source artist -> similar artist -> event -> promoter -> venue
```

## MVP scope (current target)

MVP focuses on one flow only:

- artist -> recommended promoters

Current API contract for this MVP:

```text
GET /api/recommendations/artists/{artist_id}/promoters
```

The final output is promoters. Similar artists are an internal signal for finding promoters, not the final recommendation output.

Signal families for this MVP:

### 1) `semantic_artist_bridge`

- Graph path:
  `source artist -> similar artist -> event -> promoter`
- What it means:
  We find artists that are semantically close to the source artist (embeddings + style/tag overlap), then collect promoters from those artists' events.
- Why it matters:
  This is the strongest cold-start bridge when the source artist has little direct promoter history.
- Example explanation text:
  `"Connected through semantically similar artists who played promoter events in your neighborhood."`

### 2) `direct_connection`

- Graph path:
  `source artist -> event -> promoter`
- What it means:
  Promoters that already booked events where the source artist played.
- Why it matters:
  Highest-trust evidence of real-world reachability and proven fit.
- Example explanation text:
  `"You already played events organized by this promoter."`

### 3) `warm_network`

- Graph path:
  `source artist -> shared event -> co-played artist -> other event -> promoter`
- What it means:
  Promoters reached via artists that shared lineups with the source artist and have additional promoter relationships elsewhere.
- Why it matters:
  Captures near-network opportunities that are more reachable than purely global similarity.
- Example explanation text:
  `"Artists you shared lineups with also work with this promoter at other events."`

### 4) `event_similarity`

- Graph path:
  `source artist -> source event -> similar event -> promoter`
- What it means:
  Promoters connected to events similar to the source artist's event context (venue/genre/lineup/promoter neighborhood).
- Why it matters:
  Expands discovery beyond direct history while preserving scene fit.
- Example explanation text:
  `"This promoter runs events similar to the ones you already play."`

Implementation note for current FastAPI backend:

- The endpoint already implements the `semantic_artist_bridge` family and returns graph evidence.
- `direct_connection`, `warm_network`, and `event_similarity` are planned additions for the same endpoint and should be introduced incrementally with tests after each step.

### Recommendation feedback

```text
POST /api/recommendation-feedback
GET  /api/recommendation-feedback
```

Stores explicit feedback for recommendation candidates.

Current feedback values:

- positive
- negative
- hidden

This is currently stored but not yet deeply integrated into the ranking algorithm.

## What is not finished yet

The real recommendation engine is still planned.

Missing or incomplete parts:

- user-based preference model
- user onboarding / taste profile
- user interaction history as ranking input
- venue recommendations
- event recommendations as a first-class public endpoint
- promoter recommendations beyond the current artist-based flow
- reachability scoring
- stronger path explanations
- score calibration
- feedback-aware reranking
- frontend recommendation page
- frontend explanation panel
- API docs for external consumers

## Planned real recommendation engine

The target recommendation engine should support multiple recommendation directions:

```text
user -> artists
user -> events
user -> venues
user -> promoters
artist -> artists
artist -> promoters
artist -> venues
artist -> events
event -> similar events
venue -> relevant artists/events
promoter -> relevant artists/events
```

The final engine should combine these signal families:

### 1. Semantic similarity

Based on embeddings generated from normalized artist and event profiles.

### 2. Style similarity

Based on normalized style tags from event descriptions, artist biographies, and extracted tags.

### 3. Graph proximity

Based on shared events, venues, promoters, genres, and artists.

### 4. Strength of connection

Based on repeated overlaps, number of shared events, number of shared promoters, and related activity volume.

### 5. Recency

Recent events and recent activity should have higher weight than stale connections.

### 6. Reachability

Reachability should prevent recommendations from being dominated only by very large or globally famous nodes.

Potential reachability signals:

- hop distance
- shared neighborhoods
- activity gap
- style fit
- repeated overlaps
- scene proximity

### 7. User feedback

Explicit feedback should influence future rankings.

Examples:

- positive feedback increases similar candidates
- negative feedback lowers similar candidates
- hidden feedback removes specific candidates from future results

## Explanation output

Every recommendation should eventually explain why it was shown.

Good explanation examples:

```text
Recommended because this promoter books 4 artists with a similar EBM / dark disco profile.
```

```text
Recommended because this venue repeatedly hosts events with artists connected to your selected artist.
```

```text
Recommended because the artist shares label and style tags with your source artist and appears in the same promoter neighborhood.
```

The final explanation contract should include:

- relation path
- strongest overlap signal
- shared tags or styles
- score breakdown
- confidence / score
- graph evidence

## Suggested next implementation order

### Step 1: stabilize current backend foundation

- keep current endpoints working
- add API docs
- improve README
- verify tests
- document seed/import flow

### Step 2: make current recommendations explainable

- expose score breakdown consistently
- expose graph paths consistently
- add explanation text generation from deterministic templates
- avoid LLM-generated explanations in the first version

### Step 3: add venue recommendations

- recommend venues for source artist
- use similar artists -> events -> venues evidence
- score by semantic relevance, activity, recency, and venue overlap

### Step 4: add event recommendations

- promote event recommendations to a public endpoint
- rank events by semantic similarity, artist overlap, venue/promoter overlap, recency, and style fit

### Step 5: add user profile support

- store user preferences
- store liked/hidden/negative items
- build a user text profile and graph profile
- generate user-based recommendations

### Step 6: frontend integration

- recommendation page
- recommendation cards
- graph evidence view
- explanation panel
- feedback buttons

## Current limitation

At the moment, the project has strong backend ingredients but does not yet have a finished recommendation product. The current branch should be described as:

```text
recommendation-engine foundation
```

not as:

```text
complete production recommendation engine
```

This distinction should stay explicit in README and demo documentation.
