from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.auth import require_admin
from app.db import get_db
from psycopg import Connection
from .metrics_integrity import get_integrity, IntegrityItem
from .metrics_rankings import get_rankings, TopList

router = APIRouter()

class MetricsResponse(BaseModel):
    latest_source_payload: Optional[str] = None
    metrics: List[IntegrityItem]
    rankings: List[TopList]

@router.get("/metrics", response_model=MetricsResponse)
def get_dashboard(
    admin: dict = Depends(require_admin),
    db: Connection = Depends(get_db),
):

    integrities = get_integrity(db)
    rankings = get_rankings(db)

    return {
        "latest_source_payload": integrities.latest_source_payload if integrities else [],
        "metrics": integrities.integrity_lists if integrities else [],
        "rankings": rankings.top_lists if rankings else []
    }
