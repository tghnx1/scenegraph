from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Literal, Optional
from app.db import get_connection

router = APIRouter()

SearchSort = Literal["relevance", "name_asc", "name_desc"]

SORT_ORDER_BY: dict[SearchSort, str] = {
    "relevance": "rank DESC, name ASC",
    "name_asc": "name ASC",
    "name_desc": "name DESC",
}

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

SEARCH_BY_TYPE_SQL = {
    "artist": """
        SELECT type, id, name
        FROM (
            SELECT
                'artist' AS type,
                id,
                name,
                ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank
            FROM artists
            WHERE name ILIKE %s
        ) results
        ORDER BY {order_by}
        LIMIT %s;
    """,
    "venue": """
        SELECT type, id, name
        FROM (
            SELECT
                'venue' AS type,
                id,
                name,
                ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank
            FROM venues
            WHERE name ILIKE %s
        ) results
        ORDER BY {order_by}
        LIMIT %s;
    """,
    "event": """
        SELECT type, id, name
        FROM (
            SELECT
                'event' AS type,
                id,
                title AS name,
                ts_rank(to_tsvector('simple', title), plainto_tsquery('simple', %s)) AS rank
            FROM events
            WHERE title ILIKE %s
        ) results
        ORDER BY {order_by}
        LIMIT %s;
    """,
    "promoter": """
        SELECT type, id, name
        FROM (
            SELECT
                'promoter' AS type,
                id,
                name,
                ts_rank(to_tsvector('simple', name), plainto_tsquery('simple', %s)) AS rank
            FROM promoters
            WHERE name ILIKE %s
        ) results
        ORDER BY {order_by}
        LIMIT %s;
    """,
}

@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=100),
    entity_type: Optional[Literal["artist", "venue", "event", "promoter"]] = Query(None, alias="type"),
    sort: SearchSort = Query("relevance"),
):
    pattern = f"%{q}%"

    with get_connection() as db:
        with db.cursor() as cur:
            if entity_type:
                sql = SEARCH_BY_TYPE_SQL[entity_type].format(order_by=SORT_ORDER_BY[sort])
                cur.execute(sql, (q, pattern, limit))
            else:
                per_type = max(2, limit // 4)
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
