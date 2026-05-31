from __future__ import annotations

from collections import defaultdict
from datetime import date as DateValue
from datetime import datetime
from typing import Literal

from psycopg import Connection

from app.recommendation_helpers import graph_node_id
from app.recommendation_scoring import PromoterRecommendationScoringConfig
from app.schemas import (
    GraphLink,
    GraphNode,
    GraphResponse,
    PromoterRecommendationItem,
    RecommendationEvidenceItem,
)

RECOMMENDATION_REASON_ITEM_LIMIT = 5
RECOMMENDATION_REASON_MAX_CHARS = 220

# Convert event date recency into a 0..1 score.
def date_recency_score(value: DateValue | datetime | None) -> float:
    if value is None:
        return 0.0
    event_date = value.date() if isinstance(value, datetime) else value
    age_days = max((DateValue.today() - event_date).days, 0)
    return max(0.0, 1.0 - age_days / 365)

# Build user-facing reason strings for a promoter recommendation row.
def promoter_recommendation_reasons(row: dict) -> list[str]:
    # Keep order while removing duplicates to avoid repeated names in reasons.
    def dedupe_keep_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    # Format a list-valued reason with a stable display limit and +N suffix.
    def list_reason(prefix: str, values: list[str]) -> str:
        if not values:
            return prefix
        displayed = values[:RECOMMENDATION_REASON_ITEM_LIMIT]
        hidden_count = max(len(values) - len(displayed), 0)
        while displayed:
            reason = f"{prefix}: {', '.join(displayed)}"
            if hidden_count > 0:
                reason += f", +{hidden_count} more"
            if len(reason) <= RECOMMENDATION_REASON_MAX_CHARS:
                return reason
            # Keep removing one displayed item while preserving total hidden count.
            displayed = displayed[:-1]
            hidden_count += 1

        return f"{prefix}: +{len(values)} more"

    # Normalize generic string arrays from DB rows.
    def names_list(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        result = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        return dedupe_keep_order(result)

    # Normalize artist objects into a list of artist names.
    def artist_names(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        result: list[str] = []
        for value in values:
            if isinstance(value, dict):
                name = value.get("name")
                if isinstance(name, str) and name.strip():
                    result.append(name.strip())
        return dedupe_keep_order(result)

    reasons = []
    if row["direct_connection_count"] > 0:
        reasons.append(f"{row['direct_connection_count']} direct artist-promoter events")
    manual_warm_connection_count = int(row.get("manual_warm_connection_count", 0) or 0)
    if row["warm_connection_count"] > 0:
        warm_names = artist_names(row.get("warm_connection_artists"))
        if warm_names:
            reasons.append(list_reason(f"{row['warm_connection_count']} co-played artists connected", warm_names))
        else:
            reasons.append(f"{row['warm_connection_count']} co-played artists connected")
    if manual_warm_connection_count > 0:
        manual_names = artist_names(row.get("manual_warm_connection_artists"))
        if manual_names:
            reasons.append(
                list_reason(
                    f"{manual_warm_connection_count} manually added trusted artist links",
                    manual_names,
                )
            )
        else:
            reasons.append(f"{manual_warm_connection_count} manually added trusted artist links")
    if row["matched_artist_count"] > 0:
        matched_artist_names = names_list(row.get("matched_artist_names"))
        if matched_artist_names:
            reasons.append(
                list_reason(f"{row['matched_artist_count']} similar artists connected", matched_artist_names)
            )
        else:
            reasons.append(f"{row['matched_artist_count']} similar artists connected")
    if row["event_similarity_count"] > 0:
        event_similarity_titles = names_list(row.get("event_similarity_event_titles"))
        if event_similarity_titles:
            displayed_event_similarity_count = len(event_similarity_titles)
            reasons.append(
                list_reason(
                    f"{displayed_event_similarity_count} similar promoter events",
                    event_similarity_titles,
                )
            )
        else:
            reasons.append(f"{row['event_similarity_count']} similar promoter events")
    if row["event_count"] > 0:
        related_event_titles = names_list(row.get("related_event_titles"))
        if related_event_titles:
            displayed_related_event_count = len(related_event_titles)
            reasons.append(
                list_reason(
                    f"{displayed_related_event_count} related promoter events",
                    related_event_titles,
                )
            )
        else:
            reasons.append(f"{row['event_count']} related promoter events")
    if row["latest_event_date"] is not None:
        reasons.append(f"latest related event on {row['latest_event_date']}")
    return reasons[:4]

# Derive recommendation status label from direct and warm counts.
def promoter_recommendation_status(
    row: dict,
    scoring_config: PromoterRecommendationScoringConfig,
) -> str:
    manual_warm_connection_count = int(row.get("manual_warm_connection_count", 0) or 0)
    if row["direct_connection_count"] >= scoring_config.existing_partner_direct_min:
        return "existing_partner"
    if (
        row["warm_connection_count"] >= scoring_config.warm_relevant_connection_min
        or manual_warm_connection_count > 0
    ):
        return "warm_relevant"
    return "new_relevant"

# Build structured evidence entries shown in recommendation payloads.
def promoter_recommendation_item_evidence(row: dict) -> list[RecommendationEvidenceItem]:
    evidence: list[RecommendationEvidenceItem] = []
    if row["direct_connection_count"] > 0:
        evidence.append(
            RecommendationEvidenceItem(
                type="direct_connection",
                path="Source Artist -> Event -> Promoter",
            )
        )
    if row["warm_connection_count"] > 0:
        evidence.append(
            RecommendationEvidenceItem(
                type="warm_network",
                path="Source Artist -> Shared Event -> Co-played Artist -> Other Event -> Promoter",
            )
        )
    manual_warm_connection_count = int(row.get("manual_warm_connection_count", 0) or 0)
    if manual_warm_connection_count > 0:
        evidence.append(
            RecommendationEvidenceItem(
                type="manual_connection",
                path="Source Artist -> Trusted Artist Link -> Event -> Promoter",
            )
        )
    if row["event_similarity_count"] > 0:
        evidence.append(
            RecommendationEvidenceItem(
                type="event_similarity",
                path="Source Artist -> Source Event -> Similar Promoter Event -> Promoter",
            )
        )
    if row["matched_artist_count"] > 0 and row["semantic_score"] > 0:
        evidence.append(
            RecommendationEvidenceItem(
                type="semantic_bridge",
                path="Source Artist -> Similar Artist -> Event -> Promoter",
            )
        )
    return evidence

# Build explainability graph payload for Artist -> Promoter recommendations.
def promoter_recommendation_graph(
    *,
    source_artist_id: int,
    source_artist_name: str,
    recommendations: list[PromoterRecommendationItem],
    semantic_evidence_rows: list[dict],
    direct_evidence_rows: list[dict],
    warm_evidence_rows: list[dict],
    manual_evidence_rows: list[dict],
    event_similarity_evidence_rows: list[dict],
    scoring_config: PromoterRecommendationScoringConfig,
) -> GraphResponse:
    source_artist_node_id = graph_node_id("artist", source_artist_id)
    nodes: dict[str, GraphNode] = {
        source_artist_node_id: GraphNode(
            id=source_artist_node_id,
            entityId=source_artist_id,
            type="artist",
            name=source_artist_name,
        )
    }
    links: list[GraphLink] = []
    seen_links: set[tuple[str, str, str]] = set()
    preferred_path_node_ids: dict[str, set[str]] = defaultdict(set)
    preferred_path_link_keys: dict[str, set[str]] = defaultdict(set)
    preferred_co_played_artist_ids_by_promoter: dict[int, set[int]] = {}
    preferred_manual_artist_ids_by_promoter: dict[int, set[int]] = {}

    for recommendation in recommendations:
        promoter_node_id = graph_node_id("promoter", recommendation.id)
        nodes[promoter_node_id] = GraphNode(
            id=promoter_node_id,
            entityId=recommendation.id,
            type="promoter",
            name=recommendation.name,
            eventCount=recommendation.eventCount,
        )
        preferred_co_played_artist_ids_by_promoter[recommendation.id] = {
            artist.id for artist in recommendation.coPlayedConnectionArtists
        }
        preferred_manual_artist_ids_by_promoter[recommendation.id] = {
            artist.id for artist in recommendation.manualConnectionArtists
        }

    # Build a deterministic undirected link key used by frontend path focus.
    def undirected_link_key(source: str, target: str) -> str:
        return "|".join(sorted((source, target)))

    # Register a path edge into per-promoter focused path payload.
    def add_preferred_path_edge(promoter_id: int, source: str, target: str) -> None:
        promoter_node_id = graph_node_id("promoter", promoter_id)
        preferred_path_node_ids[promoter_node_id].add(source)
        preferred_path_node_ids[promoter_node_id].add(target)
        preferred_path_link_keys[promoter_node_id].add(undirected_link_key(source, target))

    # Add a graph link once and preserve deduplication by key.
    def add_link(
        source: str,
        target: str,
        relationship: str,
        weight: int = 1,
        *,
        evidence_type: str | None = None,
        style: Literal["solid", "dashed", "dotted"] | None = None,
        strength: float | None = None,
    ) -> None:
        key = (source, target, relationship)
        if key in seen_links:
            return
        seen_links.add(key)
        links.append(
            GraphLink(
                source=source,
                target=target,
                relationship=relationship,
                weight=weight,
                evidenceType=evidence_type,
                style=style,
                strength=strength,
            )
        )

    for row in direct_evidence_rows:
        promoter_node_id = graph_node_id("promoter", row["promoter_id"])
        event_node_id = graph_node_id("event", row["event_id"])
        direct_strength = max(
            scoring_config.direct_edge_strength_min,
            min(
                scoring_config.direct_edge_strength_max,
                row["direct_connection_count"] / scoring_config.direct_connection_cap,
            ),
        )

        nodes[event_node_id] = GraphNode(
            id=event_node_id,
            entityId=row["event_id"],
            type="event",
            name=row["event_title"],
            date=row["event_date"],
        )
        add_link(
            source_artist_node_id,
            event_node_id,
            "played",
            evidence_type="direct_connection",
            style="solid",
            strength=direct_strength,
        )
        add_link(
            promoter_node_id,
            event_node_id,
            "organized",
            evidence_type="direct_connection",
            style="solid",
            strength=direct_strength,
        )

        if row["venue_id"] is not None:
            venue_node_id = graph_node_id("venue", row["venue_id"])
            nodes[venue_node_id] = GraphNode(
                id=venue_node_id,
                entityId=row["venue_id"],
                type="venue",
                name=row["venue_name"],
            )
            add_link(
                event_node_id,
                venue_node_id,
                "at",
                evidence_type="direct_connection",
                style="solid",
                strength=max(scoring_config.warm_edge_strength_min, direct_strength * 0.9),
            )

    for row in warm_evidence_rows:
        promoter_id = int(row["promoter_id"])
        promoter_node_id = graph_node_id("promoter", promoter_id)
        co_artist_node_id = graph_node_id("artist", row["co_artist_id"])
        shared_event_id = row["shared_event_id"]
        shared_event_node_id = graph_node_id("event", shared_event_id)
        other_event_node_id = graph_node_id("event", row["other_event_id"])
        warm_strength = max(
            scoring_config.warm_edge_strength_min,
            min(
                scoring_config.warm_edge_strength_max,
                row["warm_connection_count"] / scoring_config.warm_connection_cap,
            ),
        )

        nodes[co_artist_node_id] = GraphNode(
            id=co_artist_node_id,
            entityId=row["co_artist_id"],
            type="artist",
            name=row["co_artist_name"],
        )
        nodes[shared_event_node_id] = GraphNode(
            id=shared_event_node_id,
            entityId=shared_event_id,
            type="event",
            name=row["shared_event_title"],
            date=row["shared_event_date"],
        )
        nodes[other_event_node_id] = GraphNode(
            id=other_event_node_id,
            entityId=row["other_event_id"],
            type="event",
            name=row["other_event_title"],
            date=row["other_event_date"],
        )
        add_link(
            source_artist_node_id,
            shared_event_node_id,
            "played",
            evidence_type="warm_network",
            style="solid",
            strength=warm_strength,
        )
        add_link(
            co_artist_node_id,
            shared_event_node_id,
            "played",
            evidence_type="warm_network",
            style="solid",
            strength=warm_strength,
        )
        add_link(
            co_artist_node_id,
            other_event_node_id,
            "played",
            evidence_type="warm_network",
            style="solid",
            strength=warm_strength,
        )
        add_link(
            promoter_node_id,
            other_event_node_id,
            "organized",
            evidence_type="warm_network",
            style="solid",
            strength=warm_strength,
        )

        preferred_co_played_artist_ids = preferred_co_played_artist_ids_by_promoter.get(promoter_id, set())
        if int(row["co_artist_id"]) in preferred_co_played_artist_ids:
            add_preferred_path_edge(promoter_id, source_artist_node_id, shared_event_node_id)
            add_preferred_path_edge(promoter_id, shared_event_node_id, co_artist_node_id)
            add_preferred_path_edge(promoter_id, co_artist_node_id, other_event_node_id)
            add_preferred_path_edge(promoter_id, other_event_node_id, promoter_node_id)

        if row["other_venue_id"] is not None:
            venue_node_id = graph_node_id("venue", row["other_venue_id"])
            nodes[venue_node_id] = GraphNode(
                id=venue_node_id,
                entityId=row["other_venue_id"],
                type="venue",
                name=row["other_venue_name"],
            )
            add_link(
                other_event_node_id,
                venue_node_id,
                "at",
                evidence_type="warm_network",
                style="solid",
                strength=max(0.3, warm_strength * 0.9),
            )
            if int(row["co_artist_id"]) in preferred_co_played_artist_ids:
                add_preferred_path_edge(promoter_id, other_event_node_id, venue_node_id)

    # Add explicit trusted-artist connection paths used by manual connection signal.
    for row in manual_evidence_rows:
        promoter_id = int(row["promoter_id"])
        promoter_node_id = graph_node_id("promoter", promoter_id)
        trusted_artist_node_id = graph_node_id("artist", row["co_artist_id"])
        trusted_event_node_id = graph_node_id("event", row["event_id"])
        manual_strength = max(
            scoring_config.warm_edge_strength_min,
            min(
                scoring_config.warm_edge_strength_max,
                row["manual_connection_count"] / scoring_config.manual_warm_connection_cap,
            ),
        )

        nodes[trusted_artist_node_id] = GraphNode(
            id=trusted_artist_node_id,
            entityId=row["co_artist_id"],
            type="artist",
            name=row["co_artist_name"],
        )
        nodes[trusted_event_node_id] = GraphNode(
            id=trusted_event_node_id,
            entityId=row["event_id"],
            type="event",
            name=row["event_title"],
            date=row["event_date"],
        )
        add_link(
            source_artist_node_id,
            trusted_artist_node_id,
            "trusted",
            evidence_type="manual_connection",
            style="solid",
            strength=manual_strength,
        )
        add_link(
            trusted_artist_node_id,
            trusted_event_node_id,
            "played",
            evidence_type="manual_connection",
            style="solid",
            strength=max(0.4, manual_strength),
        )
        add_link(
            promoter_node_id,
            trusted_event_node_id,
            "organized",
            evidence_type="manual_connection",
            style="solid",
            strength=max(0.4, manual_strength),
        )

        preferred_manual_artist_ids = preferred_manual_artist_ids_by_promoter.get(promoter_id, set())
        if int(row["co_artist_id"]) in preferred_manual_artist_ids:
            add_preferred_path_edge(promoter_id, source_artist_node_id, trusted_artist_node_id)
            add_preferred_path_edge(promoter_id, trusted_artist_node_id, trusted_event_node_id)
            add_preferred_path_edge(promoter_id, trusted_event_node_id, promoter_node_id)

        if row["venue_id"] is not None:
            venue_node_id = graph_node_id("venue", row["venue_id"])
            nodes[venue_node_id] = GraphNode(
                id=venue_node_id,
                entityId=row["venue_id"],
                type="venue",
                name=row["venue_name"],
            )
            add_link(
                trusted_event_node_id,
                venue_node_id,
                "at",
                evidence_type="manual_connection",
                style="solid",
                strength=max(0.3, manual_strength * 0.9),
            )
            if int(row["co_artist_id"]) in preferred_manual_artist_ids:
                add_preferred_path_edge(promoter_id, trusted_event_node_id, venue_node_id)

    for row in event_similarity_evidence_rows:
        promoter_node_id = graph_node_id("promoter", row["promoter_id"])
        source_event_node_id = graph_node_id("event", row["source_event_id"])
        promoter_event_node_id = graph_node_id("event", row["promoter_event_id"])
        shared_artists = row.get("shared_artists") or []
        event_similarity_strength = max(
            scoring_config.event_similarity_edge_strength_min,
            min(
                scoring_config.event_similarity_edge_strength_max,
                row["path_similarity"],
            ),
        )

        nodes[source_event_node_id] = GraphNode(
            id=source_event_node_id,
            entityId=row["source_event_id"],
            type="event",
            name=row["source_event_title"],
            date=row["source_event_date"],
        )
        nodes[promoter_event_node_id] = GraphNode(
            id=promoter_event_node_id,
            entityId=row["promoter_event_id"],
            type="event",
            name=row["promoter_event_title"],
            date=row["promoter_event_date"],
        )
        add_link(
            graph_node_id("artist", source_artist_id),
            source_event_node_id,
            "played",
            evidence_type="event_similarity",
            style="solid",
            strength=max(0.4, event_similarity_strength),
        )
        add_link(
            source_event_node_id,
            promoter_event_node_id,
            "event similarity",
            evidence_type="event_similarity",
            style="dotted",
            strength=event_similarity_strength,
        )

        for shared_artist in shared_artists:
            shared_artist_id = int(shared_artist["id"])
            shared_artist_name = shared_artist["name"]
            shared_artist_node_id = graph_node_id("artist", shared_artist_id)
            nodes[shared_artist_node_id] = GraphNode(
                id=shared_artist_node_id,
                entityId=shared_artist_id,
                type="artist",
                name=shared_artist_name,
            )
            add_link(
                source_event_node_id,
                shared_artist_node_id,
                "played",
                evidence_type="event_similarity",
                style="solid",
                strength=max(0.4, event_similarity_strength),
            )
            add_link(
                shared_artist_node_id,
                promoter_event_node_id,
                "played",
                evidence_type="event_similarity",
                style="solid",
                strength=max(0.4, event_similarity_strength),
            )

        add_link(
            promoter_node_id,
            promoter_event_node_id,
            "organized",
            evidence_type="event_similarity",
            style="solid",
            strength=max(0.4, event_similarity_strength),
        )

        if row["promoter_venue_id"] is not None:
            venue_node_id = graph_node_id("venue", row["promoter_venue_id"])
            nodes[venue_node_id] = GraphNode(
                id=venue_node_id,
                entityId=row["promoter_venue_id"],
                type="venue",
                name=row["promoter_venue_name"],
            )
            add_link(
                promoter_event_node_id,
                venue_node_id,
                "at",
                evidence_type="event_similarity",
                style="solid",
                strength=max(0.3, event_similarity_strength * 0.9),
            )

    for row in semantic_evidence_rows:
        promoter_node_id = graph_node_id("promoter", row["promoter_id"])
        artist_node_id = graph_node_id("artist", row["artist_id"])
        event_node_id = graph_node_id("event", row["event_id"])

        nodes[artist_node_id] = GraphNode(
            id=artist_node_id,
            entityId=row["artist_id"],
            type="artist",
            name=row["artist_name"],
        )
        nodes[event_node_id] = GraphNode(
            id=event_node_id,
            entityId=row["event_id"],
            type="event",
            name=row["event_title"],
            date=row["event_date"],
        )

        semantic_strength = max(0.0, min(float(row["semantic_score"]), 1.0))
        add_link(
            graph_node_id("artist", source_artist_id),
            artist_node_id,
            "semantic match",
            max(1, round(semantic_strength * 10)),
            evidence_type="semantic_bridge",
            style="dashed",
            strength=semantic_strength,
        )
        add_link(
            artist_node_id,
            event_node_id,
            "played",
            evidence_type="semantic_bridge",
            style="solid",
            strength=max(0.5, semantic_strength),
        )
        add_link(
            promoter_node_id,
            event_node_id,
            "organized",
            evidence_type="semantic_bridge",
            style="solid",
            strength=max(0.5, semantic_strength),
        )

        if row["venue_id"] is not None:
            venue_node_id = graph_node_id("venue", row["venue_id"])
            nodes[venue_node_id] = GraphNode(
                id=venue_node_id,
                entityId=row["venue_id"],
                type="venue",
                name=row["venue_name"],
            )
            add_link(
                event_node_id,
                venue_node_id,
                "at",
                evidence_type="semantic_bridge",
                style="solid",
                strength=max(0.3, semantic_strength * 0.8),
            )

    return GraphResponse(
        nodes=list(nodes.values()),
        links=links,
        promoterPathNodeIds={
            promoter_node_id: sorted(node_ids)
            for promoter_node_id, node_ids in preferred_path_node_ids.items()
            if node_ids
        },
        promoterPathLinkKeys={
            promoter_node_id: sorted(link_keys)
            for promoter_node_id, link_keys in preferred_path_link_keys.items()
            if link_keys
        },
    )

# Load semantic-bridge evidence rows used for recommendation graph building.
def promoter_recommendation_evidence(
    connection: Connection,
    *,
    promoter_ids: list[int],
    semantic_scores: dict[int, float],
) -> list[dict]:
    if not promoter_ids or not semantic_scores:
        return []

    artist_ids = list(semantic_scores.keys())
    artist_scores = [semantic_scores[artist_id] for artist_id in artist_ids]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH semantic_candidates AS (
                SELECT *
                FROM unnest(%(artist_ids)s::bigint[], %(artist_scores)s::double precision[])
                    AS candidate(artist_id, semantic_score)
            ),
            ranked_evidence AS (
                SELECT
                    ep.promoter_id,
                    a.id AS artist_id,
                    a.name AS artist_name,
                    e.id AS event_id,
                    e.title AS event_title,
                    e.event_date::date AS event_date,
                    e.venue_id,
                    v.name AS venue_name,
                    sc.semantic_score,
                    row_number() OVER (
                        PARTITION BY ep.promoter_id
                        ORDER BY sc.semantic_score DESC, e.event_date DESC NULLS LAST, e.id DESC
                    ) AS row_number
                FROM semantic_candidates sc
                JOIN artists a
                    ON a.id = sc.artist_id
                JOIN event_artists ea
                    ON ea.artist_id = sc.artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                LEFT JOIN venues v
                    ON v.id = e.venue_id
                WHERE ep.promoter_id = ANY(%(promoter_ids)s)
            )
            SELECT *
            FROM ranked_evidence
            WHERE row_number <= 5
            ORDER BY promoter_id ASC, row_number ASC
            """,
            {
                "artist_ids": artist_ids,
                "artist_scores": artist_scores,
                "promoter_ids": promoter_ids,
            },
        )
        return cursor.fetchall()

# Load direct source-artist to promoter evidence rows.
def promoter_direct_connection_evidence(
    connection: Connection,
    *,
    source_artist_id: int,
    promoter_ids: list[int],
) -> list[dict]:
    if not promoter_ids:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH direct_counts AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT e.id)::int AS direct_connection_count
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                WHERE ea.artist_id = %(source_artist_id)s
                  AND ep.promoter_id = ANY(%(promoter_ids)s)
                GROUP BY ep.promoter_id
            ),
            ranked_evidence AS (
                SELECT
                    ep.promoter_id,
                    e.id AS event_id,
                    e.title AS event_title,
                    e.event_date::date AS event_date,
                    e.venue_id,
                    v.name AS venue_name,
                    dc.direct_connection_count,
                    row_number() OVER (
                        PARTITION BY ep.promoter_id
                        ORDER BY e.event_date DESC NULLS LAST, e.id DESC
                    ) AS row_number
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                JOIN direct_counts dc
                    ON dc.promoter_id = ep.promoter_id
                LEFT JOIN venues v
                    ON v.id = e.venue_id
                WHERE ea.artist_id = %(source_artist_id)s
                  AND ep.promoter_id = ANY(%(promoter_ids)s)
            )
            SELECT *
            FROM ranked_evidence
            WHERE row_number <= 5
            ORDER BY promoter_id ASC, row_number ASC
            """,
            {
                "source_artist_id": source_artist_id,
                "promoter_ids": promoter_ids,
            },
        )
        return cursor.fetchall()

# Load warm-network evidence rows (co-played path to promoter).
def promoter_warm_network_evidence(
    connection: Connection,
    *,
    source_artist_id: int,
    promoter_ids: list[int],
) -> list[dict]:
    if not promoter_ids:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH source_events AS (
                SELECT DISTINCT event_id
                FROM event_artists
                WHERE artist_id = %(source_artist_id)s
            ),
            co_played_artists AS (
                SELECT DISTINCT
                    ea_shared.artist_id AS co_artist_id,
                    se.event_id AS shared_event_id
                FROM source_events se
                JOIN event_artists ea_shared
                    ON ea_shared.event_id = se.event_id
                WHERE ea_shared.artist_id <> %(source_artist_id)s
            ),
            warm_counts AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT cpa.co_artist_id)::int AS warm_connection_count
                FROM co_played_artists cpa
                JOIN event_artists ea
                    ON ea.artist_id = cpa.co_artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                WHERE (cpa.shared_event_id IS NULL OR e.id <> cpa.shared_event_id)
                  AND ep.promoter_id = ANY(%(promoter_ids)s)
                GROUP BY ep.promoter_id
            ),
            ranked_paths AS (
                SELECT
                    ep.promoter_id,
                    cpa.co_artist_id,
                    a.name AS co_artist_name,
                    cpa.shared_event_id,
                    shared_event.title AS shared_event_title,
                    shared_event.event_date::date AS shared_event_date,
                    e.id AS other_event_id,
                    e.title AS other_event_title,
                    e.event_date::date AS other_event_date,
                    e.venue_id AS other_venue_id,
                    v.name AS other_venue_name,
                    wc.warm_connection_count,
                    row_number() OVER (
                        PARTITION BY ep.promoter_id
                        ORDER BY e.event_date DESC NULLS LAST, e.id DESC
                    ) AS row_number
                FROM co_played_artists cpa
                JOIN artists a
                    ON a.id = cpa.co_artist_id
                JOIN event_artists ea
                    ON ea.artist_id = cpa.co_artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                JOIN warm_counts wc
                    ON wc.promoter_id = ep.promoter_id
                LEFT JOIN events shared_event
                    ON shared_event.id = cpa.shared_event_id
                LEFT JOIN venues v
                    ON v.id = e.venue_id
                WHERE (cpa.shared_event_id IS NULL OR e.id <> cpa.shared_event_id)
                  AND ep.promoter_id = ANY(%(promoter_ids)s)
            )
            SELECT *
            FROM ranked_paths
            WHERE row_number <= 5
            ORDER BY promoter_id ASC, row_number ASC
            """,
            {
                "source_artist_id": source_artist_id,
                "promoter_ids": promoter_ids,
            },
        )
        return cursor.fetchall()

# Load manual trusted-artist evidence rows (source -> trusted artist -> event -> promoter).
def promoter_manual_connection_evidence(
    connection: Connection,
    *,
    promoter_manual_artist_ids: dict[int, list[int]],
) -> list[dict]:
    flattened_pairs: list[tuple[int, int]] = []
    for promoter_id, artist_ids in promoter_manual_artist_ids.items():
        for artist_id in artist_ids:
            flattened_pairs.append((int(promoter_id), int(artist_id)))

    if not flattened_pairs:
        return []

    promoter_ids = [pair[0] for pair in flattened_pairs]
    artist_ids = [pair[1] for pair in flattened_pairs]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH requested_pairs AS (
                SELECT DISTINCT *
                FROM unnest(%(promoter_ids)s::bigint[], %(artist_ids)s::bigint[])
                    AS pair(promoter_id, co_artist_id)
            ),
            manual_counts AS (
                SELECT
                    promoter_id,
                    count(DISTINCT co_artist_id)::int AS manual_connection_count
                FROM requested_pairs
                GROUP BY promoter_id
            ),
            ranked_paths AS (
                SELECT
                    rp.promoter_id,
                    rp.co_artist_id,
                    a.name AS co_artist_name,
                    e.id AS event_id,
                    e.title AS event_title,
                    e.event_date::date AS event_date,
                    e.venue_id,
                    v.name AS venue_name,
                    mc.manual_connection_count,
                    row_number() OVER (
                        PARTITION BY rp.promoter_id, rp.co_artist_id
                        ORDER BY e.event_date DESC NULLS LAST, e.id DESC
                    ) AS row_number
                FROM requested_pairs rp
                JOIN artists a
                    ON a.id = rp.co_artist_id
                JOIN event_artists ea
                    ON ea.artist_id = rp.co_artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                   AND ep.promoter_id = rp.promoter_id
                JOIN manual_counts mc
                    ON mc.promoter_id = rp.promoter_id
                LEFT JOIN venues v
                    ON v.id = e.venue_id
            )
            SELECT *
            FROM ranked_paths
            WHERE row_number <= 2
            ORDER BY promoter_id ASC, co_artist_name ASC, event_date DESC NULLS LAST, event_id DESC
            """,
            {
                "promoter_ids": promoter_ids,
                "artist_ids": artist_ids,
            },
        )
        return cursor.fetchall()
