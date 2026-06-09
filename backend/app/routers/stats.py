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


STATS_SQL = """
SELECT
    (SELECT COUNT(*) FROM events)    AS events,
    (SELECT COUNT(*) FROM artists)   AS artists,
    (SELECT COUNT(*) FROM venues)    AS venues,
    (SELECT COUNT(*) FROM promoters) AS promoters,
    (SELECT COUNT(*) FROM genres)    AS genres,
    (SELECT COUNT(*) FROM artists WHERE biography IS NULL OR biography = '') AS artists_no_bio;
"""

@router.get("", response_model=StatsResponse)
def get_stats(db: Connection = Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(STATS_SQL)
        row = cur.fetchone()

    return StatsResponse(
        events=row["events"],
        artists=row["artists"],
        venues=row["venues"],
        promoters=row["promoters"],
        genres=row["genres"],
        artists_no_bio=row["artists_no_bio"],
    )
