from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg import Connection
from app.db import get_db

router = APIRouter()


class EventSummary(BaseModel):
    id: int
    title: str
    event_date: Optional[str]
    venue_name: Optional[str]


class ConnectedArtist(BaseModel):
    id: int
    name: str
    shared_events: int


class ArtistResponse(BaseModel):
    type: str
    id: int
    name: str
    genres: List[str]
    bio: Optional[str]
    event_count: int
    events: List[EventSummary]
    connected_artists: List[ConnectedArtist]


ARTIST_SQL = """
SELECT
    a.id,
    a.name,
    a.biography
FROM artists a
WHERE a.id = %s;
"""

ARTIST_GENRES_SQL = """
SELECT DISTINCT g.name
FROM event_artists ea
JOIN event_genres eg ON eg.event_id = ea.event_id
JOIN genres g        ON g.id = eg.genre_id
WHERE ea.artist_id = %s
ORDER BY g.name;
"""

ARTIST_EVENTS_SQL = """
SELECT
    e.id,
    e.title,
    e.event_date::text,
    v.name AS venue_name
FROM event_artists ea
JOIN events  e ON e.id = ea.event_id
LEFT JOIN venues v ON v.id = e.venue_id
WHERE ea.artist_id = %s
ORDER BY e.event_date DESC;
"""

CONNECTED_ARTISTS_SQL = """
SELECT
    a.id,
    a.name,
    COUNT(*) AS shared_events
FROM event_artists ea1
JOIN event_artists ea2 ON ea2.event_id = ea1.event_id AND ea2.artist_id != ea1.artist_id
JOIN artists a         ON a.id = ea2.artist_id
WHERE ea1.artist_id = %s
GROUP BY a.id, a.name
ORDER BY shared_events DESC
LIMIT 10;
"""


@router.get("", response_model=ArtistResponse)
def get_artist(
    id: int = Query(...),
    db: Connection = Depends(get_db),
):
    with db.cursor() as cur:
        cur.execute(ARTIST_SQL, (id,))
        artist = cur.fetchone()

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    with db.cursor() as cur:
        cur.execute(ARTIST_GENRES_SQL, (id,))
        genres = [row["name"] for row in cur.fetchall()]

    with db.cursor() as cur:
        cur.execute(ARTIST_EVENTS_SQL, (id,))
        events_rows = cur.fetchall()

    with db.cursor() as cur:
        cur.execute(CONNECTED_ARTISTS_SQL, (id,))
        connected_rows = cur.fetchall()

    events = [
        EventSummary(
            id=row["id"],
            title=row["title"],
            event_date=row["event_date"],
            venue_name=row["venue_name"],
        )
        for row in events_rows
    ]

    connected_artists = [
        ConnectedArtist(
            id=row["id"],
            name=row["name"],
            shared_events=row["shared_events"],
        )
        for row in connected_rows
    ]

    return ArtistResponse(
        type="artist",
        id=artist["id"],
        name=artist["name"],
        genres=genres,
        bio=artist["biography"],
        event_count=len(events),
        events=events,
        connected_artists=connected_artists,
    )
    