# AGENTS.md

High-signal context for OpenCode agents working in this repo. If it’s not here, assume defaults.

## What this repo is
- Prototype backend-heavy web app: FastAPI + PostgreSQL (pgvector) + Docker Compose.
- Core value is data import, enrichment, graph logic, and explainable recommendations.
- Frontend exists, but backend and data workflows are the source of truth.

## Current submission goal
- The active goal is to ship `ft_transcendence` with a defensible module set, not to build unrelated product features.
- Treat the current checklist as a living evaluation aid: add notes in separate columns or new rows, but do not overwrite existing verdicts or historical context.
- The selected custom major module is the graph + explainable recommendation path system.
- The selected custom minor module is the automated scraping / normalization / tag extraction / validation / database update pipeline.
- First inspect the working branches `codex/data_import`, `feature/endpoints`, and `feature/frontend` before making new assumptions.
- Preserve explainability, admin tooling, and import workflows; these are part of the submission story.

## Real entrypoints
- Local gateway: `http://localhost:8080`
- FastAPI app runs behind NGINX via Docker Compose.
- OpenAPI UI: `http://localhost:8080/docs`
- Health check: `GET /health`

## How to run (don’t guess)
- Create env file: `make env` (do not hand-write `.env`)
- Start everything: `make upd`
  - This also applies Prisma migrations automatically.
- Stop stack: `make down`

## Database & migrations
- PostgreSQL is expected to run via Docker Compose by default.
- Schema and migrations live in `backend/prisma/`.
- Manual migration command when needed: `make prisma-migrate`.
- Backend code assumes `DATABASE_URL` is set (usually points at the Docker DB).

## Tests (important quirks)
- Tests must be run **inside** the backend container:
  - `docker compose exec backend pytest -q`
- Focused test runs:
  - `docker compose exec backend pytest tests/test_graph_api.py -q`
  - `docker compose exec backend pytest tests/test_recommendation_scoring.py -q`
- Many tests do NOT require external providers; some enrichment tests do.

## Data workflows (order matters)
- Prefer `make full-pipeline` for the end-to-end ingestion flow.
- It runs the full import pipeline in Docker, using the `backend/scripts/full_pipeline.py` coordinator from the `codex/data_import` work.
- The coordinator scrapes and parses events and artists, optionally launches local Chromium for biography scraping, deduplicates against the database, imports the resulting JSON, backfills normalized texts, extracts tags, generates embeddings, and validates the import.
- Control its behavior with `FULL_PIPELINE_*` variables such as date range, artifact directory, skip flags, and optional validation artist id.
- Use the individual stage commands only when you are debugging a specific step or intentionally isolating a failure.

## External providers
- Embeddings and extraction may call OpenAI / Azure OpenAI.
- Controlled entirely via env vars (`EMBEDDING_PROVIDER`, `EXTRACTION_PROVIDER`).
- Code is written to degrade gracefully when providers are unset, but some commands will fail.

## Architecture boundaries
- `backend/app/`: FastAPI app, routers, recommendation logic.
- `backend/scripts/`: one-off and batch workflows (imports, enrichment).
- `parsers/`: raw data ingestion and normalization (not API-facing).
- `frontend/`: React/Vite client; not all backend features are exposed.

## Trust hierarchy
- Docker Compose, Makefile, and code override docs if they conflict.
- Older files under `documentation/` may be stale planning artifacts.

## Known non-goals / placeholders
- Authentication exists and uses JWT + bcrypt + account approval + role checks, but it is still development-grade.
- Browser sessions store tokens in `localStorage`, and the auth flow is not production-hardened or server-side revocable.
- Public API access exists through a static `X-API-Key`, but rate limiting is process-local/in-memory and the deployment is not hardened.
- Do not assume prod-readiness semantics, distributed abuse protection, revocation guarantees, or hardened deployment behavior.

## When modifying code
- Prefer minimal, local changes; avoid refactors that span backend + scripts unless necessary.
- Recommendation logic is evidence-based; preserve explainability fields when changing scoring.
- Tests are valued; update or add pytest coverage for behavior changes.
- Keep recommendation scoring defaults in code/config rather than growing `.env` with more tuning knobs unless an override is truly needed.
- For Transcendence work, prefer changes that strengthen module coverage, evaluation evidence, and README-proof over cosmetic cleanup.

## Review gate for cleanup work
- Before leaving endpoint cleanup, test cleanup, docs cleanup, or starting weight cleanup, invoke `@review-gate`.
- Treat `@review-gate` as read-only: it reviews diffs and verification output, but does not edit code.
- Do not continue to the next cleanup phase until `@review-gate` explicitly says `Endpoint cleanup approved.`
- If the gate rejects a phase, fix only the reported blockers, rerun the required verification, and invoke `@review-gate` again.
- For recommendation cleanup, the product path is promoter recommendations only; deleted legacy endpoint tests/docs do not count as real usage.
- For endpoint cleanup, prefer `/endpoint-cleanup-loop`; for direct review, use `/review-endpoint-cleanup` so `@review-gate` receives the current diff, compile output, and endpoint search results.
