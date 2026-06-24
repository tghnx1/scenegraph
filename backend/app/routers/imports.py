import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from psycopg import Connection

from app.auth import require_admin
from app.db import get_db

router = APIRouter()

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class ImportResponse(BaseModel):
    success: bool
    message: str
    imported_file: str
    event_id: int | None = None
    event_title: str | None = None
    imported_count: int = 0


class ImportRequest(BaseModel):
    filename: str
    payload: Any


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


@router.post("/import", response_model=ImportResponse)
def run_import(
    request: ImportRequest,
    admin: dict = Depends(require_admin),
    db: Connection = Depends(get_db),
) -> ImportResponse:
    filename = safe_import_filename(request.filename)
    source_ids = imported_source_ids(request.payload)
    if not source_ids:
        raise HTTPException(status_code=400, detail="Import JSON does not contain any event ids")

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=f"-{filename}",
        prefix="dashboard-import-",
        dir="/tmp",
        delete=False,
    ) as temp_file:
        json.dump(request.payload, temp_file)
        temp_path = Path(temp_file.name)

    try:
        result = subprocess.run(
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

    with db.cursor() as cursor:
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
    db.commit()

    return ImportResponse(
        success=True,
        message=(
            f"Imported {imported_count} event(s); latest is {event['title']} as event #{event['id']}"
            if event
            else f"Imported {filename}"
        ),
        imported_file=filename,
        event_id=event["id"] if event else None,
        event_title=event["title"] if event else None,
        imported_count=imported_count,
    )
