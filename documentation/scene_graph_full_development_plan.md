# Berlin Scene Graph — Full Development Plan

## Goal
Ship a **fully runnable 42 Transcendence project** that:
1. satisfies the mandatory requirements first,
2. then reaches a **safe 16-point module target**,
3. then delivers the core scene graph recommendation value.

The order matters:
- **mandatory infrastructure first**
- **module-safe features second**
- **core product polish third**

---

## Final Validated Module Target (16 pts)

### Major modules
1. Web — Frontend + backend frameworks (**2**)
2. Web — Real-time features (**2**)
3. Web — User interaction (**2**)
4. Web — Public API (**2**)
5. Data & Analytics — Advanced analytics dashboard (**2**)
6. Modules of choice — Scene graph recommendation & explanation engine (**2**)

### Minor modules
7. Web — ORM (**1**)
8. Web — Advanced search (**1**)
9. Accessibility — Additional browser support (**1**)
10. Data & Analytics — Data export/import (**1**)

**Total = 16**

---

## Phase 0 — Freeze the Scope
Before coding, agree on:
- project name
- exact module list
- exact tech stack
- team roles
- branch strategy
- what is explicitly out of scope

### Deliverables
- scope lock page
- team role assignment
- GitHub repo
- Notion workspace
- issue board

---

## Phase 1 — Mandatory Skeleton First
This phase is not exciting, but it protects the project.

### 1.1 Repository and project layout
Create:
- `frontend/`
- `backend/`
- `nginx/`
- `docs/`
- `docker-compose.yml`
- root `README.md`
- `.env.example`

### 1.2 Frontend setup
Stack:
- React
- TypeScript
- Vite
- Tailwind

Initial pages:
- Landing
- Login
- Signup
- Dashboard placeholder
- Privacy Policy
- Terms of Service

### 1.3 Backend setup
Stack:
- Node.js
- Express
- TypeScript

Initial structure:
- routes
- controllers
- services
- middleware
- validators
- websocket setup placeholder

### 1.4 Database setup
Stack:
- PostgreSQL
- Prisma

Initial schema:
- User
- Session or token support
- Artist
- Event
- Promoter
- Venue

### 1.5 Docker setup
Containers:
- frontend
- backend
- db
- nginx

Goal:
```bash
docker compose up --build
```
must start the whole app.

### 1.6 Auth
Mandatory baseline:
- signup
- login
- password hashing
- protected routes
- logout

### 1.7 Validation
Must exist on both sides:
- frontend form validation
- backend request validation

### 1.8 HTTPS path
Use Nginx reverse proxy and local HTTPS strategy.

### 1.9 Multi-user baseline
Support:
- multiple accounts
- simultaneous sessions
- safe writes

### 1.10 README skeleton
Add:
- description
- instructions
- team roles
- tech stack
- module plan
- database schema placeholder

### Exit criteria for Phase 1
- app runs in Docker
- user can sign up / log in
- db connected
- privacy / terms pages exist
- no obvious console errors
- basic responsive shell works

---

## Phase 2 — Safe Point Modules Before Core Complexity
Now implement features that clearly map to points.

### 2.1 ORM (Minor, 1)
- Prisma schema
- migrations
- typed queries

### 2.2 Frameworks (Major, 2)
Already satisfied by:
- React
- Express

Just make sure both are fully used.

### 2.3 User interaction (Major, 2)
Implement the exact required minimum:
- profile page
- friends system
- basic chat

#### Profile
- view user info
- edit basic info
- scene interests / short bio

#### Friends
- send friend request
- accept / remove
- friends list

#### Chat
- send message
- receive message
- direct messages only for MVP

### 2.4 Real-time features (Major, 2)
Use Socket.IO for:
- live chat
- online status / presence
- live notifications
- optional recommendation refresh event

### 2.5 Public API (Major, 2)
Implement:
- API key model
- rate limit middleware
- docs
- at least 5 endpoints

Suggested external endpoints:
- `GET /api/artists`
- `GET /api/events`
- `GET /api/promoters`
- `GET /api/venues`
- `GET /api/recommendations`

### 2.6 Advanced search (Minor, 1)
Search page:
- keyword search
- style filter
- promoter filter
- venue filter
- sorting
- pagination

### 2.7 Additional browsers (Minor, 1)
Test and fix:
- Firefox
- Safari

Create a short support note.

### 2.8 Data export/import (Minor, 1)
Implement:
- export analytics/recommendations as CSV/JSON
- import curated seed data with validation

### 2.9 Analytics dashboard (Major, 2)
Dashboard must include:
- charts
- date range filters
- real-time updates
- export button

Suggested widgets:
- events ingested over time
- top styles
- top connected promoters
- recommendation distribution
- user interaction counts

### Exit criteria for Phase 2
- safe 14+ structure exists on paper and mostly in code
- social features work
- realtime works
- API works
- search works
- dashboard works
- export/import works

---

## Phase 3 — Core Domain Model
Only now build the product brain.

### 3.1 Scene graph data model
Entities:
- Artist
- Event
- Promoter
- Venue

Relations:
- Artist → Event
- Promoter → Event
- Event → Venue

### 3.2 Event-first ingestion
Build ingestion starting from events.

Each event should produce:
- title
- date
- description
- lineup
- promoter
- venue
- interest metric if available

### 3.3 Upsert strategy
For every ingested event:
- upsert Event
- upsert Promoter
- upsert Venue
- upsert Artists
- connect edges

### 3.4 Style tagging
Add normalized tags from:
- event description
- artist bio
- promoter description
- venue description

For MVP use:
- keyword extraction
- tag normalization dictionary

### 3.5 Metrics
Precompute:
- artist activity count
- promoter activity count
- venue activity count
- event similarity inputs

---

## Phase 4 — Recommendation Core
This phase is the custom major module.

### 4.1 Candidate generation
For a given user, collect candidates:
- nearby artists
- nearby promoters
- nearby venues
- nearby events

### 4.2 Inputs for ranking
Use:
- graph proximity
- connection strength
- style similarity
- entity relevance
- reachability

### 4.3 Reachability
Runtime-only metric.
Purpose:
- avoid recommending only huge unreachable nodes

Signals:
- hop distance
- repeated overlaps
- style fit
- level gap
- activity level

### 4.4 Recommendation outputs
Return:
- top promoters
- top venues
- top artists
- top events

### 4.5 Path explanation
For every recommendation, attach:
- why recommended
- relation path
- strongest overlap signal

Examples:
- user → shared artist → event → promoter
- user → event neighborhood → venue

### 4.6 Custom module justification
Document in README:
- this is project-specific
- it is technically substantial
- it is not a trivial UI feature
- it is the core differentiator of the product

### Exit criteria for Phase 4
- recommendation endpoint returns ranked results
- explanation path visible in UI
- custom module is defendable

---

## Phase 5 — UI Integration and Demo Flow

### 5.1 Main product pages
- Home
- Auth
- User profile
- Friends/chat
- Search
- Dashboard
- Recommendations
- API docs page / link

### 5.2 Recommendation page
Sections:
- recommended promoters
- recommended venues
- closest artists
- reachable events

### 5.3 Graph view
Show:
- user
- nearby artists
- events
- promoters
- venues

Use:
- node colors by type
- node size by relevance
- edge thickness by strength

### 5.4 Explanation panel
When clicking a recommendation:
- show path
- show style overlap
- show hop count
- show why it is reachable

---

## Phase 6 — Hardening for Evaluation

### 6.1 Browser support
Actively test:
- Chrome
- Firefox
- Safari

### 6.2 Validation and error cases
Check:
- bad auth input
- duplicate signup
- bad API key
- rate limit
- empty search
- websocket reconnect
- concurrent actions

### 6.3 Performance sanity
You do not need massive scale.
You do need:
- stable UI
- no crashes
- no obvious race conditions

### 6.4 Clean console / logs
- no frontend warnings
- no backend noise during demo
- meaningful error messages

### 6.5 Security sanity
- bcrypt
- protected routes
- env isolation
- no secrets in repo

---

## Phase 7 — Documentation and Submission

### 7.1 README
Must include:
- project description
- instructions
- team roles
- project management
- tech stack
- database schema
- features list
- chosen modules with points
- module implementation notes
- individual contributions
- AI usage note

### 7.2 Architecture docs
Keep in `/docs`:
- system design
- visualization guide
- development plan

### 7.3 Demo checklist
Prepare:
- seeded accounts
- seeded graph data
- stable demo flow
- module-by-module proof

---

## Recommended Team Split

### Person 1
- auth
- user profiles
- friends system

### Person 2
- chat
- websockets
- notifications / presence

### Person 3
- ingestion
- graph data model
- style tagging

### Person 4
- recommendation engine
- ranking
- path explanations

### Person 5 (if present)
- dashboard
- search
- browser support
- API docs / exports

All members should still know the whole system.

---

## Suggested Milestone Order

### Milestone 1
- Docker
- auth
- db
- UI shell

### Milestone 2
- social features
- realtime
- public API
- search

### Milestone 3
- ingestion
- graph model
- style tags
- dashboard

### Milestone 4
- recommendations
- explanation paths
- exports/imports

### Milestone 5
- browser fixes
- README
- final demo hardening

---

## What NOT to Build Before MVP
Do not spend early time on:
- machine learning
- embeddings
- OAuth
- 2FA
- file uploads
- organizations
- advanced permissions
- PWA
- SSR
- microservices
- ELK / Prometheus
- labels / radio / external social scraping

If time remains, these are bonus candidates. They are not required for the safe 16-point target.

---

## Definition of Done
The project is done when:
- mandatory requirements are satisfied
- Docker startup works
- multi-user usage works
- chosen 16 points are fully demoable
- README is complete
- recommendation engine and custom module are explainable
- the team can modify small parts live during evaluation
