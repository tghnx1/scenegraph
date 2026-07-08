---
name: scenegraph
description: Project-specific guidance for working in the scenegraph repository. Use when touching backend API, PostgreSQL/Prisma, recommendation jobs, ingestion pipeline, graph UI, auth/admin, or import validation.
---

# Scenegraph

## What this repo is
`scenegraph` is a backend-heavy web app for Berlin music-scene data. It ingests artists, events, promoters, venues, genres, and source payloads into PostgreSQL, extracts tags and embeddings, and serves explainable promoter recommendations through FastAPI and a React frontend.

The "graph" here is the data graph for recommendations and navigation across artists, events, promoters, and venues. It is not a rendering-engine scene graph.

## Read first
When starting work, inspect these files first:

- `README.md`
- `AGENTS.md`
- `backend/app/main.py`
- `backend/app/routers/index.py`
- `backend/app/routers/search.py`
- `backend/app/routers/graph.py`
- `backend/app/routers/recommendations.py`
- `backend/app/routers/session.py`
- `backend/app/admin/users.py`
- `backend/app/recommendations/engine.py`
- `backend/app/recommendations/scoring.py`
- `backend/app/recommendations/services.py`
- `backend/app/recommendations/jobs.py`
- `backend/app/recommendations/worker.py`
- `backend/app/text_profiles.py`
- `backend/app/style_tags.py`
- `backend/app/artist_tag_extraction.py`
- `backend/app/event_tag_extraction.py`
- `backend/app/import_run_logger.py`
- `backend/app/schema_preflight.py`
- `backend/prisma/schema.prisma`
- `parsers/run_ra_pipeline.py`
- `backend/scripts/full_pipeline.py`
- `frontend/src/pages/GraphPage.tsx`
- `frontend/src/pages/ProfilePage.tsx`
- `frontend/src/pages/AgencyPage.tsx`
- `frontend/src/pages/components/GraphPanel.tsx`
- `frontend/src/pages/components/RecommendationPanel.tsx`
- `frontend/src/pages/components/SearchInputField.tsx`

## Core architecture
- Python + FastAPI powers the backend.
- PostgreSQL stores source entities, graph edges, tags, embeddings, jobs, and feedback.
- Prisma defines the database schema and migrations.
- Parsers and scripts own ingestion and enrichment.
- React + TypeScript implements the UI.
- Recommendation jobs are durable and worker-driven.

## Key rules for edits
- Preserve explainability fields and scoring breakdowns when changing recommendation logic.
- Do not mutate graph state or node shape casually; prefer the existing router/service/helpers layer and the frontend store/actions that already own those transitions.
- Keep ingestion slices, tag extraction, embeddings, and validation aligned; if you change one stage, check downstream stages and tests.
- Prefer minimal local changes over cross-cutting refactors.
- If a change affects the public API contract, update both backend types and frontend consumers together.

## Validation expectations
- Backend tests run inside the backend container: `docker compose exec backend pytest -q`
- Frontend validation uses: `cd frontend && npm run build`
- Local development stack starts with `make upd`
- End-to-end ingestion uses `make full-pipeline`
- If biography scraping is needed, set `FULL_PIPELINE_SKIP_BIO=no`

## OpenCode model note
- When launching OpenCode, set `OPENCODE_MODEL=azure/gpt-5.2` or your Azure OpenAI deployment name if it differs.

## Safety
- Never create commits or push without explicit user instruction.
- Do not upgrade foundational dependencies, Prisma schema, or deployment-facing configuration without asking first.
- If a change touches auth, admin flows, or recommendation jobs, verify the full request/response path before claiming completion.
