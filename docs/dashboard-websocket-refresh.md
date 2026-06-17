# Dashboard WebSocket Refresh

Use WebSockets as an invalidation signal while keeping the existing HTTP endpoints as the source of dashboard data.

## Flow

1. The dashboard loads data through:
   - `GET /api/admin/composition`
   - `GET /api/admin/stats`
2. The frontend opens a WebSocket connection.
3. After an import or other relevant data mutation commits, the backend sends:

```json
{
  "type": "dashboard.updated",
  "areas": ["composition", "stats"]
}
```

4. The frontend receives the message and calls the existing `refetch()` functions.

## Backend Connection Manager

```python
# backend/app/dashboard_updates.py
from fastapi import WebSocket


class DashboardUpdateManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.connections.discard(websocket)

    async def broadcast(self, message: dict):
        disconnected = []

        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


dashboard_updates = DashboardUpdateManager()
```

## WebSocket Route

```python
from fastapi import WebSocket, WebSocketDisconnect
from app.dashboard_updates import dashboard_updates


@app.websocket("/api/ws/dashboard")
async def dashboard_socket(websocket: WebSocket):
    await dashboard_updates.connect(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_updates.disconnect(websocket)
```

## Broadcasting Updates

After an import successfully commits:

```python
await dashboard_updates.broadcast({
    "type": "dashboard.updated",
    "areas": ["composition", "stats"],
})
```

Broadcast only after the database transaction commits. Broadcasting earlier may cause the frontend to refetch stale data.

## Authentication

Browser WebSockets cannot directly set an `Authorization` header. Prefer a short-lived connection ticket or an HTTP-only cookie.

A token query parameter is a simpler alternative:

```ts
const token = localStorage.getItem('token')
const socket = new WebSocket(
  `${protocol}//${window.location.host}/api/ws/dashboard?token=${encodeURIComponent(token ?? '')}`,
)
```

The backend must validate the token and confirm that the user is an approved administrator before accepting the connection. Avoid logging the full WebSocket URL because its query string contains the token.

## Frontend Hook

```ts
import {useEffect} from 'react'

export type DashboardUpdate = {
  type: 'dashboard.updated'
  areas: Array<'composition' | 'stats'>
}

export function useDashboardUpdates(
  onUpdate: (message: DashboardUpdate) => void,
) {
  useEffect(() => {
    let socket: WebSocket | undefined
    let reconnectTimer: number | undefined

    const connect = () => {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const token = localStorage.getItem('token')

      socket = new WebSocket(
        `${protocol}//${location.host}/api/ws/dashboard?token=${encodeURIComponent(token ?? '')}`,
      )

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as DashboardUpdate

        if (message.type === 'dashboard.updated') {
          onUpdate(message)
        }
      }

      socket.onclose = () => {
        reconnectTimer = window.setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [onUpdate])
}
```

## Dashboard Integration

The existing `useApi` hook returns `refetch`:

```tsx
const {
  data: dashboardStatus,
  refetch: refetchComposition,
} = useApi(...)

const {
  data: dashboardStats,
  refetch: refetchMetrics,
} = useApi(fetchDashboardStats, [])
```

Handle update messages:

```tsx
const handleDashboardUpdate = useCallback(
  ({areas}: DashboardUpdate) => {
    if (areas.includes('composition')) {
      void refetchComposition()
    }

    if (areas.includes('stats')) {
      void refetchMetrics()
    }
  },
  [refetchComposition, refetchMetrics],
)

useDashboardUpdates(handleDashboardUpdate)
```

## Operational Notes

- Add reconnect handling with exponential backoff.
- Validate incoming JSON before using it.
- Debounce repeated update messages during large imports.
- Send heartbeat messages or configure proxy timeouts.
- Configure Nginx WebSocket upgrade headers.
- Keep HTTP refetching instead of sending the full dataset over the socket.
- For multiple backend instances, use Redis Pub/Sub. An in-memory manager only reaches clients connected to the same process.
