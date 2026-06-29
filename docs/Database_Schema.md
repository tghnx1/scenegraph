# Database Schema README

This project uses Prisma with PostgreSQL to model the core event, artist, recommendation, and import workflow data.

The canonical schema lives in `backend/prisma/schema.prisma`, and migrations are stored under `backend/prisma/migrations/`.

## Overview

The database is organized around a music/event discovery domain with these main concerns:

- Core catalog entities: artists, events, venues, genres, and promoters
- Relationship data: which artists appear at which events and which promoters are linked to events
- Enrichment and tagging: extracted tags, tag extraction runs, embeddings, and normalized text profiles
- Recommendation and user workflows: feedback, jobs, and user accounts
- Import pipeline tracking: run metadata and per-stage execution history

## Core Models

### Artists and events

- `Artist`
  - Represents an artist imported from the source system.
  - Stores identifiers, names, biography, normalized biography, and related enrichment data.
  - Links to event participation, extracted tags, and recommendation jobs.

- `Event`
  - Represents an event or gig.
  - Stores title, description, lineup text, timestamps, venue linkage, and metadata such as age restrictions and ticketing information.
  - Links to artists, genres, promoters, tags, and payload snapshots.

- `Venue`
  - Represents a venue tied to one or more events.
  - Includes address, coordinates, and geographic metadata.

- `Genre`
  - Represents a genre used by events.

- `Promoter`
  - Represents an event promoter and can be associated with multiple events.

### Junction and relationship tables

- `EventArtist`
  - Many-to-many relationship between events and artists.

- `EventGenre`
  - Many-to-many relationship between events and genres.

- `EventPromoter`
  - Many-to-many relationship between events and promoters.

- `ArtistManualConnection`
  - Manual artist-to-artist relationship data used for curated or admin-defined connections.

### Enrichment and embeddings

- `ArtistExtractedTag` and `EventExtractedTag`
  - Store extracted tags for artists and events.
  - Include tag type, tag value, confidence, extractor, and evidence.

- `ArtistTagExtractionRun` and `EventTagExtractionRun`
  - Track each extraction run for auditing and repeatability.

- `EntityEmbedding`
  - Stores embedding vectors for entities with metadata such as model, dimensions, text hash, and text profile.
  - Uses PostgreSQL vector support for similarity workflows.

### Recommendation and user data

- `User`
  - Stores authenticated users and their roles/status.

- `RecommendationJob`
  - Tracks asynchronous recommendation work for a given user and artist.

- `RecommendationFeedback`
  - Stores user feedback about recommendations for explainability and tuning.

### Import pipeline tracking

- `ImportRun`
  - Tracks a full import run, including status, date range, counts, and metadata.

- `ImportRunStage`
  - Tracks each stage of an import run, including duration, status, metadata, and errors.

## Relationship Notes

The most important relationships are:

- One `Event` may have many `EventArtist` entries and therefore many artists.
- One `Artist` may appear in many events.
- One `Event` may reference one `Venue` and many `Genre`, `Promoter`, and tag records.
- `Artist` and `Event` records can accumulate enrichment data over time without replacing the original source entity.
- Recommendation and import tables are designed to be auditable and resumable.

## Important Database Characteristics

- The schema uses PostgreSQL-specific features such as `Timestamptz` and `Unsupported("vector")` for embeddings.
- Most tables use `BigInt` primary keys with Prisma-generated auto-incrementing IDs.
- Many tables include indexes for common access patterns such as event lookups, user-based queries, and tag retrieval.
- Cascading deletes are used where related enrichment data should disappear with the parent record.

## How the Schema Fits the Application

This database supports the project’s main workflows:

1. Importing raw event and artist data from external sources.
2. Normalizing and enriching that data with tags and embeddings.
3. Building graph-like or recommendation-oriented relationships between entities.
4. Tracking import progress and recommendation jobs for debugging and auditing.

## Updating the Schema

When changing the database structure:

1. Edit `backend/prisma/schema.prisma`.
2. Create or update a Prisma migration.
3. Apply migrations with the project’s standard workflow.

Typical commands used by this repository include:

```bash
make env
make prisma-migrate
```

If the stack is running locally, you can also use the project’s Docker-based workflow described in the repository root instructions.

## Practical Guidance

- Keep schema changes small and explicit.
- Preserve explainability-related fields when changing recommendation or enrichment logic.
- Add indexes when new query patterns become common.
- Avoid removing fields that are still used by import or recommendation pipelines without a migration plan.
