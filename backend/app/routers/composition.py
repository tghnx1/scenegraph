from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from app.main import require_admin
from app.db import get_connection

router = APIRouter()

class CompositionItem(BaseModel):
    id: str
    label: str
    value: int
    percentage: float

class CompositionResponse(BaseModel):
    from_date: Optional[str] = Field(None, alias="from")
    to_date: Optional[str] = Field(None, alias="to")
    total: int
    items: List[CompositionItem]

    class Config:
        populate_by_name = True

PERIOD_SQL = """
SELECT
    MIN(event_date)::date::text AS oldest,
    MAX(event_date)::date::text AS newest
FROM events
WHERE event_date IS NOT NULL;
"""

LABELS: dict[str, str] = {
    "events":    "Events",
    "artists":   "Artists",
    "promoters": "Promoters",
    "venues":    "Venues",
}

COMPOSITION_SQL = """
WITH filtered_events AS (
    SELECT id, venue_id
    FROM events
    WHERE (%s::timestamp IS NULL OR event_date >= %s::timestamp)
      AND (%s::timestamp IS NULL OR event_date <= %s::timestamp)
)
SELECT 'events'    AS entity, COUNT(DISTINCT fe.id)            AS count FROM filtered_events fe
UNION ALL
SELECT 'artists'   AS entity, COUNT(DISTINCT ea.artist_id)     AS count FROM filtered_events fe JOIN event_artists   ea ON ea.event_id = fe.id
UNION ALL
SELECT 'promoters' AS entity, COUNT(DISTINCT ep.promoter_id)   AS count FROM filtered_events fe JOIN event_promoters ep ON ep.event_id = fe.id
UNION ALL
SELECT 'venues'    AS entity, COUNT(DISTINCT fe.venue_id)      AS count FROM filtered_events fe WHERE fe.venue_id IS NOT NULL;
"""

@router.get("/composition", response_model=CompositionResponse)
def get_composition(
    include: str = Query("events,artists,promoters,venues"),
    dateFrom: Optional[str] = Query(None),
    dateTo: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    """Return entity composition while keeping DB checkout scoped to the queries."""
    requested = [t.strip() for t in include.split(",") if t.strip() in LABELS]

    date_from = f"{dateFrom}T00:00:00Z" if dateFrom else None
    date_to   = f"{dateTo}T23:59:59Z"   if dateTo   else None

    with get_connection() as db:
        if not date_from or not date_to:
            with db.cursor() as cur:
                cur.execute(PERIOD_SQL)
                period = cur.fetchone()
            if not date_from:
                date_from = f"{period['oldest']}T00:00:00Z"
            if not date_to:
                date_to = f"{period['newest']}T23:59:59Z"

        with db.cursor() as cur:
            cur.execute(COMPOSITION_SQL, (date_from, date_from, date_to, date_to))
            rows = cur.fetchall()

    all_counts = {row["entity"]: row["count"] for row in rows}

    filtered_counts = {k: all_counts[k] for k in requested if k in all_counts}
    total = sum(filtered_counts.values())

    items = [
        CompositionItem(
            id=entity,
            label=LABELS[entity],
            value=filtered_counts[entity],
            percentage=round(filtered_counts[entity] / total * 100, 2) if total > 0 else 0.0,
        )
        for entity in requested
    ]

    return CompositionResponse(**{
        "from": date_from,
        "to":   date_to,
        "total": total,
        "items": items,
    })
