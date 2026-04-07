# Berlin Nightlife Scene Graph — Visualization & Demo Guide

> Internal navigation:
- [Overview](#overview)
- [What to Demonstrate](#what-to-demonstrate)
- [User Flow](#user-flow)
- [Visualization Types](#visualization-types)
- [Graph View Design](#graph-view-design)
- [Dashboard Design](#dashboard-design)
- [Path Explorer](#path-explorer)
- [Scoring Explanations](#scoring-explanations)
- [Tech Stack](#tech-stack)
- [Demo Script](#demo-script)

---

## Overview
This document explains how to **present and visualize** the system for demos and evaluation.

Goal: make the system understandable through **graph + explanations**.

---

## What to Demonstrate
- mapping a DJ into the scene graph
- discovering nearby artists
- identifying reachable promoters/venues
- explaining *why* recommendations appear

---

## User Flow

1. Input artist (name / RA)
2. System maps to graph
3. Load:
   - nearby artists
   - promoters
   - venues
4. Show ranked recommendations
5. Click → show explanation path

---

## Visualization Types

### 1. Network Graph
- interactive force graph
- nodes: artists, events, promoters, venues
- edges: relationships

### 2. Dashboard
- cards/lists with scores
- explanations per item

### 3. Path Explorer
- explicit path (user → artist → event → promoter)

---

## Graph View Design

### Node colors
- Artist — blue
- Event — yellow
- Promoter — purple
- Venue — green

### Node size
- based on relevance (followers/activity)

### Edge width
- connection strength

### Interactions
- click node → highlight neighbors
- hover → show metadata

---

## Dashboard Design

Sections:
- Top Promoters
- Top Venues
- Closest Artists
- Reachable Events

Each card shows:
- score
- distance (hops)
- style match
- short explanation

---

## Path Explorer

Show explicit reasoning:

Example:
User → Artist A → Event X → Promoter Y

Display:
- each step
- type of relation
- why it matters

---

## Scoring Explanations

Every recommendation should include:

- **Proximity:** “2 hops away”
- **Strength:** “shared lineup 3 times”
- **Style:** “EBM / dark disco overlap”
- **Relevance:** “active promoter”
- **Reachability:** “books artists at your level”

---

## Tech Stack

### Frontend
- React + TypeScript + Vite

### Graph Visualization
- react-force-graph (fast MVP)
- Cytoscape.js (more control)

### Backend
- Python / Node
- PostgreSQL or Neo4j

---

## Demo Script

1. Enter artist (e.g. user)
2. Show graph around them
3. Highlight closest artists
4. Show top promoters
5. Click promoter → show path
6. Explain reachability
7. Show venues & events

**Key message:**
“This is not just who is popular — this is what is realistically reachable next.”
