from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

import psycopg
from fastapi import WebSocket

from app.db import DATABASE_URL
from app.recommendation_jobs import JOB_UPDATED_CHANNEL


logger = logging.getLogger(__name__)
RECONNECT_DELAY_SECONDS = 2.0


class RecommendationJobSocketHub:
    """Track local WebSocket clients and fan out job signals by authenticated user."""

    # Initialize an in-process registry for browser sockets owned by each user.
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    # Register an accepted WebSocket for one authenticated user.
    async def add(self, user_id: int, websocket: WebSocket) -> None:
        """Register one accepted WebSocket for job events owned by a user."""
        async with self._lock:
            self._connections[user_id].add(websocket)

    # Remove one disconnected socket while preserving the user's other sessions.
    async def remove(self, user_id: int, websocket: WebSocket) -> None:
        """Remove a disconnected socket without disturbing the user's other sessions."""
        async with self._lock:
            sockets = self._connections.get(user_id)
            if sockets is None:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)

    # Forward a status signal only to local sockets owned by the target user.
    async def send_to_user(self, user_id: int, message: dict[str, object]) -> None:
        """Send a small status signal to every local browser session for one user."""
        async with self._lock:
            sockets = list(self._connections.get(user_id, ()))

        disconnected: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            await self.remove(user_id, websocket)

    # Recover possibly missed updates after reconnecting the PostgreSQL listener.
    async def request_resync(self) -> None:
        """Ask all locally connected clients to re-read durable active job state once."""
        async with self._lock:
            user_ids = list(self._connections)
        for user_id in user_ids:
            await self.send_to_user(user_id, {"type": "recommendation.jobs.resync"})


recommendation_job_socket_hub = RecommendationJobSocketHub()


# Validate and minimize database notification data before browser delivery.
def _parse_job_update(payload: str) -> tuple[int, dict[str, object]] | None:
    """Validate a PostgreSQL notification before exposing it to browser clients."""
    try:
        message = json.loads(payload)
        user_id = int(message["userId"])
        job_id = str(message["jobId"])
        status = str(message["status"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Ignoring invalid recommendation job notification: %r", payload)
        return None

    if status not in {"queued", "running", "completed", "failed"}:
        logger.warning("Ignoring recommendation job notification with status %r", status)
        return None
    return user_id, {
        "type": "recommendation.job.updated",
        "jobId": job_id,
        "status": status,
    }


# Keep one PostgreSQL LISTEN connection open per backend process.
async def listen_for_recommendation_job_updates() -> None:
    """Forward committed PostgreSQL job notifications to local WebSocket clients."""
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(
                DATABASE_URL,
                autocommit=True,
            ) as connection:
                await connection.execute(f"LISTEN {JOB_UPDATED_CHANNEL}")
                logger.info("Recommendation WebSocket hub listening on %s", JOB_UPDATED_CHANNEL)
                await recommendation_job_socket_hub.request_resync()

                async for notification in connection.notifies():
                    parsed = _parse_job_update(notification.payload)
                    if parsed is None:
                        continue
                    user_id, message = parsed
                    await recommendation_job_socket_hub.send_to_user(user_id, message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Recommendation job notification listener failed; reconnecting in %.1f seconds",
                RECONNECT_DELAY_SECONDS,
            )
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
