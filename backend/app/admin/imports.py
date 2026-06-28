from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from psycopg import Connection

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_import_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Import file must be a JSON file")
    return SAFE_FILENAME_RE.sub("_", name) or "dashboard-import.json"


def imported_source_ids(payload: Any) -> list[str]:
    events = payload.get("events", []) if isinstance(payload, dict) else payload
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="Import JSON must be a list or an object with an events list")

    ids: list[str] = []
    for event in events:
        if isinstance(event, dict) and event.get("id") is not None:
            ids.append(str(event["id"]))
    return ids


def run_dashboard_import(*, filename: str, payload: Any) -> tuple[str, list[str]]:
    safe_name = safe_import_filename(filename)
    source_ids = imported_source_ids(payload)
    if not source_ids:
        raise HTTPException(status_code=400, detail="Import JSON does not contain any event ids")

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=f"-{safe_name}",
        prefix="dashboard-import-",
        dir="/tmp",
        delete=False,
    ) as temp_file:
        json.dump(payload, temp_file)
        temp_path = Path(temp_file.name)

    try:
        subprocess.run(
            ["python", "scripts/import_events.py", str(temp_path)],
            cwd="/app",
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Import timed out") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Import failed").strip()
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return safe_name, source_ids


def summarize_import(connection: Connection, *, source_ids: list[str], filename: str, admin: dict) -> tuple[dict | None, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, title
            FROM events
            WHERE ra_event_id = ANY(%s)
            ORDER BY id DESC
            LIMIT 1
            """,
            (source_ids,),
        )
        event = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS imported_count
            FROM events
            WHERE ra_event_id = ANY(%s)
            """,
            (source_ids,),
        )
        imported_count = int(cursor.fetchone()["imported_count"])

        cursor.execute(
            """
            INSERT INTO activity_log (user_id, username, event_type, target)
            VALUES (%s, %s, %s, %s)
            """,
            (
                admin["id"],
                admin["username"],
                "dashboard import completed",
                filename,
            ),
        )
    connection.commit()
    return event, imported_count
