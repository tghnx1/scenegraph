from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.admin.metrics import get_cached_metrics_payload
from app.auth import require_admin
from app.db import get_connection
from .metrics_integrity import IntegrityItem
from .metrics_rankings import TopList

router = APIRouter()


class MetricsResponse(BaseModel):
    latest_source_payload: Optional[str] = None
    metrics: List[IntegrityItem]
    rankings: List[TopList]


@router.get("/metrics", response_model=MetricsResponse)
def get_dashboard(admin: dict = Depends(require_admin)):
    return get_cached_metrics_payload(get_connection)
