from fastapi import APIRouter, Depends
from pydantic import BaseModel
from psycopg import Connection
from app.db import get_db

router = APIRouter()


class StatsResponse(BaseModel):
    events: int
    artists: int
    venues: int
    promoters: int
    genres: int
    artists_no_bio: int
    artists_no_genre: int
    avg_artists_per_event: float
    avg_events_per_promoter: float
    missing_nodes_links: int
    complete_connections: int


STATS_SQL = """
SELECT
    (SELECT COUNT(*) FROM events)    AS events,
    (SELECT COUNT(*) FROM artists)   AS artists,
    (SELECT COUNT(*) FROM venues)    AS venues,
    (SELECT COUNT(*) FROM promoters) AS promoters,
    (SELECT COUNT(*) FROM genres)    AS genres,
    (SELECT COUNT(*) FROM artists WHERE biography IS NULL OR biography = '') AS artists_no_bio,
    (SELECT COUNT(*) FROM artists WHERE id NOT IN (SELECT DISTINCT artist_id FROM artist_extracted_genres WHERE artist_id IS NOT NULL)) AS artists_no_genre,
    (SELECT COUNT(*) FROM event_artists) AS total_event_relations,
    (SELECT COUNT(*) FROM event_promoters) AS total_promoter_relations,

    (SELECT COUNT(*) FROM artists a
     WHERE NOT EXISTS (
         SELECT 1 FROM event_artists ea WHERE ea.artist_id = a.id
     )) AS artists_without_events,

    (SELECT COUNT(*) FROM events e
     WHERE e.venue_id IS NULL
    ) AS events_without_venue,

    (SELECT COUNT(*) FROM events e
     WHERE NOT EXISTS (
         SELECT 1 FROM event_artists ea WHERE ea.event_id = e.id
     )) AS events_without_artists,

    (SELECT COUNT(*) FROM artists a
     WHERE NOT EXISTS (
         SELECT 1 FROM artist_extracted_tags t WHERE t.artist_id = a.id
     )) AS artists_without_tags,

    ---Artists who have at least one event
    (SELECT COUNT(*) 
        FROM artists a
        WHERE EXISTS (SELECT 1 FROM event_artists ea WHERE ea.artist_id = a.id)
    ) AS artists_with_complete_networks,

    ---Events that have a location and at least 1 artist
    (SELECT COUNT(*)
        FROM events e
        WHERE e.venue_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM event_artists ea WHERE ea.event_id = e.id)
    ) AS events_with_complete_networks;

"""

GENRE_STATS_SQL = """

"""

@router.get("", response_model=StatsResponse)
def get_stats(db: Connection = Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(STATS_SQL)
        row = cur.fetchone()

    total_events = row["events"]
    total_promoters = row["promoters"]
    total_networks_broken = row["events_without_venue"] + row["events_without_artists"] + row["artists_without_events"] + row["artists_without_tags"]
    total_networks_complete = row["artists_with_complete_networks"] + row["events_with_complete_networks"]

    return StatsResponse(
        events=total_events,
        artists=row["artists"],
        venues=row["venues"],
        promoters=total_promoters,
        genres=row["genres"],
        artists_no_bio=row["artists_no_bio"],
        artists_no_genre=row["artists_no_genre"],
        avg_artists_per_event=round(row["total_event_relations"] / total_events, 2) if total_events > 0 else 0.0,
        avg_events_per_promoter=round(row["total_promoter_relations"] / total_promoters, 2) if total_promoters > 0 else 0.0,
        complete_connections=total_networks_complete,
        missing_nodes_links=total_networks_broken,
    )
