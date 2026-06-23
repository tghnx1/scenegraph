import asyncio
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
PING_INTERVAL = 30


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

            stop_event = asyncio.Event()

            async def notify_task():
                try:
                    async for notify in conn.notifies():
                        if stop_event.is_set():
                            break
                        await websocket.send_text(json.dumps({
                            "type": "dashboard.updated",
                            "areas": ALL_AREAS,
                        }))
                except Exception as e:
                    logger.error("Fatal error in the database listener: %s", e, exc_info=True)
                finally:
                    stop_event.set()

            async def keepalive_task():
                try:
                    while not stop_event.is_set():
                        await asyncio.sleep(PING_INTERVAL)
                        if stop_event.is_set():
                            break
                        await websocket.send_text('{"type":"ping"}')
                except Exception as e:
                    pass
                finally:
                    stop_event.set()

            async def ws_receive_task():
                try:
                    while not stop_event.is_set():
                        await websocket.receive_text()
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.error("Unexpected error receiving WS messages: %s", e, exc_info=True)
                finally:
                    stop_event.set()

            tasks = [
                asyncio.create_task(notify_task()),
                asyncio.create_task(keepalive_task()),
                asyncio.create_task(ws_receive_task()),
            ]

            await stop_event.wait()

            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logger.exception("Critical error in the WebSocket lifecycle")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass