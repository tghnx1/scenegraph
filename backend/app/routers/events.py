from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg import Connection
from app.db import get_db

router = APIRouter()


class VenueSummary(BaseModel):
    id: str
    name: str


class ArtistSummary(BaseModel):
    id: str
    name: str


class PromoterSummary(BaseModel):
    id: str
    name: str


class EventResponse(BaseModel):
    type: str
    id: str
    title: str
    date: Optional[str]
    venue: Optional[VenueSummary]
    artists: List[ArtistSummary]
    promoters: List[PromoterSummary]


EVENT_SQL = """
SELECT
    e.id,
    e.title,
    e.event_date::text      AS date,
    v.id                    AS venue_id,
    v.name                  AS venue_name
FROM events e
LEFT JOIN venues v ON v.id = e.venue_id
WHERE e.id = %s;
"""

EVENT_ARTISTS_SQL = """
SELECT a.id, a.name
FROM event_artists ea
JOIN artists a ON a.id = ea.artist_id
WHERE ea.event_id = %s
ORDER BY a.name ASC;
"""

EVENT_PROMOTERS_SQL = """
SELECT p.id, p.name
FROM event_promoters ep
JOIN promoters p ON p.id = ep.promoter_id
WHERE ep.event_id = %s
ORDER BY p.name ASC;
"""


@router.get("/{id}", response_model=EventResponse)
def get_event(
    id: int,
    db: Connection = Depends(get_db),
):
    with db.cursor() as cur:
        cur.execute(EVENT_SQL, (id,))
        event = cur.fetchone()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    with db.cursor() as cur:
        cur.execute(EVENT_ARTISTS_SQL, (id,))
        artists = cur.fetchall()

    with db.cursor() as cur:
        cur.execute(EVENT_PROMOTERS_SQL, (id,))
        promoters = cur.fetchall()

    return EventResponse(
        type="event",
        id=str(event["id"]),
        title=event["title"],
        date=event["date"],
        venue=VenueSummary(
            id=str(event["venue_id"]),
            name=event["venue_name"],
        ) if event["venue_id"] else None,
        artists=[
            ArtistSummary(id=str(a["id"]), name=a["name"])
            for a in artists
        ],
        promoters=[
            PromoterSummary(id=str(p["id"]), name=p["name"])
            for p in promoters
        ],
    )