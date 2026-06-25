from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg import Connection
from app.db import get_db
from app.style_tags import canonicalize_style_tags, extract_style_tags
from app.auth import get_current_user_id

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


class ArtistBiographyUpdate(BaseModel):
    biography: str


class ArtistBiographyResponse(BaseModel):
    id: int
    name: str
    biography: str


ARTIST_SQL = """
SELECT
    a.id,
    a.name,
    a.biography_normalized,
    a.biography
FROM artists a
WHERE a.id = %s;
"""

ARTIST_STYLE_TAGS_SQL = """
SELECT
    extracted_genre,
    MAX(confidence) AS confidence
FROM artist_extracted_genres
WHERE artist_id = %s
  AND confidence >= 0.6
GROUP BY extracted_genre
ORDER BY confidence DESC, extracted_genre ASC;
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

STYLE_LABEL_OVERRIDES = {
    "ebm": "EBM",
    "idm": "IDM",
    "r&b": "R&B",
    "hi-nrg": "Hi-NRG",
    "uk garage": "UK Garage",
    "uk bass": "UK Bass",
    "drum and bass": "Drum & Bass",
}

STYLE_TOKEN_OVERRIDES = {
    "uk": "UK",
    "dj": "DJ",
}


def present_style_label(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        return ""

    lowered = normalized.lower()
    if lowered in STYLE_LABEL_OVERRIDES:
        return STYLE_LABEL_OVERRIDES[lowered]

    def format_token(token: str) -> str:
        token_lower = token.lower()
        if token_lower in STYLE_TOKEN_OVERRIDES:
            return STYLE_TOKEN_OVERRIDES[token_lower]
        if "-" in token_lower:
            return "-".join(format_token(part) for part in token_lower.split("-"))
        return token_lower.capitalize()

    return " ".join(format_token(token) for token in lowered.split(" "))


@router.get("/{id}", response_model=ArtistResponse)
def get_artist(
    id: int,
    db: Connection = Depends(get_db),
):
    with db.cursor() as cur:
        cur.execute(ARTIST_SQL, (id,))
        artist = cur.fetchone()

    if not artist:
        raise HTTPException(status_code=404, detail="Use the search engine above for Artist profiles. Double click an Artist icon on the upper-right graph")

    biography = artist.get("biography_normalized") or artist.get("biography") or ""
    profile_style_tags: list[str] = []
    with db.cursor() as cur:
        cur.execute("SELECT to_regclass('public.artist_extracted_genres') AS table_name")
        has_artist_extracted_genres = cur.fetchone()["table_name"] is not None
        if has_artist_extracted_genres:
            cur.execute(ARTIST_STYLE_TAGS_SQL, (id,))
            profile_style_tags = sorted(
                {
                    canonical
                    for row in cur.fetchall()
                    for canonical in canonicalize_style_tags(row["extracted_genre"])
                }
            )

    if not profile_style_tags:
        profile_style_tags = extract_style_tags(biography)

    genres = sorted(
        {
            present_style_label(tag)
            for tag in profile_style_tags
            if isinstance(tag, str) and tag.strip()
        }
    )

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
        bio=biography,
        event_count=len(events),
        events=events,
        connected_artists=connected_artists,
    )


@router.patch("/{id}/biography", response_model=ArtistBiographyResponse)
async def update_artist_biography(
    id: int,
    request: ArtistBiographyUpdate,
    db: Connection = Depends(get_db),
    current_user_id: dict = Depends(get_current_user_id),
):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT role, artist_id
            FROM users
            WHERE id = %s
            """,
            (current_user_id,)
        )
        user_row = cur.fetchone()

    if not user_row:
        raise HTTPException(status_code=403, detail="User not found")
    
    if user_row["role"] != "admin" and user_row["artist_id"] != id:
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own artist profile"
        )
    
    biography = request.biography.strip()
    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE artists
            SET biography = %s,
                biography_status = 'manually_edited'
            WHERE id = %s
            RETURNING id, name, biography;
            """,
            (biography, id),
        )
        artist = cur.fetchone()

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    return ArtistBiographyResponse(
        id=artist["id"],
        name=artist["name"],
        biography=artist["biography"] or "",
    )
    
