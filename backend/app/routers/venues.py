from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg import Connection
from app.db import get_db

router = APIRouter()


class EventSummary(BaseModel):
    id: str
    title: str
    date: Optional[str]
    artists: List[str]
    promoters: List[str]


class VenueResponse(BaseModel):
    type: str
    id: str
    name: str
    address: Optional[str]
    district: Optional[str]
    event_count: int
    events: List[EventSummary]


VENUE_SQL = """
SELECT id, name, address, area_name
FROM venues
WHERE id = %s;
"""

VENUE_EVENTS_SQL = """
SELECT
    e.id                                                        AS event_id,
    e.title,
    e.event_date::text                                          AS date,
    COALESCE(
        array_agg(DISTINCT a.name) FILTER (WHERE a.name IS NOT NULL),
        ARRAY[]::text[]
    )                                                           AS artists,
    COALESCE(
        array_agg(DISTINCT p.name) FILTER (WHERE p.name IS NOT NULL),
        ARRAY[]::text[]
    )                                                           AS promoters
FROM events e
LEFT JOIN event_artists  ea ON ea.event_id = e.id
LEFT JOIN artists         a ON a.id = ea.artist_id
LEFT JOIN event_promoters ep ON ep.event_id = e.id
LEFT JOIN promoters       p ON p.id = ep.promoter_id
WHERE e.venue_id = %s
GROUP BY e.id, e.title, e.event_date
ORDER BY e.event_date DESC;
"""


@router.get("", response_model=VenueResponse)
def get_venue(
    id: int = Query(...),
    db: Connection = Depends(get_db),
):
    with db.cursor() as cur:
        cur.execute(VENUE_SQL, (id,))
        venue = cur.fetchone()

    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    with db.cursor() as cur:
        cur.execute(VENUE_EVENTS_SQL, (id,))
        rows = cur.fetchall()

    events = [
        EventSummary(
            id=str(row['event_id']),
            title=row["title"],
            date=row["date"],
            artists=row["artists"],
            promoters=row["promoters"],
        )
        for row in rows
    ]

    return VenueResponse(
        type="venue",
        id=str(venue["id"]),
        name=venue["name"],
        address=venue["address"],
        district=venue["area_name"],
        event_count=len(events),
        events=events,
    )