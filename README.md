# Berlin Scene Graph

Berlin Scene Graph is a music-scene graph project for exploring relationships between artists, events, promoters, venues, genres, and recommendation signals.

This branch, `codex/recommendation-engine`, focuses on building the data and backend foundation for semantic similarity, artist tag extraction, embeddings, recommendation scoring, and explainable recommendation outputs.

## Current status

The project is not yet a complete end-user recommendation product. The current branch contains a working backend-oriented foundation for the future recommendation engine.

Implemented in this branch:

- FastAPI backend
- PostgreSQL database
- Prisma schema and migrations
- Docker Compose local stack
- Nginx reverse proxy for local access
- RA event import pipeline improvements
- normalized lineup and biography text backfills
- artist biography tag extraction
- OpenAI / Azure OpenAI integration for extraction and embeddings
- entity embeddings for artists and events
- semantic artist similarity
- artist-to-artist recommendations
- artist-to-promoter recommendations
- recommendation feedback storage
- graph response structure for recommendation evidence
- backend tests for extraction, embeddings, text profiles, scoring, and graph API behavior

Still planned:

- full user-facing recommendation engine
- user-based recommendation personalization
- venue recommendations
- event recommendations as a first-class public endpoint
- stronger path explanations
- reachability scoring
- frontend recommendation pages
- frontend explanation panel
- public API authentication and rate limits
- production-ready security hardening

## Tech stack

Current backend stack:

- Python
- FastAPI
- PostgreSQL
- Prisma schema / migrations
- psycopg
- OpenAI Python SDK
- httpx
- pytest

Current local infrastructure:

- Docker Compose
- PostgreSQL 16 Alpine
- Nginx
- backend container
- frontend container
- Prisma tools container

Frontend stack is expected to be React / TypeScript / Vite, but this branch is mainly focused on backend recommendation-engine work.

## Repository structure

```text
backend/
  app/
    main.py                     FastAPI app and API endpoints
    embeddings.py               Embedding generation and similarity ranking
    artist_tag_extraction.py    LLM-based artist biography tag extraction
    recommendation_scoring.py   Scoring helpers for semantic + graph ranking
    style_tags.py               Style tag extraction and overlap scoring
    text_profiles.py            Normalized text profiles for artists/events
  prisma/
    schema.prisma               Database schema
    migrations/                 Database migrations
  scripts/
    import_events.py            Event import pipeline
    backfill_normalized_texts.py Text normalization backfills
    extract_artist_tags.py      Artist tag extraction script
    generate_embeddings.py      Embedding generation script
  tests/                        Backend tests

docs/
  task-tree.html                Planning artifact / interactive roadmap

documentation/
  scene_graph_full_development_plan.md  Original full roadmap

docker-compose.yml
Makefile
.env.example
```

## Local setup

Create a local environment file:

```bash
make env
```

Edit `.env` and set at least database values. For OpenAI or Azure-powered extraction and embeddings, also configure the relevant API variables.

Start the stack:

```bash
make upd
```

Run migrations:

```bash
make prisma-migrate
```

Import events:

```bash
make import-events
```

Run text normalization backfills:

```bash
make backfill-normalized-texts
make backfill-lineup-residual
make backfill-artist-biographies
```

Extract artist tags:

```bash
make extract-artist-tags
```

Generate embeddings:

```bash
make generate-embeddings
```

Check health:

```bash
make health
```

The local Nginx entrypoint is expected to be available at:

```text
http://localhost:8080
```

## Environment variables

See `.env.example` for the complete list.

Important variables:

```env
DATABASE_URL=postgresql://scenegraph:change-me@db:5432/scenegraph

EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=

EXTRACTION_PROVIDER=openai
OPENAI_EXTRACTION_MODEL=gpt-4.1-mini
EXTRACTION_API=

AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_CHAT_API_VERSION=2025-01-01-preview
AZURE_OPENAI_RESPONSES_URL=
AZURE_OPENAI_RESPONSES_MODEL=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
AZURE_OPENAI_EXTRACTION_DEPLOYMENT=
```

For local development, do not commit `.env` or API keys.

## API overview

Current important endpoints include:

```text
GET  /health
GET  /api
GET  /api/venues
GET  /api/graph
GET  /api/semantic/artists/{artist_id}
GET  /api/artists/{artist_id}/tags
GET  /api/recommendations/artists/{artist_id}
GET  /api/recommendations/artists/{artist_id}/promoters
POST /api/recommendation-feedback
GET  /api/recommendation-feedback
```

More detailed API documentation should live in `docs/api.md`.

## Recommendation engine status

The current branch implements the foundation of the recommendation engine, not the final product version.

Current recommendation logic combines:

- embeddings
- normalized artist/event text profiles
- extracted artist tags
- style overlap
- graph overlap signals
- promoter/event evidence
- feedback storage

Planned next work:

- explicit user profile and user preference model
- reachability score
- venue recommendations
- event recommendations
- stronger path explanations
- recommendation cards in the frontend
- explanation UI for why a recommendation was produced

See `docs/recommendation-engine.md` for details.

## Documentation status

The older documents in `documentation/` and `docs/task-tree.html` are planning artifacts. They are useful for understanding the original roadmap, but they are not fully aligned with the current implementation.

The current source of truth should be:

- `README.md`
- `docs/api.md`
- `docs/recommendation-engine.md`
- `.env.example`
- `backend/prisma/schema.prisma`
- `backend/app/main.py`

## Development notes

The project currently mixes direct SQL via `psycopg` with a Prisma schema/migration workflow. This is acceptable for the current backend prototype, but should be documented clearly before evaluation or production hardening.

The recommendation-engine branch should be treated as an active feature branch, not as final stable product documentation.