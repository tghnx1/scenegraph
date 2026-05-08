from datetime import date as Date
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg import Connection

from app.db import get_db


app = FastAPI(title="Berlin Scene Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Venue(BaseModel):
    id: int
    name: str
    district: str
    scene_focus: str


class VenuesResponse(BaseModel):
    venues: list[Venue]


class GraphNode(BaseModel):
    id: str
    entityId: int
    type: Literal["artist", "event", "venue", "promoter"]
    label: str
    name: str
    genre: str | None = None
    genres: list[str] = Field(default_factory=list)
    eventCount: int | None = None
    date: Date | None = None
    district: str | None = None
    sceneFocus: str | None = None


class GraphLink(BaseModel):
    source: str
    target: str
    relationship: str
    weight: int = 1


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


def graph_node_id(node_type: str, entity_id: int) -> str:
    return f"{node_type}-{entity_id}"


@app.get("/health")
async def health(connection: Connection = Depends(get_db)) -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 AS ready")
        ready = cursor.fetchone()["ready"]

    return {"status": "ok", "database": "ok" if ready == 1 else "error"}


@app.get("/api")
async def root() -> dict[str, str]:
    return {"message": "Berlin Scene Graph backend is running."}


@app.get("/api/venues", response_model=VenuesResponse)
async def list_venues(connection: Connection = Depends(get_db)) -> VenuesResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                name,
                COALESCE(area_name, country_code, '') AS district,
                COALESCE(address, content_url, '') AS scene_focus
            FROM venues
            ORDER BY id ASC
            """
        )
        venues = cursor.fetchall()

    return VenuesResponse(venues=[Venue(**venue) for venue in venues])


@app.get("/api/graph", response_model=GraphResponse)
async def get_graph(
    genre: str | None = Query(default=None, min_length=1),
    date_from: Date | None = Query(default=None, alias="dateFrom"),
    date_to: Date | None = Query(default=None, alias="dateTo"),
    limit: int = Query(default=500, ge=1, le=1000),
    connection: Connection = Depends(get_db),
) -> GraphResponse:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="dateFrom must be earlier than or equal to dateTo.",
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                e.id,
                e.title,
                e.event_date::date AS event_date,
                e.venue_id,
                v.name AS venue_name,
                COALESCE(v.area_name, v.country_code, '') AS venue_district,
                COALESCE(v.address, v.content_url, '') AS venue_scene_focus,
                COALESCE(string_agg(DISTINCT g.name, ', '), '') AS genre,
                array_remove(array_agg(DISTINCT g.name), NULL) AS genres
            FROM events e
            LEFT JOIN venues v
                ON v.id = e.venue_id
            LEFT JOIN event_genres eg
                ON eg.event_id = e.id
            LEFT JOIN genres g
                ON g.id = eg.genre_id
            WHERE
                (%(date_from)s::date IS NULL OR e.event_date::date >= %(date_from)s::date)
                AND (%(date_to)s::date IS NULL OR e.event_date::date <= %(date_to)s::date)
                AND (
                    %(genre)s::text IS NULL
                    OR EXISTS (
                        SELECT 1
                        FROM event_genres eg_filter
                        JOIN genres g_filter
                            ON g_filter.id = eg_filter.genre_id
                        WHERE eg_filter.event_id = e.id
                          AND LOWER(g_filter.name) = LOWER(%(genre)s::text)
                    )
                )
            GROUP BY e.id, v.id
            ORDER BY e.event_date ASC, e.id ASC
            LIMIT %(limit)s
            """,
            {
                "genre": genre,
                "date_from": date_from,
                "date_to": date_to,
                "limit": limit,
            },
        )
        events = cursor.fetchall()

        if not events:
            return GraphResponse(nodes=[], links=[])

        event_ids = [event["id"] for event in events]

        cursor.execute(
            """
            SELECT
                a.id,
                a.name,
                COUNT(DISTINCT ea_all.event_id) AS event_count,
                COALESCE(string_agg(DISTINCT g.name, ', '), '') AS genre,
                array_remove(array_agg(DISTINCT g.name), NULL) AS genres
            FROM artists a
            JOIN event_artists ea_filtered
                ON ea_filtered.artist_id = a.id
            LEFT JOIN event_artists ea_all
                ON ea_all.artist_id = a.id
            LEFT JOIN event_genres eg
                ON eg.event_id = ea_all.event_id
            LEFT JOIN genres g
                ON g.id = eg.genre_id
            WHERE ea_filtered.event_id = ANY(%s)
            GROUP BY a.id, a.name
            ORDER BY a.name ASC
            """,
            (event_ids,),
        )
        artists = cursor.fetchall()

        cursor.execute(
            """
            SELECT artist_id, event_id
            FROM event_artists
            WHERE event_id = ANY(%s)
            ORDER BY event_id ASC, artist_id ASC
            """,
            (event_ids,),
        )
        artist_event_links = cursor.fetchall()

    nodes_by_id: dict[str, GraphNode] = {}
    links: list[GraphLink] = []

    for artist in artists:
        artist_node = GraphNode(
            id=graph_node_id("artist", artist["id"]),
            entityId=artist["id"],
            type="artist",
            label=artist["name"],
            name=artist["name"],
            genre=artist["genre"] or None,
            genres=artist["genres"] or [],
            eventCount=artist["event_count"],
        )
        nodes_by_id[artist_node.id] = artist_node

    for event in events:
        event_node = GraphNode(
            id=graph_node_id("event", event["id"]),
            entityId=event["id"],
            type="event",
            label=event["title"],
            name=event["title"],
            genre=event["genre"] or None,
            genres=event["genres"] or [],
            date=event["event_date"],
        )

        nodes_by_id[event_node.id] = event_node

        if event["venue_id"]:
            venue_node = GraphNode(
                id=graph_node_id("venue", event["venue_id"]),
                entityId=event["venue_id"],
                type="venue",
                label=event["venue_name"],
                name=event["venue_name"],
                district=event["venue_district"],
                sceneFocus=event["venue_scene_focus"],
            )

            nodes_by_id[venue_node.id] = venue_node

            links.append(
                GraphLink(
                    source=event_node.id,
                    target=venue_node.id,
                    relationship="held_at",
                    weight=1,
                )
            )

    for link in artist_event_links:
        links.append(
            GraphLink(
                source=graph_node_id("artist", link["artist_id"]),
                target=graph_node_id("event", link["event_id"]),
                relationship="performed_at",
                weight=1,
            )
        )

    type_order = {"artist": 0, "event": 1, "venue": 2, "promoter": 3}
    nodes = sorted(
        nodes_by_id.values(),
        key=lambda node: (type_order[node.type], node.name.lower(), node.entityId),
    )

    return GraphResponse(nodes=nodes, links=links)
