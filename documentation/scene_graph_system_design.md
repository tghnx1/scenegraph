# Berlin Nightlife Scene Graph — System Design & Implementation Plan

> Internal navigation:
- [Overview](#overview)
- [Architecture](#architecture)
- [Data Ingestion (Events-first)](#data-ingestion-events-first)
- [Graph Model](#graph-model)
- [Enrichment Layer (Style & Context)](#enrichment-layer-style--context)
- [Relevance, Centrality & Popularity](#relevance-centrality--popularity)
- [Event Similarity & Clustering](#event-similarity--clustering)
- [Offline Pipeline](#offline-pipeline)
- [Runtime Mapping](#runtime-mapping)
- [Scoring & Recommendation Logic](#scoring--recommendation-logic)
- [Outputs](#outputs)
- [MVP Scope](#mvp-scope)
- [Future Extensions](#future-extensions)
- [Visualization](#visualization)
- [Appendix: Pseudo-Schema](#appendix-pseudo-schema)

---

## Overview
We build a **scene graph of Berlin nightlife** based on event data and use it to recommend **realistic opportunities** (promoters, venues, events, and artists) for emerging DJs.

**Core principle:** not “what is popular”, but **what is both relevant and reachable** for the user.

---

## Architecture
Four layers:

1. **Ingestion** — collect events (RA Guide-like sources)
2. **Graph** — nodes & relations (Artist, Event, Promoter, Venue)
3. **Enrichment** — style tags, activity, popularity
4. **Runtime** — user mapping + ranking (proximity, strength, reachability)

---

## Data Ingestion (Events-first)
Start from events, not artists.

Each event yields:
- lineup (artists)
- promoter
- venue
- date
- description
- interested/attending (if available)

**Derive entities from events:**
- Artist
- Promoter
- Venue

This ensures **contextual, scene-relevant data**.

---

## Graph Model

### Entities
- **Artist**
- **Event**
- **Promoter**
- **Venue**

### Relations
- `Artist → played_at → Event`
- `Promoter → organizes → Event`
- `Event → takes_place_at → Venue`

> Lineups are represented as multiple `Artist → Event` edges.

---

## Enrichment Layer (Style & Context)

### Style extraction
Sources:
- event descriptions
- artist bios
- promoter/venue descriptions
- graph neighborhood (co-occurrence)

Output:
- `style_tags: string[]`

Examples:
- dark disco, EBM, indie dance, electro, industrial, post-punk, synth-driven

**Approach (MVP):**
- keyword extraction + normalization
- optional LLM normalization later

---

## Relevance, Centrality & Popularity

### Popularity / visibility
- Artist: RA followers, events_count
- Event: interested_count
- Promoter: RA followers, hosted_events_count
- Venue: RA followers, hosted_events_count

### Scene centrality (MVP approximations)
- degree (number of connections)
- unique neighbors (artists/promoters/venues)

---

## Event Similarity & Clustering

### Event similarity (compute first)
Two events are similar if:
- same promoter (+)
- same venue (+)
- overlapping lineup (+)
- similar style tags (+)

### Clustering (optional, later)
- build event-to-event similarity graph
- run community detection (e.g., Louvain/Leiden)

---

## Offline Pipeline

1. **Collect events (Berlin)**
2. **Parse events**
3. **Upsert entities**
4. **Build edges**
5. **Extract style tags**
6. **Precompute metrics**
   - activity counts
   - simple centrality
   - event similarity

---

## Runtime Mapping

User inputs:
- RA profile / name
- known events (history)
- reference artists (optional)

Mapping:
- attach user to nodes (events/artists)
- derive initial style & neighborhood

---

## Scoring & Recommendation Logic

### Core components
- **Graph proximity** — path length & connectivity
- **Connection strength** — repeated & strong relations
- **Style similarity** — overlap of style tags
- **Entity relevance** — popularity/activity
- **Reachability** — user-specific accessibility

### Example scoring (high-level)
```
score = 
  w1 * proximity
+ w2 * strength
+ w3 * style_similarity
+ w4 * relevance
+ w5 * reachability
```

### Signals

**Proximity**
- fewer hops = better

**Strength**
- repeated co-lineups
- recurring promoters/venues

**Style**
- tag overlap

**Relevance**
- followers, activity

**Reachability**
- level gap penalty
- 1–2 hop preference

---

## Outputs

- **Recommended promoters**
- **Recommended venues**
- **Closest artists**
- **Reachable events/opportunities**

Each item includes **explanations**:
- path
- style match
- strength
- distance

---

## MVP Scope

### Included
- Berlin events dataset
- Graph (Artist/Event/Promoter/Venue)
- Style extraction (lightweight)
- Basic metrics (activity, followers)
- Runtime recommendations

### Excluded
- labels/releases
- radio/podcasts
- social scraping at scale
- heavy ML/embeddings

---

## Future Extensions
- labels & releases
- radio/mix series
- richer embeddings
- full clustering
- LLM explanations

---

## Visualization

### Graph view
- Nodes: Artist (blue), Event (yellow), Promoter (purple), Venue (green)
- Node size: relevance
- Edge width: strength

### Dashboard
- Top Promoters / Venues / Artists / Events
- Scores + explanations

### Path explorer
- show “why” (user → artist → event → promoter)

Libraries:
- react-force-graph
- Cytoscape.js
- vis-network

---

## Appendix: Pseudo-Schema

### Tables / Nodes

**Artist**
- id, name, ra_url, ra_followers
- bio_text, style_tags
- activity_count, first_seen_at, last_seen_at

**Event**
- id, title, date, ra_url
- description_text, interested_count
- style_tags, promoter_id, venue_id

**Promoter**
- id, name, ra_url, ra_followers
- description_text, style_tags
- hosted_events_count

**Venue**
- id, name, ra_url, ra_followers
- description_text, style_tags
- hosted_events_count

### Edges
- Artist → Event (played_at)
- Promoter → Event (organizes)
- Event → Venue (takes_place_at)
