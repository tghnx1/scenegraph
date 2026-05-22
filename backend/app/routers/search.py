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
    SELECT type, id, name, rank, rn
    FROM (
        SELECT
            'artist'  AS type,
            id,
            name,
            ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank,
            ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) DESC, name ASC) AS rn
        FROM artists
        WHERE name ILIKE %s
    ) a WHERE rn <= %s

    UNION ALL

    SELECT type, id, name, rank, rn
    FROM (
        SELECT
            'venue'   AS type,
            id,
            name,
            ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank,
            ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) DESC, name ASC) AS rn
        FROM venues
        WHERE name ILIKE %s
    ) v WHERE rn <= %s

    UNION ALL

    SELECT type, id, name, rank, rn
    FROM (
        SELECT
            'event'   AS type,
            id,
            title     AS name,
            ts_rank(to_tsvector('simple', title), plainto_tsquery('simple', %s)) AS rank,
            ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('simple', title), plainto_tsquery('simple', %s)) DESC, title ASC) AS rn
        FROM events
        WHERE title ILIKE %s
    ) e WHERE rn <= %s

    UNION ALL

    SELECT type, id, name, rank, rn
    FROM (
        SELECT
            'promoter' AS type,
            id,
            name,
            ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank,
            ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) DESC, name ASC) AS rn
        FROM promoters
        WHERE name ILIKE %s
    ) p WHERE rn <= %s
) results
ORDER BY rank DESC, name ASC;
"""

@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=50),
    db: Connection = Depends(get_db),
):
    pattern = f"%{q}%"
    per_type = max(2, limit // 4)

    with db.cursor() as cur:
        cur.execute(SEARCH_SQL, (
            q, q, pattern, per_type,
            q, q, pattern, per_type,
            q, q, pattern, per_type,
            q, q, pattern, per_type,
        ))
        rows = cur.fetchall()

    results = [
        SearchResult(type=row["type"], id=row["id"], name=row["name"])
        for row in rows
    ]

    return SearchResponse(query=q, results=results)