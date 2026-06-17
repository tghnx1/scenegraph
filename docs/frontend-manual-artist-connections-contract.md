# Frontend Contract: Manual Artist Connections

Last Updated: 2026-06-11

## Goal

Manual artist connections let a source artist explicitly mark another artist as
someone they know or trust. The recommendation engine uses these directional
connections as manual warm-network evidence.

The frontend can currently:

1. list the manual connections of an artist
2. add or refresh a manual connection
3. remove a manual connection

## Base URL

The frontend should use the existing relative API prefix:

```text
/api
```

Through the local nginx gateway, this resolves to `http://localhost:8080/api`.

## TypeScript Types

```ts
export interface ManualArtistConnection {
  sourceArtistId: number
  connectedArtistId: number
  connectedArtistName: string
  createdAt: string
  updatedAt: string
}

export interface ManualArtistConnectionsResponse {
  items: ManualArtistConnection[]
}

export interface AddManualArtistConnectionRequest {
  connectedArtistId: number
}

export interface ApiError {
  detail: string
}
```

`createdAt` and `updatedAt` are ISO 8601 datetime strings.

## List Manual Connections

```http
GET /api/artists/{sourceArtistId}/known-artists
```

Example:

```http
GET /api/artists/2178/known-artists
```

Successful response:

```json
{
  "items": [
    {
      "sourceArtistId": 2178,
      "connectedArtistId": 1740,
      "connectedArtistName": "Zee Mon",
      "createdAt": "2026-05-26T18:02:20.544000+02:00",
      "updatedAt": "2026-05-26T18:02:20.544000+02:00"
    }
  ]
}
```

If the source artist has no manual connections, the API returns:

```json
{
  "items": []
}
```

Connections are sorted by the most recently updated connection first.

## Add Or Refresh A Manual Connection

```http
POST /api/artists/{sourceArtistId}/known-artists
Content-Type: application/json
```

Request body:

```json
{
  "connectedArtistId": 1740
}
```

Successful response:

```json
{
  "sourceArtistId": 2178,
  "connectedArtistId": 1740,
  "connectedArtistName": "Zee Mon",
  "createdAt": "2026-05-26T18:02:20.544000+02:00",
  "updatedAt": "2026-06-11T14:30:00.000000+02:00"
}
```

This endpoint is an upsert:

- a new pair creates a manual connection
- posting an existing pair does not create a duplicate
- posting an existing pair refreshes its `updatedAt` value

## Remove A Manual Connection

```http
DELETE /api/artists/{sourceArtistId}/known-artists/{connectedArtistId}
```

Example:

```http
DELETE /api/artists/2178/known-artists/1740
```

The successful response contains the removed connection:

```json
{
  "sourceArtistId": 2178,
  "connectedArtistId": 1740,
  "connectedArtistName": "Zee Mon",
  "createdAt": "2026-05-26T18:02:20.544000+02:00",
  "updatedAt": "2026-06-11T14:30:00.000000+02:00"
}
```

## Error Responses

Errors use the standard FastAPI error shape:

```json
{
  "detail": "artist 1740 not found"
}
```

Expected status codes:

| Status | Meaning |
| --- | --- |
| `400` | The source artist and connected artist are the same artist. |
| `404` | The source artist, connected artist, or requested connection does not exist. |
| `422` | The request path or JSON body is invalid. |
| `500` | The database operation failed unexpectedly. |

Current explicit error messages include:

```text
source artist and connected artist must be different
artist {artistId} not found
manual artist connection not found
```

## Frontend Integration Rules

- Treat connections as directional. `2178 -> 1740` does not create
  `1740 -> 2178`.
- Use the artist ID of the currently displayed or managed profile as
  `sourceArtistId`.
- Use artist search results to select `connectedArtistId`.
- Exclude the source artist from the connection picker.
- Disable or mark artists that already exist in `items`.
- After adding or removing a connection, refresh promoter recommendations
  because manual connections affect recommendation scores and paths.
- The frontend may optimistically add or remove a connection, but it must
  restore the previous state if the API request fails.

## Example Frontend Client

```ts
const API_BASE_URL = '/api'

export async function listManualArtistConnections(
  sourceArtistId: number,
): Promise<ManualArtistConnectionsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/artists/${sourceArtistId}/known-artists`,
  )

  if (!response.ok) {
    throw await response.json()
  }

  return response.json()
}

export async function addManualArtistConnection(
  sourceArtistId: number,
  connectedArtistId: number,
): Promise<ManualArtistConnection> {
  const response = await fetch(
    `${API_BASE_URL}/artists/${sourceArtistId}/known-artists`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connectedArtistId }),
    },
  )

  if (!response.ok) {
    throw await response.json()
  }

  return response.json()
}

export async function removeManualArtistConnection(
  sourceArtistId: number,
  connectedArtistId: number,
): Promise<ManualArtistConnection> {
  const response = await fetch(
    `${API_BASE_URL}/artists/${sourceArtistId}/known-artists/${connectedArtistId}`,
    { method: 'DELETE' },
  )

  if (!response.ok) {
    throw await response.json()
  }

  return response.json()
}
```

## Current Backend Behavior And Follow-Ups

The current backend already provides the list, upsert, and delete operations,
and the database migration prevents duplicate and self-referencing
connections.

The migration `20260525194000_add_artist_manual_connections` must be applied in
every environment. The table is required by the backend schema preflight.

Before this feature is production-ready, the backend still needs:

1. authentication and artist-profile ownership enforcement, which are being
   implemented separately
2. authorization tests after the ownership enforcement is merged

Until authorization is implemented, any client that can reach the API can
modify manual connections for any artist ID.
