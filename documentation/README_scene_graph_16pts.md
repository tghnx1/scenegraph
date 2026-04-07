# Berlin Scene Graph

*This project has been created as part of the 42 curriculum by <login1>, <login2>, <login3>, <login4>[, <login5>].*

## Description
Berlin Scene Graph is a web application for emerging DJs. It builds a graph of the local Berlin scene from event data and helps users discover realistic next opportunities: relevant promoters, venues, artists, and events.

The product focuses on **reachability**, not just popularity:
- Who is actually close to your current network
- Which venues and promoters fit your style
- Which opportunities are realistic at your current level

## Core Features
- User accounts and authentication
- Artist profile and scene profile
- Event ingestion and graph building
- Search and filtering across artists, events, promoters, venues
- Recommendation engine based on graph proximity and style tags
- Analytics dashboard with graph and recommendation views
- Public API for external access
- Real-time updates for recommendations, notifications, and activity
- Basic social layer: profiles, friends, chat

---

## Technical Stack

### Frontend
- **React**
- **TypeScript**
- **Vite**
- **Tailwind CSS**
- **react-force-graph** or **Cytoscape.js**
- **React Router**
- **TanStack Query**
- **Zod** for form validation

### Backend
- **Node.js**
- **Express**
- **TypeScript**
- **Socket.IO**
- **JWT** or secure cookie sessions
- **bcrypt**
- **Express rate limiting**
- **Swagger / OpenAPI** for API documentation

### Database
- **PostgreSQL**
- **Prisma ORM**

### Infrastructure
- **Docker Compose**
- **Nginx** as reverse proxy / HTTPS termination
- **.env** + **.env.example**

### Testing / Quality
- **Vitest** or **Jest**
- **ESLint**
- **Prettier**

---

## Why This Stack
- **React + Express** cleanly satisfies the requirement to use a framework for both frontend and backend.
- **PostgreSQL + Prisma** makes the relational graph model easy to implement and explain.
- **Socket.IO** is the fastest path to a demonstrable real-time module.
- **Docker Compose** keeps local setup simple and satisfies the containerization requirement.
- **Tailwind CSS** helps deliver a responsive UI faster.
- **Nginx** gives a realistic path to HTTPS everywhere for backend traffic.

---

## Mandatory Requirements Checklist

### Core web app
- [ ] Frontend
- [ ] Backend
- [ ] Database
- [ ] Responsive UI
- [ ] Dockerized single-command startup
- [ ] Latest Chrome compatibility
- [ ] No browser console errors
- [ ] Privacy Policy page
- [ ] Terms of Service page

### Security / configuration
- [ ] Secure signup / login
- [ ] Hashed and salted passwords
- [ ] Validation on frontend and backend
- [ ] `.env` ignored by git
- [ ] `.env.example` provided
- [ ] HTTPS for backend
- [ ] Meaningful git history from all team members

### Multi-user support
- [ ] Multiple concurrent users
- [ ] Concurrent actions handled correctly
- [ ] Real-time updates where applicable
- [ ] No race conditions / data corruption

---

## Chosen Modules (Target: 16 points, no fuzzy claims)

### 1) Web — Framework for both frontend and backend (**Major, 2 pts**)
Implementation:
- React frontend
- Express backend

### 2) Web — Real-time features using WebSockets (**Major, 2 pts**)
Implementation:
- Live recommendation refresh
- Real-time notifications
- Presence / online activity
- Real-time chat updates

### 3) Web — Allow users to interact with other users (**Major, 2 pts**)
Implementation:
- Basic chat system
- User profile page
- Friends system (add/remove/list)

### 4) Web — Public API (**Major, 2 pts**)
Implementation:
- API key protection
- Rate limiting
- Documentation
- At least 5 endpoints:
  - `GET /api/artists`
  - `GET /api/events`
  - `GET /api/promoters`
  - `GET /api/venues`
  - `GET /api/recommendations`
  - `POST /api/recommendations/refresh`
  - `PUT /api/profile`
  - `DELETE /api/friends/:id`

### 5) Web — ORM (**Minor, 1 pt**)
Implementation:
- Prisma for schema, migrations, and queries

### 6) Web — Advanced search (**Minor, 1 pt**)
Implementation:
- Search across artists / events / promoters / venues
- Filtering by style, venue, promoter, activity
- Sorting and pagination

### 7) Accessibility & Internationalization — Support for additional browsers (**Minor, 1 pt**)
Implementation:
- Full testing and fixes for **Firefox** and **Safari**
- Documented browser-specific limitations if any

### 8) Data & Analytics — Advanced analytics dashboard with data visualization (**Major, 2 pts**)
Implementation:
- Interactive charts
- Real-time data updates
- Export functionality
- Date ranges and filters

### 9) Data & Analytics — Data export and import functionality (**Minor, 1 pt**)
Implementation:
- Export recommendations / analytics / graph-related data as JSON and CSV
- Import curated event or artist datasets with validation

### 10) Modules of choice — Scene graph recommendation and path explanation engine (**Major, 2 pts**)
Implementation:
- Graph-based scene model (Artist / Event / Promoter / Venue)
- Reachability score
- Recommendation explanation paths:
  - user → artist → event → promoter
  - user → event → venue
- Why this deserves Major:
  - project-specific core logic
  - non-trivial graph modeling
  - custom ranking and explanation layer
  - central value of the product

### Total
**16 points**

---

## Modules We Are NOT Claiming
To stay conservative during evaluation, we are **not** claiming:
- AI recommendation system using machine learning
- OAuth
- 2FA
- organization system
- advanced permissions
- PWA
- SSR
- file upload
- GDPR module
- microservices
- monitoring / ELK / Prometheus

These can be added later, but they are outside the minimum validated target.

---

## Database Schema (High-Level)

### Entities
- **User**
- **Artist**
- **Event**
- **Promoter**
- **Venue**
- **Friendship**
- **Message**
- **Notification**
- **UserInteraction**
- **RecommendationSnapshot**
- **ApiKey**

### Core relations
- Artist → Event (`played_at`)
- Promoter → Event (`organizes`)
- Event → Venue (`takes_place_at`)
- User ↔ Friendship ↔ User
- User → Message
- User → Notification
- User → UserInteraction

---

## API Draft
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/profile/me`
- `PUT /api/profile/me`
- `GET /api/artists`
- `GET /api/events`
- `GET /api/promoters`
- `GET /api/venues`
- `GET /api/recommendations`
- `POST /api/recommendations/refresh`
- `GET /api/analytics/overview`
- `GET /api/search`

---

## Project Management
- Issue tracking: GitHub Issues / Projects
- Communication: Discord
- Planning: weekly sprint planning + short async daily check-ins
- Code review: at least one peer review for major PRs

---

## Team Information
_To be completed._

### Example format
- **<login1>** — Product Owner + Developer
- **<login2>** — Project Manager + Developer
- **<login3>** — Tech Lead + Developer
- **<login4>** — Developer
- **<login5>** — Developer

---

## Features List
_To be completed with owner per feature._

Suggested format:
- Authentication — <member>
- Event ingestion — <member>
- Graph building — <member>
- Recommendation engine — <member>
- Dashboard — <member>
- Search — <member>
- Chat / friends — <member>
- Public API — <member>

---

## Individual Contributions
_To be completed before submission._

---

## Instructions

### Prerequisites
- Docker
- Docker Compose
- Node.js (if running outside containers)
- PostgreSQL (if running outside containers)

### Run
```bash
docker compose up --build
```

### Environment
Create a `.env` file from `.env.example`.

---

## Resources
_To be completed._

Examples:
- React docs
- Express docs
- Prisma docs
- PostgreSQL docs
- Socket.IO docs
- Docker docs
- Any graph visualization library docs
- Clear note explaining how AI was used during the project

---

## Known Risks
- Real-time and social features add complexity early
- Search and dashboard can grow in scope quickly
- Browser support must be tested intentionally, not assumed

---

## Scope Discipline
This project will prioritize:
1. Mandatory requirements
2. Reliable 16-point module set
3. Core product value

Anything outside this order is optional.
