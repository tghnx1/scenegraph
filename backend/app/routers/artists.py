from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.db import get_connection
from app.auth import get_current_user_id
from app.style_tags import canonicalize_style_tags, suppress_parent_style_tags
from app.text_profiles import normalize_biography_text
from app.recommendations.jobs import create_artist_bio_refresh_job

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
    extracted_tags: dict[str, list[str]]


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

ARTIST_EXTRACTED_TAGS_SQL = """
SELECT
    tag_type,
    tag_value
FROM artist_extracted_tags
WHERE artist_id = %s
  AND tag_type = ANY(%s)
ORDER BY tag_type ASC, confidence DESC, tag_value ASC;
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

def _update_artist_biography_row(
    db,
    *,
    artist_id: int,
    biography: str,
    user_id: int,
    enqueue_refresh_job: bool = True,
) -> dict:
    biography = biography.strip()
    biography_normalized = normalize_biography_text(biography)

    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE artists
            SET biography = %s,
                biography_normalized = %s,
                biography_status = 'manually_edited'
            WHERE id = %s
            RETURNING id, name, biography, biography_normalized;
            """,
            (biography, biography_normalized, artist_id),
        )
        artist = cur.fetchone()

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    if enqueue_refresh_job:
        create_artist_bio_refresh_job(
            db,
            user_id=user_id,
            artist_id=artist_id,
            params={"trigger": "artist_biography_update"},
        )

    return artist


@router.get("/{id}", response_model=ArtistResponse)
def get_artist(
    id: int,
):
    with get_connection() as db:
        with db.cursor() as cur:
            cur.execute(ARTIST_SQL, (id,))
            artist = cur.fetchone()

        if not artist:
            raise HTTPException(status_code=404, detail="Use the search engine above for Artist profiles. Double click an Artist icon on the upper-right graph")

        biography = artist.get("biography_normalized") or artist.get("biography") or ""

        with db.cursor() as cur:
            cur.execute(ARTIST_EVENTS_SQL, (id,))
            events_rows = cur.fetchall()

        with db.cursor() as cur:
            cur.execute(CONNECTED_ARTISTS_SQL, (id,))
            connected_rows = cur.fetchall()

        with db.cursor() as cur:
            cur.execute("SELECT to_regclass('public.artist_extracted_tags') AS table_name")
            has_artist_extracted_tags = cur.fetchone()["table_name"] is not None
            extracted_tags: dict[str, list[str]] = {}
            if has_artist_extracted_tags:
                cur.execute(
                    ARTIST_EXTRACTED_TAGS_SQL,
                    (id, ["style", "label", "collective", "role", "residency", "alias"]),
                )
                seen_tag_values: dict[str, set[str]] = {}
                style_tags: list[str] = []
                for row in cur.fetchall():
                    tag_type = row["tag_type"]
                    tag_value = str(row["tag_value"]).strip()
                    if not tag_value:
                        continue
                    if tag_type == "style":
                        style_tags.extend(canonicalize_style_tags(tag_value))
                        continue
                    values = extracted_tags.setdefault(tag_type, [])
                    seen_values = seen_tag_values.setdefault(tag_type, set())
                    normalized_value = tag_value.casefold()
                    if normalized_value not in seen_values:
                        values.append(tag_value)
                        seen_values.add(normalized_value)

                if style_tags:
                    extracted_tags["style"] = [
                        present_style_label(tag)
                        for tag in suppress_parent_style_tags(style_tags)
                    ]

    genres: list[str] = []

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
        extracted_tags=extracted_tags,
    )


@router.patch("/{id}/biography", response_model=ArtistBiographyResponse)
async def update_artist_biography(
    id: int,
    request: ArtistBiographyUpdate,
    current_user_id: dict = Depends(get_current_user_id),
):
    with get_connection() as db:
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

        artist = _update_artist_biography_row(
            db,
            artist_id=id,
            biography=request.biography,
            user_id=current_user_id,
            enqueue_refresh_job=True,
        )

    return ArtistBiographyResponse(
        id=artist["id"],
        name=artist["name"],
        biography=artist["biography"] or "",
    )
    
