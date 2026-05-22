from __future__ import annotations

from datetime import date as DateValue

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from app.db import get_db
from app.recommendation_helpers import graph_node_id
from app.schemas import GraphLink, GraphNode, GraphResponse

router = APIRouter()


@router.get(
    "/graph",
    response_model=GraphResponse,
    response_model_exclude_none=True,
)
async def get_graph(
    genre: str | None = Query(default=None, min_length=1),
    date_from: DateValue | None = Query(default=None, alias="dateFrom"),
    date_to: DateValue | None = Query(default=None, alias="dateTo"),
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
                array_remove(array_agg(DISTINCT LOWER(g.name)), NULL) AS genres
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
                array_remove(array_agg(DISTINCT LOWER(g.name)), NULL) AS genres
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

        cursor.execute(
            """
            SELECT
                p.id,
                p.name,
                COUNT(DISTINCT ep_all.event_id) AS event_count
            FROM promoters p
            JOIN event_promoters ep_filtered
                ON ep_filtered.promoter_id = p.id
            LEFT JOIN event_promoters ep_all
                ON ep_all.promoter_id = p.id
            WHERE ep_filtered.event_id = ANY(%s)
            GROUP BY p.id, p.name
            ORDER BY p.name ASC
            """,
            (event_ids,),
        )
        promoters = cursor.fetchall()

        cursor.execute(
            """
            SELECT promoter_id, event_id
            FROM event_promoters
            WHERE event_id = ANY(%s)
            ORDER BY event_id ASC, promoter_id ASC
            """,
            (event_ids,),
        )
        promoter_event_links = cursor.fetchall()

    nodes_by_id: dict[str, GraphNode] = {}
    links: list[GraphLink] = []

    for artist in artists:
        artist_node = GraphNode(
            id=graph_node_id("artist", artist["id"]),
            entityId=artist["id"],
            type="artist",
            name=artist["name"],
            genres=artist["genres"] or [],
            eventCount=artist["event_count"],
        )
        nodes_by_id[artist_node.id] = artist_node

    for promoter in promoters:
        promoter_node = GraphNode(
            id=graph_node_id("promoter", promoter["id"]),
            entityId=promoter["id"],
            type="promoter",
            name=promoter["name"],
            eventCount=promoter["event_count"],
        )
        nodes_by_id[promoter_node.id] = promoter_node

    for event in events:
        event_node = GraphNode(
            id=graph_node_id("event", event["id"]),
            entityId=event["id"],
            type="event",
            name=event["title"],
            genres=event["genres"] or [],
            date=event["event_date"],
            startDate=event["event_date"],
            endDate=event["event_date"],
        )

        nodes_by_id[event_node.id] = event_node

        if event["venue_id"]:
            venue_node = GraphNode(
                id=graph_node_id("venue", event["venue_id"]),
                entityId=event["venue_id"],
                type="venue",
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

    for link in promoter_event_links:
        links.append(
            GraphLink(
                source=graph_node_id("promoter", link["promoter_id"]),
                target=graph_node_id("event", link["event_id"]),
                relationship="organized",
                weight=1,
            )
        )

    type_order = {"artist": 0, "event": 1, "venue": 2, "promoter": 3}
    nodes = sorted(
        nodes_by_id.values(),
        key=lambda node: (type_order[node.type], node.name.lower(), node.entityId),
    )

    return GraphResponse(nodes=nodes, links=links)
