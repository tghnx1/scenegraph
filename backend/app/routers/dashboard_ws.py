import json
import logging
from typing import Annotated

import psycopg
import psycopg.rows
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.auth import _user_id_from_jwt
from app.db import DATABASE_URL, get_connection

logger = logging.getLogger(__name__)

router = APIRouter()

NOTIFY_CHANNEL = "scenegraph_dashboard_refresh"
ALL_AREAS = ["composition", "metrics"]


@router.websocket("/dashboard")
async def dashboard_ws(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
):
    if not token:
        await websocket.close(code=1008)
        return

    try:
        with get_connection() as auth_conn:
            _user_id_from_jwt(token, auth_conn)
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        async with await psycopg.AsyncConnection.connect(
            DATABASE_URL,
            autocommit=True,
            row_factory=psycopg.rows.dict_row,
        ) as conn:
            await conn.execute(f"LISTEN {NOTIFY_CHANNEL}")

            async for _ in conn.notifies():
                await websocket.send_text(json.dumps({
                    "type": "dashboard.updated",
                    "areas": ALL_AREAS,
                }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"Dashboard WS error: {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass