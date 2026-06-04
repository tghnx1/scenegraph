from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from psycopg import Connection
from app.db import get_db

router = APIRouter()


# ─── Models ───────────────────────────────────────────────────────────────────

class ExtractedTag(BaseModel):
    tag_type: str
    tag_value: str
    confidence: float


class ArtistNode(BaseModel):
    id: str
    type: str
    name: str
    genres: List[str] = []
    tags: List[ExtractedTag] = []


class VenueNode(BaseModel):
    id: str
    type: str
    name: str


class EventNode(BaseModel):
    id: str
    type: str
    title: str
    genres: List[str] = []
    tags: List[ExtractedTag] = []
    date: Optional[str] = None


class PromoterNode(BaseModel):
    id: str
    type: str
    name: str


class GraphLinkWeighted(BaseModel):
    source: str
    target: str
    weight: int = 1
    relationship: str


class GraphLink(BaseModel):
    source: str
    target: str
    relationship: str


class ArtistGraphResponse(BaseModel):
    centerNodeId: str
    nodes: list
    links: List[GraphLinkWeighted]


class GraphResponse(BaseModel):
    centerNodeId: str
    nodes: list
    links: List[GraphLink]


# ─── Queries ──────────────────────────────────────────────────────────────────

ARTIST_INFO_SQL = """
SELECT a.id, a.name,
    COALESCE(
        array_agg(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL),
        ARRAY[]::text[]
    ) AS genres
FROM artists a
LEFT JOIN event_artists ea ON ea.artist_id = a.id
LEFT JOIN event_genres eg  ON eg.event_id = ea.event_id
LEFT JOIN genres g         ON g.id = eg.genre_id
WHERE a.id = %s
GROUP BY a.id, a.name;
"""

ARTIST_TAGS_SQL = """
SELECT tag_type, tag_value, confidence
FROM artist_extracted_tags
WHERE artist_id = %s
ORDER BY confidence DESC;
"""

ARTIST_MANUAL_CONNECTIONS_SQL = """
SELECT amc.connected_artist_id AS artist_id, a.name
FROM artist_manual_connections amc
JOIN artists a ON a.id = amc.connected_artist_id
WHERE amc.source_artist_id = %s
UNION
SELECT amc.source_artist_id AS artist_id, a.name
FROM artist_manual_connections amc
JOIN artists a ON a.id = amc.source_artist_id
WHERE amc.connected_artist_id = %s;
"""

ARTIST_EVENTS_SQL = """
SELECT
    e.id        AS event_id,
    e.title,
    e.event_date::date::text AS date,
    v.id        AS venue_id,
    v.name      AS venue_name,
    COALESCE(
        array_agg(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL),
        ARRAY[]::text[]
    ) AS genres
FROM event_artists ea
JOIN events e      ON e.id = ea.event_id
LEFT JOIN venues v ON v.id = e.venue_id
LEFT JOIN event_genres eg ON eg.event_id = e.id
LEFT JOIN genres g        ON g.id = eg.genre_id
WHERE ea.artist_id = %s
GROUP BY e.id, e.title, e.event_date, v.id, v.name
ORDER BY e.event_date DESC
LIMIT %s;
"""

EVENT_TAGS_SQL = """
SELECT tag_type, tag_value, confidence
FROM event_extracted_tags
WHERE event_id = %s
ORDER BY confidence DESC;
"""

VENUE_INFO_SQL = """
SELECT id, name FROM venues WHERE id = %s;
"""

VENUE_EVENTS_SQL = """
SELECT
    e.id        AS event_id,
    e.title,
    e.event_date::date::text AS date,
    COALESCE(
        array_agg(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL),
        ARRAY[]::text[]
    ) AS genres
FROM events e
LEFT JOIN event_genres eg ON eg.event_id = e.id
LEFT JOIN genres g        ON g.id = eg.genre_id
WHERE e.venue_id = %s
GROUP BY e.id, e.title, e.event_date
ORDER BY e.event_date DESC
LIMIT %s;
"""

EVENT_INFO_SQL = """
SELECT
    e.id, e.title, e.event_date::date::text AS date,
    v.id   AS venue_id,
    v.name AS venue_name,
    COALESCE(
        array_agg(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL),
        ARRAY[]::text[]
    ) AS genres
FROM events e
LEFT JOIN venues v        ON v.id = e.venue_id
LEFT JOIN event_genres eg ON eg.event_id = e.id
LEFT JOIN genres g        ON g.id = eg.genre_id
WHERE e.id = %s
GROUP BY e.id, e.title, e.event_date, v.id, v.name;
"""

EVENT_ARTISTS_SQL = """
SELECT a.id, a.name
FROM event_artists ea
JOIN artists a ON a.id = ea.artist_id
WHERE ea.event_id = %s
ORDER BY a.name ASC;
"""

PROMOTER_INFO_SQL = """
SELECT id, name FROM promoters WHERE id = %s;
"""

PROMOTER_EVENTS_SQL = """
SELECT
    e.id        AS event_id,
    e.title,
    e.event_date::date::text AS date,
    v.id        AS venue_id,
    v.name      AS venue_name,
    COALESCE(
        array_agg(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL),
        ARRAY[]::text[]
    ) AS genres
FROM event_promoters ep
JOIN events e      ON e.id = ep.event_id
LEFT JOIN venues v ON v.id = e.venue_id
LEFT JOIN event_genres eg ON eg.event_id = e.id
LEFT JOIN genres g        ON g.id = eg.genre_id
WHERE ep.promoter_id = %s
GROUP BY e.id, e.title, e.event_date, v.id, v.name
ORDER BY e.event_date DESC
LIMIT %s;
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fetch_artist_tags(artist_id: int, db: Connection) -> List[ExtractedTag]:
    with db.cursor() as cur:
        cur.execute(ARTIST_TAGS_SQL, (artist_id,))
        return [
            ExtractedTag(
                tag_type=row["tag_type"],
                tag_value=row["tag_value"],
                confidence=row["confidence"],
            )
            for row in cur.fetchall()
        ]


def fetch_event_tags(event_id: int, db: Connection) -> List[ExtractedTag]:
    with db.cursor() as cur:
        cur.execute(EVENT_TAGS_SQL, (event_id,))
        return [
            ExtractedTag(
                tag_type=row["tag_type"],
                tag_value=row["tag_value"],
                confidence=row["confidence"],
            )
            for row in cur.fetchall()
        ]


# ─── Builders ─────────────────────────────────────────────────────────────────

def build_artist_graph(id: int, limit: int, db: Connection) -> ArtistGraphResponse:
    center_id = str(id)
    nodes = {}
    links: List[GraphLinkWeighted] = []

    with db.cursor() as cur:
        cur.execute(ARTIST_INFO_SQL, (id,))
        artist = cur.fetchone()

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    center_tags = fetch_artist_tags(id, db)

    nodes[center_id] = ArtistNode(
        id=center_id,
        type="artist",
        name=artist["name"],
        genres=artist["genres"],
        tags=center_tags,
    )

    # manual connections → connected_to links
    with db.cursor() as cur:
        cur.execute(ARTIST_MANUAL_CONNECTIONS_SQL, (id, id))
        for row in cur.fetchall():
            connected_id = str(row["artist_id"])
            if connected_id not in nodes:
                connected_tags = fetch_artist_tags(row["artist_id"], db)
                nodes[connected_id] = ArtistNode(
                    id=connected_id,
                    type="artist",
                    name=row["name"],
                    tags=connected_tags,
                )
            links.append(GraphLinkWeighted(
                source=center_id,
                target=connected_id,
                weight=1,
                relationship="connected_to",
            ))

    with db.cursor() as cur:
        cur.execute(ARTIST_EVENTS_SQL, (id, limit))
        rows = cur.fetchall()

    for row in rows:
        event_id = str(row["event_id"])
        venue_id = str(row["venue_id"]) if row["venue_id"] else None

        if event_id not in nodes:
            event_tags = fetch_event_tags(row["event_id"], db)
            nodes[event_id] = EventNode(
                id=event_id,
                type="event",
                title=row["title"],
                genres=row["genres"],
                tags=event_tags,
                date=row["date"],
            )

        links.append(GraphLinkWeighted(
            source=center_id,
            target=event_id,
            weight=1,
            relationship="performed_at",
        ))

        if venue_id and venue_id not in nodes:
            nodes[venue_id] = VenueNode(
                id=venue_id,
                type="venue",
                name=row["venue_name"],
            )

        if venue_id:
            links.append(GraphLinkWeighted(
                source=event_id,
                target=venue_id,
                weight=1,
                relationship="held_at",
            ))

    return ArtistGraphResponse(
        centerNodeId=center_id,
        nodes=list(nodes.values()),
        links=links,
    )


def build_venue_graph(id: int, limit: int, db: Connection) -> GraphResponse:
    center_id = str(id)
    nodes = {}
    links: List[GraphLink] = []

    with db.cursor() as cur:
        cur.execute(VENUE_INFO_SQL, (id,))
        venue = cur.fetchone()

    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    nodes[center_id] = VenueNode(
        id=center_id,
        type="venue",
        name=venue["name"],
    )

    with db.cursor() as cur:
        cur.execute(VENUE_EVENTS_SQL, (id, limit))
        rows = cur.fetchall()

    for row in rows:
        event_id = str(row["event_id"])

        if event_id not in nodes:
            event_tags = fetch_event_tags(row["event_id"], db)
            nodes[event_id] = EventNode(
                id=event_id,
                type="event",
                title=row["title"],
                genres=row["genres"],
                tags=event_tags,
                date=row["date"],
            )

        links.append(GraphLink(
            source=center_id,
            target=event_id,
            relationship="held_at",
        ))

    return GraphResponse(
        centerNodeId=center_id,
        nodes=list(nodes.values()),
        links=links,
    )


def build_event_graph(id: int, limit: int, db: Connection) -> GraphResponse:
    center_id = str(id)
    nodes = {}
    links: List[GraphLink] = []

    with db.cursor() as cur:
        cur.execute(EVENT_INFO_SQL, (id,))
        event = cur.fetchone()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event_tags = fetch_event_tags(id, db)

    nodes[center_id] = EventNode(
        id=center_id,
        type="event",
        title=event["title"],
        genres=event["genres"],
        tags=event_tags,
        date=event["date"],
    )

    if event["venue_id"]:
        venue_id = str(event["venue_id"])
        nodes[venue_id] = VenueNode(
            id=venue_id,
            type="venue",
            name=event["venue_name"],
        )
        links.append(GraphLink(
            source=venue_id,
            target=center_id,
            relationship="held_at",
        ))

    with db.cursor() as cur:
        cur.execute(EVENT_ARTISTS_SQL, (id,))
        artists = cur.fetchall()

    for row in artists:
        artist_id = str(row["id"])
        if artist_id not in nodes:
            artist_tags = fetch_artist_tags(row["id"], db)
            nodes[artist_id] = ArtistNode(
                id=artist_id,
                type="artist",
                name=row["name"],
                tags=artist_tags,
            )
        links.append(GraphLink(
            source=artist_id,
            target=center_id,
            relationship="performed_at",
        ))

    return GraphResponse(
        centerNodeId=center_id,
        nodes=list(nodes.values()),
        links=links,
    )


def build_promoter_graph(id: int, limit: int, db: Connection) -> GraphResponse:
    center_id = str(id)
    nodes = {}
    links: List[GraphLink] = []

    with db.cursor() as cur:
        cur.execute(PROMOTER_INFO_SQL, (id,))
        promoter = cur.fetchone()

    if not promoter:
        raise HTTPException(status_code=404, detail="Promoter not found")

    nodes[center_id] = PromoterNode(
        id=center_id,
        type="promoter",
        name=promoter["name"],
    )

    with db.cursor() as cur:
        cur.execute(PROMOTER_EVENTS_SQL, (id, limit))
        rows = cur.fetchall()

    for row in rows:
        event_id = str(row["event_id"])
        venue_id = str(row["venue_id"]) if row["venue_id"] else None

        if event_id not in nodes:
            event_tags = fetch_event_tags(row["event_id"], db)
            nodes[event_id] = EventNode(
                id=event_id,
                type="event",
                title=row["title"],
                genres=row["genres"],
                tags=event_tags,
                date=row["date"],
            )

        links.append(GraphLink(
            source=center_id,
            target=event_id,
            relationship="promoted",
        ))

        if venue_id and venue_id not in nodes:
            nodes[venue_id] = VenueNode(
                id=venue_id,
                type="venue",
                name=row["venue_name"],
            )

        if venue_id:
            links.append(GraphLink(
                source=event_id,
                target=venue_id,
                relationship="held_at",
            ))

    return GraphResponse(
        centerNodeId=center_id,
        nodes=list(nodes.values()),
        links=links,
    )


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("/ego")
def get_ego_graph(
    type: str = Query(...),
    id: int = Query(...),
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(100, ge=1, le=500),
    db: Connection = Depends(get_db),
):
    if type == "artist":
        return build_artist_graph(id, limit, db)
    elif type == "venue":
        return build_venue_graph(id, limit, db)
    elif type == "event":
        return build_event_graph(id, limit, db)
    elif type == "promoter":
        return build_promoter_graph(id, limit, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported type: {type}")