from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.admin import imports as admin_imports_service
from app.auth import require_admin
from app.db import get_connection

router = APIRouter()


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


@router.post("/import", response_model=ImportResponse)
def run_import(
    request: ImportRequest,
    admin: dict = Depends(require_admin),
) -> ImportResponse:
    filename, source_ids = admin_imports_service.run_dashboard_import(
        filename=request.filename,
        payload=request.payload,
    )

    with get_connection() as connection:
        event, imported_count = admin_imports_service.summarize_import(
            connection,
            source_ids=source_ids,
            filename=filename,
            admin=admin,
        )

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
