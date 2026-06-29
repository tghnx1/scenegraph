_This project has been created as part of the 42 curriculum by mkokorev, hsetyamu, tsilva, and apaz-mar._

# Scenegraph

## Description

This is an experimental, exploratory project to map relationships between artists, events, promoters, venues, and genres, in Berlin's electronic music scene. These relationships are then used to produce explainable recommendations that are useful for electronic music artists to find prospective promoters.

Music-scene data is spread across event listings, lineups, biographies, venues, and promoter histories. The Scenegraph project brings those sources into a normalized relational model so the project can answer questions such as:
- Which artists are semantically or stylistically related?
- Which promoters are relevant to an artist?
- Which events share artists, promoters, venues, genres, or extracted tags?
- What evidence contributed to a recommendation?

The key features of the project:
1. Visualization of the events-artists-promoters-venues
2. Recommendation
3. Different roles for regitered users
4. Live dashboard updates

## Instructions

Requirements:

- Docker with Docker Compose v2
- GNU Make
- Optional provider API keys for embedding and extraction workflows

Create a local environment file:

```bash
make env
```

Build and start the local stack:

```bash
make upd-build
```

This applies Prisma migrations and starts PostgreSQL, the FastAPI backend, frontend, and NGINX gateway.

Useful commands:

```bash
make list
make logs
make prisma-migrate
make down
```

Entry point:
- Gateway: `https://localhost:8443`
- Health check: `https://localhost:8443/health`

## Team members and roles

### Maksim Kokorev (mkokorev): PO
Designs the grand scheme of the project and aim, decides necessary features and priorities, checks pull requests and validates features implementation.

### Howard Setyamukti (hsetyamu): PM
Organize and plan meetings, document meeting in notes, kanban board maintenance/updates, establish communication channel.

### Tarcisio Silva (tsilva): Tech Lead
Decides which technology stack to use, maintain code usability & quality.

### Aaron Paz Martinez (apaz-mar): Developer
Implement and design vital features for the app and testing other features.

## Project management approach

For the most part, the project members consolidate at least once every week on an agreed time. This usually occurs on Thurdays. This opportunity is used to:
1. announce progress results of the previous week
2. declare hindrances
3. discussions
4. target to achieve for the following week

Communication, beside direct physical conversation, is also done by group communication in a Slack group.

Tasks were divided by agreement during meeting and were tracked by a kanban board in Jira.
Meeting notes are also written and published in the Jira board along with other useful documents for the team to serve as reference.

## Technologies used

### Frontend
React, Vite, and TypeScript are used because they make it easier to build a fast, maintainable UI with a modern developer experience and strong type safety.

### Backend and data
Python and FastAPI provide a simple, productive API layer. PostgreSQL stores the core data reliably, pgvector supports similarity search, psycopg connects the app to the database efficiently, Prisma migrations keep schema changes organized, and pytest keeps the backend behavior testable.

### Deployment infrastructure
Docker and Docker Compose make local development and deployment consistent, while NGINX acts as the gateway in front of the app.

### Enrichment providers: 
OpenAI is used for embeddings and Azure OpenAI for extraction because they provide the language-model features needed for semantic enrichment, and environment variables keep those providers configurable.

## Database schema
-- See Database_Schema.md --

## List of features
The following are main features included in the project.

### apaz-mar
Authentication & Authorization
- Implemented user registration and login.
- Implemented JWT-based authentication and role-based authorization (artist, agent, admin).
- Implemented password hashing (bcrypt), input validation, and authentication activity logging.

User Administration
- Implemented user approval, rejection, activation/deactivation, and role management.
- Implemented bootstrap administrator creation and protection (bootstrap admin, last active admin, self-deactivation safeguards).
- Implemented automatic logout of deactivated users on their next protected request.

Artist Claim Management
- Implemented artist profile claim workflow (submission, approval/rejection, assignment).
- Added protections against duplicate, conflicting, and simultaneous pending claims.

Public API
- Implemented Public API authentication using API keys.
- Added rate limiting and pagination support (limit / offset) for public endpoints.

### tsilva
Database Design & Setup
- Designed and implemented the full PostgreSQL schema using Prisma, covering all core entities, junction tables, enrichment and ML tables, and pipeline audit tables.

REST API
- Implemented all public-facing endpoints: search (cross-entity full-text with trigram indexes), artist, venue, event, promoter, genres, and ego graph
- Applied performance-first query design throughout: CTEs, aggregations, window functions, and separate queries to avoid JOIN row multiplication
- Designed the ego graph endpoint supporting four entity types with configurable depth and relationship labeling

Admin Dashboard — Metrics & Composition
- Built the `/api/admin/metrics` endpoint producing all dashboard health metrics from a single SQL query using CTEs, correlated subqueries, and percentile calculations
- Built the `/api/admin/composition` endpoint for entity distribution charts, using a single filtered CTE to avoid redundant table scans
- Defined status rules (good / warning / critical) based on missing-data rates across the dataset

Real-Time WebSocket Architecture
- Designed and implemented the WebSocket endpoint (`/api/admin/dashboard`) for live dashboard updates
- Implemented three concurrent `asyncio` tasks: `notify_task` (PostgreSQL `LISTEN/NOTIFY`), `keepalive_task` (30s ping), and `ws_receive_task` (disconnect detection), coordinated via a shared `stop_event`
- Implemented 500ms debounce to batch rapid bulk-import notifications into single flush messages
- Implemented JWT authentication enforced before the WebSocket handshake is accepted, with close codes `1008` and `1011`
- Created the PostgreSQL trigger function `scenegraph_notify_dashboard_refresh` attached to all tracked tables, firing once per statement to minimize notification volume
- Designed the `areas` field in the WebSocket message contract as a forward-compatibility hook for future partial frontend refreshes

### hsetyamu
Implemented frontend features include:
- Graph visualization of nodes and links data of different entities from the backend
- Interactive visualization: supports panning and zooming in the graph canvas
- Interactive visualization: implementation of a force directed graph
- Filter functionality (implemented both to filter the data send to the frontend and filtering of the display itself)
- Additional panel to diplay entity details
- Search functionality with filter (based on entity) and pagination
- Role-based workspaces for artists, agents, and admins
- Admin dashboard with live updates, metrics, user management, exports to different file formats
- Biography editing for users that has claimed an artist's profile
- Basic informational pages
- Theme switching
- Modular components for reusability in different workspaces

### mkokorev
Recommendation Engine / AI Module
- Built the promoter recommendation system with explainable scoring and debug output.
- Added asynchronous recommendation jobs and worker processing.
- Implemented role/ownership checks so artists can only access their own recommendations, while agents/admins can access any artist.
- Cleaned and migrated recommendation tuning/configuration, including legacy alias removal and config-backed weights.

Custom Major Module — Graph / Evidence Explorer
- Built the interactive graph (backend side) and evidence-exploration module.

Custom Minor Module — Automated Ingestion Pipeline
- Built the automated pipeline for scraping, normalization, tag extraction, embeddings, validation, and DB updates.
- Added automatic refresh behavior when artist biographies change.
- Kept the pipeline runnable through the project’s Docker/Make workflow.

Auth / Permissions / UX
- Implemented manual connection permissions. (only artists can change them)

Docs / Cleanup
- Wrote and reorganized project documentation for the recommendation engine, jobs, graph module, and ingestion pipeline.
- Removed legacy endpoints, dead code, and old dev-only plumbing.

## Chosen modules
-- see Checklist.md --

## Resources
- https://fastapi.tiangolo.com/
- https://react.dev/learn
- https://www.postgresql.org/docs/
- https://www.prisma.io/docs
- https://www.typescriptlang.org/docs/handbook/intro.html
- https://www.python.org/doc/
- https://vite.dev/guide/
- https://docs.docker.com/manuals/
- https://nginx.org/en/docs/

### AI Usage declaration
Apart from the AI agent involved in the algorithm for the recommendation pipeline, AI was used extensively throughout the project for implementation drafts, debugging, documentation, refactoring, and repetitive tasks.
The project direction, validation, integration, and final review were handled by the team.