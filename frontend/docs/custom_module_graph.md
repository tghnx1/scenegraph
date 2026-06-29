# Custom Major Module: Interactive Scene Graph and Evidence Explorer

## Module claim

Claim:

 **IV.10 Modules of choice - Major module**.

Module name:

**Interactive Scene Graph and Recommendation Evidence Explorer**

## What the module does

The module turns the project data into an interactive graph. Instead of showing artists, events, venues, and promoters as separate lists, it shows how they are connected and why the system considers them related.

The graph can display:

- artists
- events
- venues
- promoters
- relationships between them, such as artists playing at events, events happening at venues, and promoters organizing events
- recommendation evidence paths that explain why a promoter, artist, venue, or event is relevant

The frontend graph is interactive. Users can click nodes, filter the visible graph, inspect selected entities, and view focused relationship paths.

## Why we chose this module

The project is an experimental exploration of a music scene. A graph is a natural fit because music-scene data is relationship-based:

- artists play together
- artists perform at events
- events happen at venues
- promoters organize events
- similar artists and events can lead to useful recommendations

A normal table or list can show the data, but does not clearly show the network connectivity. The graph helps users understand the structure of the scene visually.

## Technical challenges

This module is more than a simple chart because the graph is generated from real application data and from recommendation evidence built from that data.

Main technical challenges:

- building graph nodes and links from relational database tables
- supporting different entity types in one shared graph model
- filtering graph data by genre, date range, and limit
- supporting ego graphs, where the graph is centered around one artist, event, venue, or promoter
- creating recommendation explanation paths, not only recommendation scores
- showing graph evidence with different link styles and strengths
- rendering a large interactive graph in the frontend with zooming, dragging, clicking, filtering, and highlighting for interactivity

## How it adds value to the project

The graph makes the application easier to understand and more useful.

It adds value because:

- users can explore the scene visually instead of reading only lists
- recommendations become explainable because the user can see the path behind them
- artists can discover relevant promoters, venues, and nearby scene connections

## Why it deserves Major module status

This module deserves Major status because it is not just UI decoration or a static visualization.

It includes backend, frontend, API design, and graph-specific logic:

- backend endpoints generate graph data from the database
- graph responses use typed nodes and links
- the frontend renders an interactive force-directed graph
- users can filter and focus the graph
- recommendation evidence is represented as graph paths
- the module connects directly to the core purpose of the project

The graph required custom logic for relationship modeling, path explanation, filtering, and interaction.

## Main implementation files

- `backend/app/routers/graph.py` - builds the main graph API response
- `backend/app/routers/graph_ego.py` - builds focused ego graphs for one entity
- `backend/app/promoter_graph.py` - builds recommendation evidence paths
- `frontend/src/api/graph.ts` - frontend graph API calls
- `frontend/src/types/graph.ts` - frontend graph types
- `frontend/src/pages/GraphPage.tsx` - graph page layout
- `frontend/src/pages/components/GraphPanel.tsx` - interactive graph rendering and behavior
- `frontend/src/pages/components/GraphDataFilter.tsx` - graph filters
- `frontend/src/pages/components/GraphNodeFilter.tsx` - node type visibility controls

## Short explanation

This module is chosen because the project is about relationships inside a music scene. The graph turns separate database records into a connected scene map. It is technically substantial because it requires backend graph generation, typed API responses, frontend force-graph rendering, filtering, node interaction, and recommendation path explanations. It adds value by making recommendations understandable and by helping users explore artists, events, venues, and promoters visually.

## Boundary with the AI module

The recommendation engine file owns scoring and ranking math.
This file owns graph visualization, graph evidence, and path explanation UX.
The two modules are connected, but they are intentionally documented separately so the evaluator sees one AI module and one graph/evidence module.
