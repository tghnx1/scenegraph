from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg import Connection
from app.db import get_db

router = APIRouter()

class SearchResult(BaseModel):
    type: str
    id: int
    name: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]


SEARCH_SQL = """
SELECT type, id, name
FROM (
    SELECT
        'artist'  AS type,
        id,
        name,
        ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank
    FROM artists
    WHERE name ILIKE %s

    UNION ALL

    SELECT
        'venue'   AS type,
        id,
        name,
        ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank
    FROM venues
    WHERE name ILIKE %s

    UNION ALL

    SELECT
        'event'   AS type,
        id,
        title     AS name,
        ts_rank(to_tsvector('simple', title), plainto_tsquery('simple', %s)) AS rank
    FROM events
    WHERE title ILIKE %s

    UNION ALL

    SELECT
        'promoter' AS type,
        id,
        name,
        ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank
    FROM promoters
    WHERE name ILIKE %s
) results
ORDER BY rank DESC, name ASC
LIMIT %s;
"""


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=50),
    db: Connection = Depends(get_db),
):
    pattern = f"%{q}%"

    with db.cursor() as cur:
        cur.execute(SEARCH_SQL, (q, pattern, q, pattern, q, pattern, q, pattern, limit))
        rows = cur.fetchall()

    results = [
        SearchResult(type=row["type"], id=row["id"], name=row["name"])
        for row in rows
    ]

    return SearchResponse(query=q, results=results)