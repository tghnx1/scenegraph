from __future__ import annotations

from typing import Literal

from fastapi import WebSocket
from starlette.websockets import WebSocketState


DashboardUpdateArea = Literal["composition", "metrics"]


class DashboardUpdateManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, areas: list[DashboardUpdateArea]) -> None:
        if not areas:
            return

        message = {
            "type": "dashboard.updated",
            "areas": areas,
        }
        disconnected_clients: list[WebSocket] = []

        for websocket in tuple(self._clients):
            if websocket.client_state != WebSocketState.CONNECTED:
                disconnected_clients.append(websocket)
                continue

            try:
                await websocket.send_json(message)
            except RuntimeError:
                disconnected_clients.append(websocket)

        for websocket in disconnected_clients:
            self.disconnect(websocket)


dashboard_updates = DashboardUpdateManager()


async def broadcast_dashboard_update(areas: list[DashboardUpdateArea]) -> None:
    await dashboard_updates.broadcast(areas)
