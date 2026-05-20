# Recommendation Engine

This document describes the recommendation-engine work in the `codex/recommendation-engine` branch.

The current implementation is a backend foundation for recommendation logic. The current MVP target is not a generic multi-direction recommender. The current MVP target is one polished flow:

```text
Artist -> Recommended Promoters
```

The final user-facing output is a ranked list of promoters. Similar artists, events, and graph paths are supporting evidence used to explain why each promoter is relevant.

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

## MVP scope

MVP focuses on one recommendation flow only:

```text
Selected Artist -> Recommended Promoters
```

The user selects an artist. The system recommends promoters that are likely relevant for that artist.

Important clarification:

```text
similar artists = internal evidence layer
recommended promoters = final user-facing result
```

We are not removing similar artist recommendations from the backend. Similar artists remain important, but for the MVP they are mainly used to discover and explain promoter recommendations.

## Main endpoint

```text
GET /api/recommendations/artists/{artist_id}/promoters?limit=10
```

This endpoint should eventually return:

- ranked promoter recommendations
- final score
- score breakdown
- human-readable reasons
- evidence paths
- graph nodes and links for explanation UI

## MVP signal families

The promoter ranking should combine four main signal families.

### 1. `semantic_bridge`

Graph path:

```text
Source Artist -> Similar Artist -> Event -> Promoter
```

Meaning:

We find artists that are semantically close to the source artist, then find promoters connected to those artists through events.

Signals may include:

- artist embedding similarity
- style overlap
- extracted tag overlap
- event connections of similar artists

Why it matters:

This is the strongest discovery signal for promoters who have not directly booked the source artist yet.

Example explanation:

```text
Booked 5 artists similar to the selected artist.
```

### 2. `direct_connection`

Graph path:

```text
Source Artist -> Event -> Promoter
```

Meaning:

The promoter is already directly connected to the source artist through an event where the source artist played.

Why it matters:

This is the strongest existing relationship signal. It proves the artist and promoter already have a real-world connection.

Example explanation:

```text
Already connected through 2 event(s).
```

Frontend status suggestion:

```text
already_connected
```

### 3. `warm_network`

Graph path:

```text
Source Artist -> Shared Event -> Co-played Artist -> Other Event -> Promoter
```

Meaning:

The promoter is connected through artists who have already played with the source artist.

Why it matters:

This captures warm scene-network opportunities. These promoters may be more reachable than purely cold semantic matches.

Example explanation:

```text
Connected through 2 artists who already played with the selected artist.
```

Frontend status suggestion:

```text
warm_contact
```

### 4. `event_similarity`

Graph path:

```text
Source Artist -> Source Artist Event -> Similar Promoter Event -> Promoter
```

Meaning:

Compare events where the source artist played with events organized by candidate promoters.

Why it matters:

A promoter can be relevant even if they did not book a directly similar artist, as long as they organize events with a similar scene context.

Potential event similarity inputs:

- event title
- event description
- lineup
- genres
- venue
- promoter/event neighborhood
- event embeddings

Example explanation:

```text
Organizes events similar to events the selected artist has played.
```

## Proposed MVP scoring

Target final scoring formula:

```text
final_score =
  0.30 * semanticBridgeScore
+ 0.25 * eventSimilarityScore
+ 0.20 * warmNetworkScore
+ 0.10 * directConnectionScore
+ 0.08 * activityScore
+ 0.07 * recencyScore
```

The exact weights can be tuned after manual review of real recommendations.

The response should expose the score breakdown instead of returning only a final score.

Example:

```json
{
  "score": 0.84,
  "scoreBreakdown": {
    "semanticBridge": 0.30,
    "eventSimilarity": 0.25,
    "warmNetwork": 0.20,
    "directConnection": 0.10,
    "activity": 0.08,
    "recency": 0.07
  }
}
```

## Graph-based explanation UI

The recommendation UI should be graph-based.

The selected artist is the central node.

Recommended promoters are target nodes.

The nodes between them are evidence nodes that explain why the promoter was recommended.

Important constraint:

```text
Do not show the full database graph for MVP.
Show a small local explanation graph around the selected artist and the selected/recommended promoter.
```

The graph should answer this question:

```text
Why this promoter?
```

### Node types

The graph can contain these node types:

- `source_artist`
- `similar_artist`
- `co_played_artist`
- `event`
- `promoter_event`
- `promoter`
- `venue`

The selected artist should be visually centered.

Recommended promoters should be visually emphasized as target nodes.

### Edge types

The graph can contain these edge types:

- `played_at`
- `similar_to`
- `co_played_with`
- `organized_by`
- `event_similarity`
- `held_at`

### Edge strength and line thickness

Edges should have different visual weights.

Line thickness represents relationship strength.

Suggested mapping:

```text
0.8 - 1.0 = thick line
0.5 - 0.8 = medium line
0.2 - 0.5 = thin line
0.0 - 0.2 = very thin / faded line
```

Suggested line styles:

```text
solid line   = real existing connection
dashed line  = semantic similarity
dotted line  = event similarity
```

Examples:

```text
Strong direct connection:
Source Artist -> Event -> Promoter
```

Use a thicker solid line.

```text
Warm indirect connection:
Source Artist -> Shared Event -> Co-played Artist -> Other Event -> Promoter
```

Use a medium solid line.

```text
Semantic connection:
Source Artist -> Similar Artist -> Event -> Promoter
```

Use a thinner dashed line for the similarity edge and solid lines for real event/promoter edges.

```text
Event similarity connection:
Source Artist -> Source Artist Event -> Similar Promoter Event -> Promoter
```

Use a dotted line for the event similarity edge.

## Target response shape

The backend response should move toward this shape:

```json
{
  "entityId": 123,
  "entityType": "artist",
  "recommendations": [
    {
      "id": 42,
      "type": "promoter",
      "name": "Promoter X",
      "score": 0.84,
      "status": "new_relevant",
      "scoreBreakdown": {
        "semanticBridge": 0.30,
        "eventSimilarity": 0.25,
        "warmNetwork": 0.20,
        "directConnection": 0.10,
        "activity": 0.08,
        "recency": 0.07
      },
      "reasons": [
        "Booked 5 artists similar to the selected artist",
        "Connected through 2 artists who already played with the selected artist",
        "Organizes events similar to events the selected artist has played"
      ],
      "matchedArtistCount": 5,
      "warmConnectionCount": 2,
      "directConnectionCount": 1,
      "eventCount": 8,
      "latestEventDate": "2026-05-12",
      "evidence": [
        {
          "type": "semantic_bridge",
          "path": "Source Artist -> Similar Artist -> Event -> Promoter"
        },
        {
          "type": "warm_network",
          "path": "Source Artist -> Shared Event -> Co-played Artist -> Other Event -> Promoter"
        },
        {
          "type": "event_similarity",
          "path": "Source Artist -> Source Artist Event -> Similar Promoter Event -> Promoter"
        }
      ]
    }
  ],
  "graph": {
    "nodes": [
      {
        "id": "artist-123",
        "type": "source_artist",
        "label": "Selected Artist"
      },
      {
        "id": "artist-456",
        "type": "similar_artist",
        "label": "Similar Artist"
      },
      {
        "id": "event-777",
        "type": "event",
        "label": "Event Name"
      },
      {
        "id": "promoter-42",
        "type": "promoter",
        "label": "Promoter X",
        "score": 0.84
      }
    ],
    "links": [
      {
        "source": "artist-123",
        "target": "artist-456",
        "relationship": "similar_to",
        "evidenceType": "semantic_bridge",
        "weight": 0.62,
        "style": "dashed"
      },
      {
        "source": "artist-456",
        "target": "event-777",
        "relationship": "played_at",
        "evidenceType": "semantic_bridge",
        "weight": 0.75,
        "style": "solid"
      },
      {
        "source": "event-777",
        "target": "promoter-42",
        "relationship": "organized_by",
        "evidenceType": "semantic_bridge",
        "weight": 0.75,
        "style": "solid"
      }
    ]
  }
}
```

## Frontend MVP flow

1. User selects or enters an artist.
2. Frontend requests promoter recommendations.
3. UI displays promoter recommendation cards.
4. User clicks a promoter card or `Why this promoter?`.
5. UI shows a small local explanation graph for that promoter.

Each promoter card should show:

- promoter name
- recommendation score
- status badge
- recommendation reasons
- score breakdown
- matched artists count
- warm/direct connection counts
- latest event date

Expandable section:

```text
Why this promoter?
```

This section can display:

- recommendation reasons
- evidence paths
- matched artists
- small graph explanation

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

For MVP, this endpoint is useful as a backend/internal layer. It is not the main user-facing product output.

### Promoter recommendations for an artist

```text
GET /api/recommendations/artists/{artist_id}/promoters
```

Returns promoters connected to the source artist through semantic, graph, and event evidence.

This is the main MVP endpoint.

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

Planned MVP feedback behavior:

- `hidden` removes the promoter from future results for the same source artist
- `negative` applies a score penalty
- `positive` adds a small boost or marks the recommendation as useful

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

## What is not finished yet

The real product recommendation engine is still planned.

Missing or incomplete MVP parts:

- direct connection signal
- warm network signal
- event similarity signal
- unified evidence path model
- graph edge weights / styles in backend response
- feedback-aware reranking
- frontend recommendation page
- frontend explanation graph
- API docs for frontend/external consumers

Post-MVP parts:

- user-based preference model
- user onboarding / taste profile
- venue recommendations
- event recommendations as a first-class public endpoint
- full multi-direction graph recommender
- advanced reachability scoring
- score calibration dashboard

## Suggested next implementation order

### Step 1: inspect and stabilize current promoter recommendation flow

- keep current endpoint path unchanged
- document current SQL paths
- verify current tests
- add tests where missing

### Step 2: expose explicit signal fields

- `semanticBridgeScore`
- `directConnectionScore`
- `warmNetworkScore`
- `eventSimilarityScore`
- `activityScore`
- `recencyScore`
- `scoreBreakdown`

Use `0.0` placeholders for signals that are not implemented yet.

### Step 3: implement `direct_connection`

- source artist -> event -> promoter
- add count, score, reason, and evidence path
- add tests

### Step 4: implement `warm_network`

- source artist -> shared event -> co-played artist -> other event -> promoter
- add count, score, reason, and evidence path
- add tests

### Step 5: implement unified evidence model

- explicit evidence array
- evidence types
- graph nodes
- graph links
- edge weights
- edge styles

### Step 6: implement `event_similarity`

- compare source artist events with candidate promoter events
- use existing event embeddings when available
- do not generate embeddings inside API requests
- add fallback when embeddings are missing
- add tests

### Step 7: update final scoring formula

- apply MVP weights
- keep final score in range `0..1`
- preserve backward-compatible fields where possible
- add ranking tests

### Step 8: make feedback affect ranking

- hidden removes promoter
- negative applies penalty
- positive adds boost/mark
- add tests

### Step 9: frontend MVP

- promoter cards
- `Why this promoter?` section
- local explanation graph
- edge weight visualization

## Current limitation

At the moment, the project has strong backend ingredients but does not yet have a finished recommendation product.

The current branch should be described as:

```text
artist-to-promoter recommendation foundation
```

not as:

```text
complete production recommendation engine
```
