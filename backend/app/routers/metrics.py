import os
import threading
from time import monotonic

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.main import require_admin
from app.db import get_connection
from .metrics_integrity import get_integrity, IntegrityItem
from .metrics_rankings import get_rankings, TopList

router = APIRouter()
ADMIN_METRICS_CACHE_TTL_SECONDS = float(os.getenv("ADMIN_METRICS_CACHE_TTL_SECONDS", "15"))
_metrics_cache_lock = threading.Lock()
_metrics_cache: tuple[float, dict] | None = None

class MetricsResponse(BaseModel):
    latest_source_payload: Optional[str] = None
    metrics: List[IntegrityItem]
    rankings: List[TopList]

@router.get("/metrics", response_model=MetricsResponse)
def get_dashboard(
    admin: dict = Depends(require_admin),
):
    """Return dashboard metrics, reusing a short cache to avoid repeated full-dataset scans."""
    global _metrics_cache

    if ADMIN_METRICS_CACHE_TTL_SECONDS > 0:
        with _metrics_cache_lock:
            if _metrics_cache is not None:
                cached_at, cached_payload = _metrics_cache
                if monotonic() - cached_at < ADMIN_METRICS_CACHE_TTL_SECONDS:
                    return cached_payload

            with get_connection() as db:
                integrities = get_integrity(db)
                rankings = get_rankings(db)

            payload = {
                "latest_source_payload": integrities.latest_source_payload if integrities else [],
                "metrics": integrities.integrity_lists if integrities else [],
                "rankings": rankings.top_lists if rankings else []
            }
            _metrics_cache = (monotonic(), payload)
            return payload

    with get_connection() as db:
        integrities = get_integrity(db)
        rankings = get_rankings(db)

    payload = {
        "latest_source_payload": integrities.latest_source_payload if integrities else [],
        "metrics": integrities.integrity_lists if integrities else [],
        "rankings": rankings.top_lists if rankings else []
    }

    return payload
