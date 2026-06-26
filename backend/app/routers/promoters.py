from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.db import get_connection

router = APIRouter()


class EventSummary(BaseModel):
    id: str
    title: str
    date: Optional[str]
    venue_name: Optional[str]
    artists: List[str]
    promoters: List[str]


class PromoterResponse(BaseModel):
    type: str
    id: str
    name: str
    event_count: int
    events: List[EventSummary]


PROMOTER_SQL = """
SELECT id, name
FROM promoters
WHERE id = %s;
"""

PROMOTER_EVENTS_SQL = """
SELECT
    e.id                                                            AS event_id,
    e.title,
    e.event_date::text                                              AS date,
    v.name                                                          AS venue_name,
    COALESCE(
        array_agg(DISTINCT a.name) FILTER (WHERE a.name IS NOT NULL),
        ARRAY[]::text[]
    )                                                               AS artists,
    COALESCE(
        array_agg(DISTINCT p.name) FILTER (WHERE p.name IS NOT NULL),
        ARRAY[]::text[]
    )                                                               AS promoters
FROM event_promoters ep
JOIN events e          ON e.id = ep.event_id
LEFT JOIN venues v     ON v.id = e.venue_id
LEFT JOIN event_artists ea  ON ea.event_id = e.id
LEFT JOIN artists a         ON a.id = ea.artist_id
LEFT JOIN event_promoters ep2 ON ep2.event_id = e.id
LEFT JOIN promoters p        ON p.id = ep2.promoter_id
WHERE ep.promoter_id = %s
GROUP BY e.id, e.title, e.event_date, v.name
ORDER BY e.event_date DESC;
"""


@router.get("/{id}", response_model=PromoterResponse)
def get_promoter(
    id: int,
):
    with get_connection() as db:
        with db.cursor() as cur:
            cur.execute(PROMOTER_SQL, (id,))
            promoter = cur.fetchone()

        if not promoter:
            raise HTTPException(status_code=404, detail="Promoter not found")

        with db.cursor() as cur:
            cur.execute(PROMOTER_EVENTS_SQL, (id,))
            rows = cur.fetchall()

    events = [
        EventSummary(
            id=str(row["event_id"]),
            title=row["title"],
            date=row["date"],
            venue_name=row["venue_name"],
            artists=row["artists"],
            promoters=row["promoters"],
        )
        for row in rows
    ]

    return PromoterResponse(
        type="promoter",
        id=str(promoter["id"]),
        name=promoter["name"],
        event_count=len(events),
        events=events,
    )
