from __future__ import annotations

from collections import defaultdict
from datetime import date as DateValue
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from app.db import get_db
from app.recommendation_helpers import graph_node_id
from app.schemas import GraphLink, GraphNode, GraphResponse

router = APIRouter()

GraphNodeType = Literal["artist", "event", "venue", "promoter"]


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


@router.get(
    "/graph/ego",
    response_model=GraphResponse,
    response_model_exclude_none=True,
)
async def get_ego_graph(
    node_type: GraphNodeType = Query(..., alias="type"),
    entity_id: int = Query(..., alias="id", ge=1),
    depth: int = Query(default=1, ge=1, le=4),
    limit: int = Query(default=100, ge=1, le=1000),
    connection: Connection = Depends(get_db),
) -> GraphResponse:
    table_name = {
        "artist": "artists",
        "event": "events",
        "venue": "venues",
        "promoter": "promoters",
    }[node_type]
    center_node_id = graph_node_id(node_type, entity_id)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT 1 FROM {table_name} WHERE id = %s",
            (entity_id,),
        )
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail=f"{node_type} {entity_id} not found",
            )

        visited: dict[str, set[int]] = defaultdict(set)
        visited[node_type].add(entity_id)
        visited_count = 1
        frontier: dict[str, set[int]] = defaultdict(set)
        frontier[node_type].add(entity_id)
        links: list[GraphLink] = []
        link_keys: set[tuple[str, str, str]] = set()

        def add_node(node_kind: GraphNodeType, node_id: int) -> bool:
            nonlocal visited_count
            if node_id in visited[node_kind]:
                return True
            if visited_count >= limit:
                return False
            visited[node_kind].add(node_id)
            visited_count += 1
            return True

        def add_link(source: str, target: str, relationship: str) -> None:
            key = (source, target, relationship)
            if key in link_keys:
                return
            link_keys.add(key)
            links.append(
                GraphLink(
                    source=source,
                    target=target,
                    relationship=relationship,
                    weight=1,
                )
            )

        for _ in range(depth):
            if not frontier:
                break

            next_frontier: dict[str, set[int]] = defaultdict(set)
            current_frontier = frontier
            frontier = defaultdict(set)

            artist_ids = sorted(current_frontier.get("artist", set()))
            if artist_ids:
                cursor.execute(
                    """
                    SELECT
                        ea.artist_id,
                        e.id AS event_id,
                        e.venue_id
                    FROM event_artists ea
                    JOIN events e
                        ON e.id = ea.event_id
                    WHERE ea.artist_id = ANY(%s)
                    ORDER BY e.event_date ASC, e.id ASC
                    """,
                    (artist_ids,),
                )
                for row in cursor.fetchall():
                    artist_id = row["artist_id"]
                    event_id = row["event_id"]
                    if event_id is None:
                        continue

                    event_known = event_id in visited["event"]
                    if not event_known and not add_node("event", event_id):
                        continue

                    add_link(
                        graph_node_id("artist", artist_id),
                        graph_node_id("event", event_id),
                        "performed_at",
                    )
                    if not event_known:
                        next_frontier["event"].add(event_id)

                    venue_id = row["venue_id"]
                    if venue_id is not None:
                        venue_known = venue_id in visited["venue"]
                        if not venue_known and not add_node("venue", venue_id):
                            continue
                        add_link(
                            graph_node_id("event", event_id),
                            graph_node_id("venue", venue_id),
                            "held_at",
                        )
                        if not venue_known:
                            next_frontier["venue"].add(venue_id)

            promoter_ids = sorted(current_frontier.get("promoter", set()))
            if promoter_ids:
                cursor.execute(
                    """
                    SELECT
                        ep.promoter_id,
                        e.id AS event_id,
                        e.venue_id
                    FROM event_promoters ep
                    JOIN events e
                        ON e.id = ep.event_id
                    WHERE ep.promoter_id = ANY(%s)
                    ORDER BY e.event_date ASC, e.id ASC
                    """,
                    (promoter_ids,),
                )
                for row in cursor.fetchall():
                    promoter_id = row["promoter_id"]
                    event_id = row["event_id"]
                    if event_id is None:
                        continue

                    event_known = event_id in visited["event"]
                    if not event_known and not add_node("event", event_id):
                        continue

                    add_link(
                        graph_node_id("promoter", promoter_id),
                        graph_node_id("event", event_id),
                        "organized",
                    )
                    if not event_known:
                        next_frontier["event"].add(event_id)

                    venue_id = row["venue_id"]
                    if venue_id is not None:
                        venue_known = venue_id in visited["venue"]
                        if not venue_known and not add_node("venue", venue_id):
                            continue
                        add_link(
                            graph_node_id("event", event_id),
                            graph_node_id("venue", venue_id),
                            "held_at",
                        )
                        if not venue_known:
                            next_frontier["venue"].add(venue_id)

            venue_ids = sorted(current_frontier.get("venue", set()))
            if venue_ids:
                cursor.execute(
                    """
                    SELECT
                        v.id AS venue_id,
                        e.id AS event_id
                    FROM venues v
                    JOIN events e
                        ON e.venue_id = v.id
                    WHERE v.id = ANY(%s)
                    ORDER BY e.event_date ASC, e.id ASC
                    """,
                    (venue_ids,),
                )
                for row in cursor.fetchall():
                    venue_id = row["venue_id"]
                    event_id = row["event_id"]
                    if event_id is None:
                        continue

                    event_known = event_id in visited["event"]
                    if not event_known and not add_node("event", event_id):
                        continue

                    add_link(
                        graph_node_id("venue", venue_id),
                        graph_node_id("event", event_id),
                        "held_at",
                    )
                    if not event_known:
                        next_frontier["event"].add(event_id)

            event_ids = sorted(current_frontier.get("event", set()))
            if event_ids:
                cursor.execute(
                    """
                    SELECT
                        ea.event_id,
                        ea.artist_id
                    FROM event_artists ea
                    WHERE ea.event_id = ANY(%s)
                    ORDER BY ea.event_id ASC, ea.artist_id ASC
                    """,
                    (event_ids,),
                )
                for row in cursor.fetchall():
                    artist_id = row["artist_id"]
                    artist_known = artist_id in visited["artist"]
                    if not artist_known and not add_node("artist", artist_id):
                        continue

                    add_link(
                        graph_node_id("artist", artist_id),
                        graph_node_id("event", row["event_id"]),
                        "performed_at",
                    )
                    if not artist_known:
                        next_frontier["artist"].add(artist_id)

                cursor.execute(
                    """
                    SELECT
                        ep.event_id,
                        ep.promoter_id
                    FROM event_promoters ep
                    WHERE ep.event_id = ANY(%s)
                    ORDER BY ep.event_id ASC, ep.promoter_id ASC
                    """,
                    (event_ids,),
                )
                for row in cursor.fetchall():
                    promoter_id = row["promoter_id"]
                    promoter_known = promoter_id in visited["promoter"]
                    if not promoter_known and not add_node("promoter", promoter_id):
                        continue

                    add_link(
                        graph_node_id("promoter", promoter_id),
                        graph_node_id("event", row["event_id"]),
                        "organized",
                    )
                    if not promoter_known:
                        next_frontier["promoter"].add(promoter_id)

            frontier = next_frontier

        artist_ids = sorted(visited.get("artist", set()))
        event_ids = sorted(visited.get("event", set()))
        venue_ids = sorted(visited.get("venue", set()))
        promoter_ids = sorted(visited.get("promoter", set()))

        nodes_by_id: dict[str, GraphNode] = {}

        if artist_ids:
            cursor.execute(
                """
                SELECT
                    a.id,
                    a.name,
                    COUNT(DISTINCT ea_all.event_id) AS event_count,
                    array_remove(array_agg(DISTINCT LOWER(g.name)), NULL) AS genres
                FROM artists a
                LEFT JOIN event_artists ea_all
                    ON ea_all.artist_id = a.id
                LEFT JOIN event_genres eg
                    ON eg.event_id = ea_all.event_id
                LEFT JOIN genres g
                    ON g.id = eg.genre_id
                WHERE a.id = ANY(%s)
                GROUP BY a.id, a.name
                ORDER BY a.name ASC
                """,
                (artist_ids,),
            )
            for artist in cursor.fetchall():
                artist_node = GraphNode(
                    id=graph_node_id("artist", artist["id"]),
                    entityId=artist["id"],
                    type="artist",
                    name=artist["name"],
                    genres=artist["genres"] or [],
                    eventCount=artist["event_count"],
                )
                nodes_by_id[artist_node.id] = artist_node

        if event_ids:
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
                WHERE e.id = ANY(%s)
                GROUP BY e.id, v.id
                ORDER BY e.event_date ASC, e.id ASC
                """,
                (event_ids,),
            )
            for event in cursor.fetchall():
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
                    venue_node_id = graph_node_id("venue", event["venue_id"])
                    if venue_node_id not in nodes_by_id:
                        venue_node = GraphNode(
                            id=venue_node_id,
                            entityId=event["venue_id"],
                            type="venue",
                            name=event["venue_name"],
                            district=event["venue_district"],
                            sceneFocus=event["venue_scene_focus"],
                        )
                        nodes_by_id[venue_node.id] = venue_node

        if venue_ids:
            cursor.execute(
                """
                SELECT
                    v.id,
                    v.name,
                    COUNT(DISTINCT e.id) AS event_count,
                    COALESCE(v.area_name, v.country_code, '') AS district,
                    COALESCE(v.address, v.content_url, '') AS scene_focus
                FROM venues v
                LEFT JOIN events e
                    ON e.venue_id = v.id
                WHERE v.id = ANY(%s)
                GROUP BY v.id, v.name, v.area_name, v.country_code, v.address, v.content_url
                ORDER BY v.name ASC
                """,
                (venue_ids,),
            )
            for venue in cursor.fetchall():
                venue_node = GraphNode(
                    id=graph_node_id("venue", venue["id"]),
                    entityId=venue["id"],
                    type="venue",
                    name=venue["name"],
                    eventCount=venue["event_count"],
                    district=venue["district"],
                    sceneFocus=venue["scene_focus"],
                )
                nodes_by_id[venue_node.id] = venue_node

        if promoter_ids:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    COUNT(DISTINCT ep_all.event_id) AS event_count
                FROM promoters p
                LEFT JOIN event_promoters ep_all
                    ON ep_all.promoter_id = p.id
                WHERE p.id = ANY(%s)
                GROUP BY p.id, p.name
                ORDER BY p.name ASC
                """,
                (promoter_ids,),
            )
            for promoter in cursor.fetchall():
                promoter_node = GraphNode(
                    id=graph_node_id("promoter", promoter["id"]),
                    entityId=promoter["id"],
                    type="promoter",
                    name=promoter["name"],
                    eventCount=promoter["event_count"],
                )
                nodes_by_id[promoter_node.id] = promoter_node

    type_order = {"artist": 0, "event": 1, "venue": 2, "promoter": 3}
    nodes = sorted(
        nodes_by_id.values(),
        key=lambda node: (type_order[node.type], node.name.lower(), node.entityId),
    )

    return GraphResponse(
        centerNodeId=center_node_id,
        nodes=nodes,
        links=links,
        graphMode="full",
    )
