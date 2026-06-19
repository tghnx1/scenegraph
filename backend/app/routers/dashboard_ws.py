from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any

import psycopg
from fastapi import APIRouter, WebSocket
from psycopg import sql
from starlette.websockets import WebSocketState

from app.db import DATABASE_URL


router = APIRouter()
logger = logging.getLogger(__name__)

DASHBOARD_REFRESH_CHANNEL = "scenegraph_dashboard_refresh"
DASHBOARD_REFRESH_TYPE = "dashboard_refresh_required"


def dashboard_message_from_payload(payload: str) -> dict[str, Any]:
    message: dict[str, Any] = {
        "type": DASHBOARD_REFRESH_TYPE,
        "reason": "database_changed",
    }
    if not payload:
        return message

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        message["reason"] = payload
        return message

    if isinstance(data, dict):
        message.update(data)

    if not isinstance(message.get("type"), str):
        message["type"] = DASHBOARD_REFRESH_TYPE
    if not isinstance(message.get("reason"), str):
        message["reason"] = "database_changed"
    return message


async def relay_dashboard_notifications(websocket: WebSocket) -> None:
    async with await psycopg.AsyncConnection.connect(
        DATABASE_URL,
        autocommit=True,
    ) as connection:
        await connection.execute(
            sql.SQL("LISTEN {}").format(sql.Identifier(DASHBOARD_REFRESH_CHANNEL))
        )

        async for notify in connection.notifies():
            await websocket.send_json(dashboard_message_from_payload(notify.payload))


async def wait_for_client_disconnect(websocket: WebSocket) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    listener_task = asyncio.create_task(relay_dashboard_notifications(websocket))
    disconnect_task = asyncio.create_task(wait_for_client_disconnect(websocket))

    done, pending = await asyncio.wait(
        {listener_task, disconnect_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    for task in done:
        if task.cancelled():
            continue
        exception = task.exception()
        if exception is not None:
            logger.error(
                "Dashboard WebSocket closed after listener failure",
                exc_info=(type(exception), exception, exception.__traceback__),
            )

    if websocket.client_state != WebSocketState.DISCONNECTED:
        with suppress(RuntimeError):
            await websocket.close()
