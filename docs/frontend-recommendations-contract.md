# Frontend Contract (Minimal MVP): Artist -> Promoters

Last Updated: 2026-05-25
Endpoint: `GET /api/recommendations/artists/{artist_id}/promoters`

## Goal

Frontend MVP should render only:

1. promoter card with explanation text
2. local explanation graph

No extra analytics UI for now.

## Request

```http
GET /api/recommendations/artists/{artist_id}/promoters?limit=20&exclude_existing=true
```

Use `debug=false` in frontend by default.

## What Frontend Must Render

For each promoter card (`recommendations[]`):

- `name`
- `score`
- all `reasons` (show full list, no collapse)

For explanation graph:

- `graph.nodes`
- `graph.links`

## Minimal Response Fields Frontend Should Depend On

```ts
interface MinimalPromoterRecommendationResponse {
  entityId: number;
  entityType: "artist";
  recommendations: Array<{
    id: number;
    type: "promoter";
    name: string;
    score: number;
    reasons: string[];
  }>;
  graph: {
    nodes: Array<{
      id: string;
      entityId: number;
      type: "artist" | "event" | "venue" | "promoter";
      name: string;
    }>;
    links: Array<{
      source: string;
      target: string;
      relationship: string;
      evidenceType?: string | null;
      style?: "solid" | "dashed" | "dotted" | null;
      strength?: number | null;
    }>;
  };
}
```

## Explicitly Out of Scope (For Now)

Do not render for MVP UI:

- `status`
- `warmConnectionCount`
- `directConnectionCount`
- `scoreBreakdown` visuals
- `debug` data
- tabs by `warmRecommendations` / `discoveryRecommendations`

These fields can stay in API but are not required in frontend MVP.

## Example (Minimal Consumption)

```json
{
  "entityId": 2178,
  "entityType": "artist",
  "recommendations": [
    {
      "id": 98,
      "type": "promoter",
      "name": "Crack Bellmer",
      "score": 0.52,
      "reasons": [
        "1 co-played artists connected: dOctOr doms",
        "12 similar artists connected: ...",
        "9 similar promoter events: ...",
        "11 related promoter events: ..."
      ]
    }
  ],
  "graph": {
    "nodes": [
      {
        "id": "artist-2178",
        "entityId": 2178,
        "type": "artist",
        "name": "NUARRR"
      },
      {
        "id": "promoter-98",
        "entityId": 98,
        "type": "promoter",
        "name": "Crack Bellmer"
      },
      {
        "id": "artist-594",
        "entityId": 594,
        "type": "artist",
        "name": "dOctOr doms"
      },
      {
        "id": "event-189",
        "entityId": 189,
        "type": "event",
        "name": "SWARM"
      },
      {
        "id": "venue-12",
        "entityId": 12,
        "type": "venue",
        "name": "Mensch Meier"
      }
    ],
    "links": [
      {
        "source": "artist-2178",
        "target": "event-189",
        "relationship": "played",
        "evidenceType": "warm_network",
        "style": "solid",
        "strength": 0.72
      },
      {
        "source": "artist-594",
        "target": "event-189",
        "relationship": "played",
        "evidenceType": "warm_network",
        "style": "solid",
        "strength": 0.72
      },
      {
        "source": "promoter-98",
        "target": "event-189",
        "relationship": "organized",
        "evidenceType": "warm_network",
        "style": "solid",
        "strength": 0.72
      },
      {
        "source": "event-189",
        "target": "venue-12",
        "relationship": "at",
        "evidenceType": "warm_network",
        "style": "solid",
        "strength": 0.64
      }
    ]
  }
}
```
