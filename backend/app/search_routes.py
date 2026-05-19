from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List
from psycopg import Connection
from app.db import get_db

router = APIRouter()

class SearchResultItem(BaseModel):
    type: str
    id: str
    name: str

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

@router.get("/api/search", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(8, ge=1, le=50),
    connection: Connection = Depends(get_db)
):
    search_pattern = f"%{q}%"
    combined_results = []

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ra_artist_id, name FROM artists WHERE name ILIKE %s LIMIT %s",
            (search_pattern, limit)
        )
        for row in cursor.fetchall():
            combined_results.append({
                "type": "artist",
                "id": f"artist-{row['ra_artist_id']}",
                "name": row['name']
            })

        cursor.execute(
            "SELECT ra_venue_id, name FROM venues WHERE name ILIKE %s LIMIT %s",
            (search_pattern, limit)
        )
        for row in cursor.fetchall():
            combined_results.append({
                "type": "venue",
                "id": f"venue-{row['ra_venue_id']}",
                "name": row['name']
            })

        cursor.execute(
            "SELECT ra_promoter_id, name FROM promoters WHERE name ILIKE %s LIMIT %s",
            (search_pattern, limit)
        )
        for row in cursor.fetchall():
            combined_results.append({
                "type": "promoter",
                "id": f"promoter-{row['ra_promoter_id']}",
                "name": row['name']
            })

        cursor.execute(
            "SELECT ra_event_id, title FROM events WHERE title ILIKE %s LIMIT %s",
            (search_pattern, limit)
        )
        for row in cursor.fetchall():
            combined_results.append({
                "type": "event",
                "id": f"event-{row['ra_event_id']}",
                "name": row['title']
            })

    return {
        "query": q,
        "results": combined_results[:limit]
    }