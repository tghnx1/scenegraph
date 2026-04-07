# Berlin Scene Graph — Concrete Implementation Notes

## Why this file exists
This file turns the module list into **concrete implementation examples** for our specific project, so the team can understand what is actually required and what can stay out of scope.

---

## 1) Web — Real-time features (Major, 2 pts)

### What is the module asking for
Real-time updates across clients using WebSockets or similar technology.

### What we will implement in our project
We will keep this module **minimal and defendable**:

- **Real-time chat updates**
  - direct messages appear instantly for both users
- **Presence / online activity**
  - show whether a friend is online/offline
- **Real-time notifications**
  - friend request accepted
  - new message received
- **Optional: recommendation refresh event**
  - only if already easy to plug in later

### What is NOT required for this module
We do **not** need:
- live graph animation
- continuous recommendation recomputation
- fancy streaming UI

### Safe conclusion
To validate this module, the safest path is:
1. live chat
2. presence
3. notifications

That is enough to clearly demonstrate real-time behavior.

---

## 2) Web — ORM (Minor, 1 pt)

### What Prisma is
Prisma is an **ORM** (Object-Relational Mapper).

It means:
- we define database models in a schema file
- Prisma generates typed database access code
- we use it for:
  - schema definition
  - migrations
  - queries

### Why we use it
Instead of writing raw SQL everywhere, Prisma lets us do things like:

```ts
const artists = await prisma.artist.findMany({
  where: { styles: { has: "ebm" } }
})
```

### What this gives us
- clearer schema
- safer queries
- easier migrations
- easy justification for the ORM module

### What we need to show in evaluation
- Prisma schema
- migrations
- real queries in code
- relations between tables

---

## 3) Web — Advanced search (Minor, 1 pt)

### What this means in our project
Yes, this is a **user-facing search feature**.

### We will implement search for:
- artists
- events
- promoters
- venues

### And support:
- keyword search
- filtering by style
- filtering by promoter
- filtering by venue
- sorting
- pagination

### Example
A user can search:
- style = EBM
- venue = about blank
- sort by newest event

### Important
This module is **not** just a backend query.
It should be visible in the product and usable by the user.

---

## 4) AI module question

### Can an AI agent give us AI points?
Potentially yes, but only if the module clearly matches what the subject asks.

### The risky part
The subject AI section asks for things like:
- complete RAG system
- complete LLM interface
- recommendation system using machine learning

A vague “agent that analyzes opportunities” is interesting, but it can be challenged during evaluation if it does not cleanly map to one of those modules.

### Honest recommendation
For the safe 16-point plan, we should **not depend on AI points**.

### If we add an AI agent later
Then the safest direction would be one of these:

#### Option A — complete LLM system interface (Major)
Example:
- user asks:
  - “Which promoter should I contact first?”
  - “Summarize these opportunities”
- LLM streams back analysis
- proper error handling
- rate limiting

#### Option B — complete RAG system (Major)
Example:
- retrieval over ingested events, artists, promoters, venues
- user asks questions in natural language
- system retrieves context and answers

### But for now
AI should be treated as:
- optional extension
- not part of the safe 16-point target

---

## 5) Concrete implementation of our custom module

### Module of choice — Scene graph recommendation and path explanation engine (Major, 2 pts)

This is our most project-specific module.

### What we will build
A graph-based system using:
- Artist
- Event
- Promoter
- Venue

### Core relations
- Artist -> played_at -> Event
- Promoter -> organizes -> Event
- Event -> takes_place_at -> Venue

### Our recommendation logic
For a given user:
- find nearby artists through shared events and scene overlap
- find relevant promoters through connected artists and events
- find relevant venues through connected promoters and events
- rank opportunities using:
  - graph proximity
  - connection strength
  - style overlap
  - relevance
  - reachability

### Example in our project
User profile:
- style interest: dark disco / EBM
- history: played with Artist A at Event X

System can recommend:
- Promoter P, because:
  - Artist A also played two events organized by Promoter P
  - Promoter P runs events tagged with similar styles
  - venue level is reachable for the user

### Explanation path in UI
We should show paths like:
- user -> Artist A -> Event X -> Promoter P
- user -> Event X -> Venue V

### Why this is defendable as a custom major module
- it is core product logic
- it is project-specific
- it is not a trivial CRUD feature
- it requires graph modeling, ranking, and explanation

---

## 6) What we actually need to build vs what we can skip

### Must build
- auth
- database
- Docker
- profile
- friends
- chat
- realtime basics
- public API
- search
- dashboard
- graph model
- recommendation engine
- explanation paths

### Can skip for now
- ML
- embeddings
- AI agent
- OAuth
- 2FA
- file upload
- organizations
- advanced permissions
- microservices
- PWA
- SSR

---

## 7) Practical recommendation

### For the current milestone
Build modules in this order:
1. mandatory skeleton
2. user interaction
3. realtime
4. API
5. search
6. dashboard
7. custom recommendation engine

### Do not let AI expand the scope early
If AI is added, do it only after the 16-point set is already safe.
