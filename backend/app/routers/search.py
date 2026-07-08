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

ARTIST_SEARCH_SELECT = """
        SELECT
            'artist' AS type,
            a.id,
            a.name,
            a.ra_artist_id,
            COALESCE(event_counts.event_count, 0)::int AS event_count,
            COALESCE(genre_rows.genres, ARRAY[]::text[]) AS genres,
            NULLIF(BTRIM(COALESCE(a.biography_normalized, '')), '') AS biography_normalized,
            NULLIF(BTRIM(COALESCE(a.biography, '')), '') IS NOT NULL AS has_biography,
            NULLIF(LEFT(REGEXP_REPLACE(COALESCE(a.biography, ''), E'\\s+', ' ', 'g'), 140), '') AS biography_preview,
            latest_event.latest_event_title,
            latest_event.latest_event_date,
            ts_rank(to_tsvector('simple', a.name), plainto_tsquery('simple', %s)) AS rank,
            ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('simple', a.name), plainto_tsquery('simple', %s)) DESC, a.name ASC) AS rn
        FROM (
            SELECT *
            FROM artists
            WHERE name ILIKE %s
        ) a
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::int AS event_count
            FROM event_artists ea
            WHERE ea.artist_id = a.id
        ) event_counts ON TRUE
        LEFT JOIN LATERAL (
            SELECT (ARRAY_AGG(extracted_genre ORDER BY confidence DESC, extracted_genre ASC))[1:3] AS genres
            FROM artist_extracted_genres
            WHERE artist_id = a.id
        ) genre_rows ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                e.title AS latest_event_title,
                to_char(e.event_date, 'YYYY-MM-DD') AS latest_event_date
            FROM event_artists ea
            JOIN events e
                ON e.id = ea.event_id
            WHERE ea.artist_id = a.id
            ORDER BY e.event_date DESC NULLS LAST, e.id DESC
            LIMIT 1
        ) latest_event ON TRUE
"""

class SearchResult(BaseModel):
    type: str
    id: int
    name: str
    ra_artist_id: str | None = None
    event_count: int | None = None
    genres: List[str] | None = None
    biography_normalized: str | None = None
    has_biography: bool | None = None
    biography_preview: str | None = None
    latest_event_title: str | None = None
    latest_event_date: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]


SEARCH_SQL = """
SELECT type, id, name, ra_artist_id, event_count, genres, biography_normalized, has_biography, biography_preview, latest_event_title, latest_event_date
FROM (
    SELECT type, id, name, ra_artist_id, event_count, genres, biography_normalized, has_biography, biography_preview, latest_event_title, latest_event_date, rank, rn
    FROM (
        {artist_select}
    ) a WHERE rn <= %s

    UNION ALL

    SELECT type, id, name, NULL AS ra_artist_id, NULL::int AS event_count, NULL::text[] AS genres, NULL::text AS biography_normalized, NULL::boolean AS has_biography, NULL::text AS biography_preview, NULL::text AS latest_event_title, NULL::text AS latest_event_date, rank, rn
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

    SELECT type, id, name, NULL AS ra_artist_id, NULL::int AS event_count, NULL::text[] AS genres, NULL::text AS biography_normalized, NULL::boolean AS has_biography, NULL::text AS biography_preview, NULL::text AS latest_event_title, NULL::text AS latest_event_date, rank, rn
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

    SELECT type, id, name, NULL AS ra_artist_id, NULL::int AS event_count, NULL::text[] AS genres, NULL::text AS biography_normalized, NULL::boolean AS has_biography, NULL::text AS biography_preview, NULL::text AS latest_event_title, NULL::text AS latest_event_date, rank, rn
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
""".format(artist_select=ARTIST_SEARCH_SELECT)

SEARCH_BY_TYPE_SQL = {
    "artist": """
        SELECT type, id, name, ra_artist_id, event_count, genres, biography_normalized, has_biography, biography_preview, latest_event_title, latest_event_date
        FROM (
            {artist_select}
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
                sql = SEARCH_BY_TYPE_SQL[entity_type].format(
                    artist_select=ARTIST_SEARCH_SELECT,
                    order_by=SORT_ORDER_BY[sort],
                )
                if entity_type == "artist":
                    cur.execute(sql, (q, q, pattern, limit))
                else:
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
        SearchResult(
            type=row["type"],
            id=row["id"],
            name=row["name"],
            ra_artist_id=row.get("ra_artist_id"),
            event_count=row.get("event_count"),
            genres=row.get("genres"),
            biography_normalized=row.get("biography_normalized"),
            has_biography=row.get("has_biography"),
            biography_preview=row.get("biography_preview"),
            latest_event_title=row.get("latest_event_title"),
            latest_event_date=row.get("latest_event_date"),
        )
        for row in rows
    ]

    return SearchResponse(query=q, results=results)
