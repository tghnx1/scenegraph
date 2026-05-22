from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg import Connection
from app.db import get_db


router = APIRouter()

# global search
class SearchResultItem(BaseModel):
    type: str
    id: str
    name: str

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

@router.get("/search", response_model=SearchResponse)
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

#artist detail
class ArtistEventItem(BaseModel):
    id: str
    title: str
    date: str
    venue_name: str

class ConnectedArtistItem(BaseModel):
    id: str
    name: str
    shared_events_count: int

class ArtistDetailResponse(BaseModel):
    type: str = "artist"
    id: str
    name: str
    genres: List[str]
    bio: Optional[str] = None
    eventCount: int
    events: List[ArtistEventItem]
    connectedArtists: List[ConnectedArtistItem]

@router.get("/artist", response_model=ArtistDetailResponse)
async def get_artist_detail(
    id: str = Query(..., description="ra_artist_id"),
    connection: Connection = Depends(get_db)
):
    ra_id = id

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, biography FROM artists WHERE ra_artist_id = %s",
            (ra_id,)
        )
        artist_row = cursor.fetchone()
        
        if not artist_row:
            raise HTTPException(status_code=404, detail="Artist not found.")

        internal_artist_id = artist_row["id"] 

        cursor.execute(
            """
            SELECT DISTINCT g.name 
            FROM event_artists ea
            JOIN event_genres eg ON eg.event_id = ea.event_id
            JOIN genres g ON g.id = eg.genre_id
            WHERE ea.artist_id = %s
            ORDER BY g.name ASC
            """,
            (internal_artist_id,)
        )
        genres = [row["name"] for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT e.ra_event_id, e.title, e.event_date::text, v.name as venue_name
            FROM event_artists ea
            JOIN events e ON e.id = ea.event_id
            LEFT JOIN venues v ON v.id = e.venue_id
            WHERE ea.artist_id = %s
            ORDER BY e.event_date DESC
            """,
            (internal_artist_id,)
        )
        events_rows = cursor.fetchall()
        
        events_list = [
            {
                "id": row['ra_event_id'],
                "title": row["title"],
                "date": row["event_date"],
                "venue_name": row["venue_name"] or "Secret Venue"
            }
            for row in events_rows
        ]

        cursor.execute(
            """
            SELECT a.ra_artist_id, a.name, COUNT(ea2.event_id) as shared_count
            FROM event_artists ea1
            JOIN event_artists ea2 ON ea1.event_id = ea2.event_id AND ea1.artist_id != ea2.artist_id
            JOIN artists a ON a.id = ea2.artist_id
            WHERE ea1.artist_id = %s
            GROUP BY a.ra_artist_id, a.name
            ORDER BY shared_count DESC, a.name ASC
            LIMIT 10
            """,
            (internal_artist_id,)
        )
        connected_rows = cursor.fetchall()
        
        connected_artists = [
            {
                "id": row["ra_artist_id"],
                "name": row["name"],
                "shared_events_count": row["shared_count"]
            }
            for row in connected_rows
        ]

    return {
        "type": "artist",
        "id": id,
        "name": artist_row["name"],
        "genres": genres,
        "bio": artist_row["biography"],
        "eventCount": len(events_list),
        "events": events_list,
        "connectedArtists": connected_artists
    }
