from __future__ import annotations

from datetime import date as DateValue
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg import Connection

from app.db import get_db
from app.embeddings import EmbeddingConfig, EntityType, rank_similar_embeddings
from app.recommendation_scoring import (
    DEFAULT_RECOMMENDATION_SCORING,
    SemanticArtistTagScoringConfig,
    final_recommendation_score,
    hybrid_graph_score,
    is_similarity_candidate_eligible,
    semantic_artist_scoring_from_env,
    semantic_artist_tag_scoring_from_env,
)
from app.style_tags import extract_style_tags, style_overlap_score


app = FastAPI(title="Berlin Scene Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.index import router
app.include_router(router, prefix="/api")

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
    name: str
    genres: list[str] = Field(default_factory=list)
    eventCount: int | None = None
    date: DateValue | None = None
    startDate: DateValue | None = None
    endDate: DateValue | None = None
    district: str | None = None
    sceneFocus: str | None = None


class GraphLink(BaseModel):
    source: str
    target: str
    relationship: str
    weight: int = 1
    evidenceType: str | None = None
    style: Literal["solid", "dashed", "dotted"] | None = None
    strength: float | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]


class SimilarityItem(BaseModel):
    id: int
    type: Literal["artist", "event"]
    name: str
    score: float
    semanticScore: float
    graphScore: float
    reasons: list[str] = Field(default_factory=list)
    date: DateValue | None = None
    venueName: str | None = None


class SimilarityResponse(BaseModel):
    entityId: int
    entityType: Literal["artist", "event"]
    model: str
    dimensions: int
    similar: list[SimilarityItem]


class SemanticArtistItem(BaseModel):
    id: int
    type: Literal["artist"] = "artist"
    name: str
    score: float
    embeddingScore: float
    styleScore: float
    tagScore: float = 0.0
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    sharedStyles: list[str] = Field(default_factory=list)
    sharedTags: dict[str, list[str]] = Field(default_factory=dict)
    debug: dict[str, object] | None = None


class SemanticArtistResponse(BaseModel):
    entityId: int
    entityType: Literal["artist"] = "artist"
    model: str
    dimensions: int
    similar: list[SemanticArtistItem]


class ArtistRecommendationItem(BaseModel):
    id: int
    type: Literal["artist"] = "artist"
    name: str
    score: float
    semanticScore: float
    graphScore: float
    embeddingScore: float
    styleScore: float
    tagScore: float = 0.0
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    semanticBreakdown: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    sharedStyles: list[str] = Field(default_factory=list)
    sharedTags: dict[str, list[str]] = Field(default_factory=dict)


class ArtistRecommendationResponse(BaseModel):
    entityId: int
    entityType: Literal["artist"] = "artist"
    model: str
    dimensions: int
    recommendations: list[ArtistRecommendationItem]


class RecommendationEvidenceItem(BaseModel):
    type: Literal["semantic_bridge", "direct_connection", "warm_network", "event_similarity"]
    path: str


class PromoterRecommendationItem(BaseModel):
    id: int
    type: Literal["promoter"] = "promoter"
    name: str
    score: float
    semanticScore: float
    strengthScore: float
    activityScore: float
    recencyScore: float
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    matchedArtistCount: int
    eventCount: int
    latestEventDate: DateValue | None = None
    status: str | None = None
    warmConnectionCount: int = 0
    directConnectionCount: int = 0
    evidence: list[RecommendationEvidenceItem] = Field(default_factory=list)


class PromoterRecommendationResponse(BaseModel):
    entityId: int
    entityType: Literal["artist"] = "artist"
    model: str
    dimensions: int
    recommendations: list[PromoterRecommendationItem]
    graph: GraphResponse


class ArtistTagItem(BaseModel):
    type: Literal["style", "label", "collective", "role", "residency", "alias"]
    value: str
    source: str
    confidence: float
    extractor: str
    evidence: str | None = None


class ArtistTagsResponse(BaseModel):
    artistId: int
    artistName: str
    tags: list[ArtistTagItem]


EntityKind = Literal["artist", "event"]
FeedbackValue = Literal["positive", "negative", "hidden"]


class RecommendationFeedbackRequest(BaseModel):
    sourceEntityType: EntityKind
    sourceEntityId: int
    candidateEntityType: EntityKind
    candidateEntityId: int
    feedback: FeedbackValue
    reason: str | None = None


class RecommendationFeedbackItem(BaseModel):
    id: int
    sourceEntityType: EntityKind
    sourceEntityId: int
    candidateEntityType: EntityKind
    candidateEntityId: int
    feedback: FeedbackValue
    reason: str | None = None
    createdAt: datetime
    updatedAt: datetime


class RecommendationFeedbackResponse(BaseModel):
    feedback: list[RecommendationFeedbackItem]


def graph_node_id(node_type: str, entity_id: int) -> str:
    return f"{node_type}-{entity_id}"


def feedback_item_from_row(row: dict) -> RecommendationFeedbackItem:
    return RecommendationFeedbackItem(
        id=row["id"],
        sourceEntityType=row["source_entity_type"],
        sourceEntityId=row["source_entity_id"],
        candidateEntityType=row["candidate_entity_type"],
        candidateEntityId=row["candidate_entity_id"],
        feedback=row["feedback"],
        reason=row["reason"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def ensure_feedback_entity_exists(
    connection: Connection,
    *,
    entity_type: EntityKind,
    entity_id: int,
) -> None:
    table_name = "artists" if entity_type == "artist" else "events"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE id = %s", (entity_id,))
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail=f"{entity_type} {entity_id} not found",
            )


def recommendation_item_metadata(
    connection: Connection,
    entity_type: EntityType,
    entity_ids: list[int],
) -> dict[int, dict]:
    if not entity_ids:
        return {}

    if entity_type == "event":
        query = """
            SELECT
                e.id,
                e.title AS name,
                e.event_date::date AS date,
                v.name AS venue_name
            FROM events e
            LEFT JOIN venues v
                ON v.id = e.venue_id
            WHERE e.id = ANY(%s)
        """
    else:
        query = """
            SELECT
                id,
                name,
                NULL::date AS date,
                NULL::text AS venue_name
            FROM artists
            WHERE id = ANY(%s)
        """

    with connection.cursor() as cursor:
        cursor.execute(query, (entity_ids,))
        rows = cursor.fetchall()

    return {row["id"]: row for row in rows}


def artist_semantic_metadata(
    connection: Connection,
    artist_ids: list[int],
) -> dict[int, dict]:
    if not artist_ids:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                name,
                COALESCE(biography_normalized, biography, '') AS biography
            FROM artists
            WHERE id = ANY(%s)
            """,
            (artist_ids,),
        )
        rows = cursor.fetchall()

        cursor.execute("SELECT to_regclass('public.artist_extracted_tags') AS table_name")
        has_extracted_tags = cursor.fetchone()["table_name"] is not None

        extracted_tags: dict[int, dict[str, list[str]]] = {}
        if has_extracted_tags:
            cursor.execute(
                """
                SELECT artist_id, tag_type, tag_value
                FROM artist_extracted_tags
                WHERE artist_id = ANY(%s)
                  AND confidence >= 0.6
                ORDER BY tag_type ASC, tag_value ASC
                """,
                (artist_ids,),
            )
            for tag in cursor.fetchall():
                artist_tags = extracted_tags.setdefault(tag["artist_id"], {})
                values = artist_tags.setdefault(tag["tag_type"], [])
                normalized = tag["tag_value"].strip()
                if normalized and normalized not in values:
                    values.append(normalized)

    metadata = {
        row["id"]: {
            "id": row["id"],
            "name": row["name"],
            "tags": extracted_tags.get(row["id"], {}),
            "style_tags": sorted(
                set(extract_style_tags(row["biography"]))
                | set(extracted_tags.get(row["id"], {}).get("style", []))
            ),
        }
        for row in rows
    }
    return metadata


def tag_overlap_score(source_tags: list[str], candidate_tags: list[str], cap: int = 1) -> float:
    if not source_tags or not candidate_tags:
        return 0.0

    overlap = {tag.casefold() for tag in source_tags} & {tag.casefold() for tag in candidate_tags}
    return min(len(overlap) / cap, 1.0)


def shared_tag_values(source_tags: list[str], candidate_tags: list[str]) -> list[str]:
    candidate_lookup = {tag.casefold(): tag for tag in candidate_tags}
    return sorted(
        candidate_lookup[key]
        for key in ({tag.casefold() for tag in source_tags} & set(candidate_lookup.keys()))
    )


def extracted_tag_score(
    source_tags: dict[str, list[str]],
    candidate_tags: dict[str, list[str]],
    config: SemanticArtistTagScoringConfig,
) -> float:
    label_overlap = tag_overlap_score(source_tags.get("label", []), candidate_tags.get("label", []))
    collective_overlap = tag_overlap_score(
        source_tags.get("collective", []),
        candidate_tags.get("collective", []),
    )
    residency_overlap = tag_overlap_score(
        source_tags.get("residency", []),
        candidate_tags.get("residency", []),
    )
    role_overlap = tag_overlap_score(
        source_tags.get("role", []),
        candidate_tags.get("role", []),
        cap=config.role_overlap_cap,
    )

    return (
        config.label_weight * label_overlap
        + config.collective_weight * collective_overlap
        + config.residency_weight * residency_overlap
        + config.role_weight * role_overlap
    )


def shared_extracted_tags(
    source_tags: dict[str, list[str]],
    candidate_tags: dict[str, list[str]],
) -> dict[str, list[str]]:
    shared: dict[str, list[str]] = {}
    for tag_type in ("label", "collective", "role", "residency", "alias"):
        values = shared_tag_values(source_tags.get(tag_type, []), candidate_tags.get(tag_type, []))
        if values:
            shared[tag_type] = values
    return shared


def build_artist_semantic_candidates(
    connection: Connection,
    *,
    artist_id: int,
    debug: bool = False,
) -> tuple[dict, list[dict]]:
    config = EmbeddingConfig.from_env()
    scoring_config = semantic_artist_scoring_from_env()
    tag_scoring_config = semantic_artist_tag_scoring_from_env()
    source, ranked = rank_similar_embeddings(
        connection,
        entity_type="artist",
        entity_id=artist_id,
        config=config,
        limit=10_000,
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {config.model} embedding found for artist {artist_id}. "
                "Run scripts/generate_embeddings.py first."
            ),
        )

    candidate_ids = [item["entity_id"] for item in ranked]
    metadata = artist_semantic_metadata(connection, [artist_id, *candidate_ids])
    source_metadata = metadata.get(artist_id)
    if source_metadata is None:
        raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

    source_tags = source_metadata["style_tags"]
    source_extracted_tags = source_metadata["tags"]
    scored = []
    for item in ranked:
        candidate_metadata = metadata.get(item["entity_id"])
        if candidate_metadata is None:
            continue

        candidate_tags = candidate_metadata["style_tags"]
        shared_styles = sorted(set(source_tags) & set(candidate_tags))
        style_score = style_overlap_score(source_tags, candidate_tags)
        tag_score = extracted_tag_score(
            source_extracted_tags,
            candidate_metadata["tags"],
            tag_scoring_config,
        )
        shared_tags = shared_extracted_tags(source_extracted_tags, candidate_metadata["tags"])
        embedding_score = item["score"]
        score_breakdown = {
            "embedding": scoring_config.embedding_weight * embedding_score,
            "style": scoring_config.style_weight * style_score,
            "tag": scoring_config.tag_weight * tag_score,
        }
        scored.append(
            {
                "entity_id": item["entity_id"],
                "name": candidate_metadata["name"],
                "score": sum(score_breakdown.values()),
                "embedding_score": embedding_score,
                "style_score": style_score,
                "tag_score": tag_score,
                "score_breakdown": score_breakdown,
                "shared_styles": shared_styles,
                "shared_tags": shared_tags,
                "debug": {
                    "sourceStyles": source_tags,
                    "candidateStyles": candidate_tags,
                    "sourceTags": source_extracted_tags,
                    "candidateTags": candidate_metadata["tags"],
                }
                if debug
                else None,
            }
        )

    return source, sorted(
        scored,
        key=lambda candidate: (-candidate["score"], candidate["entity_id"]),
    )


def semantic_artist_reasons(item: dict) -> list[str]:
    reasons = []
    shared_styles = item["shared_styles"]
    shared_tags = item["shared_tags"]
    if shared_styles:
        reasons.append(f"{len(shared_styles)} shared styles: {', '.join(shared_styles[:5])}")

    for tag_type in ("label", "collective", "residency"):
        values = shared_tags.get(tag_type, [])
        if values:
            reasons.append(f"{len(values)} shared {tag_type} tags: {', '.join(values[:3])}")

    if item["embedding_score"] >= 0.60:
        reasons.append("semantic profile match")
    if not reasons:
        reasons.append("semantic similarity")
    return reasons[:3]


def build_artist_semantic_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    debug: bool = False,
) -> SemanticArtistResponse:
    source, scored = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=debug,
    )
    similar = [
        SemanticArtistItem(
            id=item["entity_id"],
            name=item["name"],
            score=item["score"],
            embeddingScore=item["embedding_score"],
            styleScore=item["style_score"],
            tagScore=item["tag_score"],
            scoreBreakdown=item["score_breakdown"],
            sharedStyles=item["shared_styles"],
            sharedTags=item["shared_tags"],
            debug=item["debug"],
        )
        for item in scored[:limit]
    ]

    return SemanticArtistResponse(
        entityId=artist_id,
        model=source["model"],
        dimensions=source["dimensions"],
        similar=similar,
    )


def build_artist_recommendation_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
) -> ArtistRecommendationResponse:
    source, semantic_candidates = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=False,
    )
    candidate_ids = [item["entity_id"] for item in semantic_candidates]
    features = recommendation_feature_sets(connection, "artist", [artist_id, *candidate_ids])
    features = apply_artist_indirect_features(
        connection,
        entity_type="artist",
        entity_id=artist_id,
        candidate_ids=candidate_ids,
        features=features,
    )
    source_features = features.get(artist_id, {})

    recommendations = []
    for item in semantic_candidates:
        candidate_features = features.get(item["entity_id"], {})
        graph_score, graph_reasons = hybrid_graph_score("artist", source_features, candidate_features)
        final_score = final_recommendation_score(
            item["score"],
            graph_score,
            DEFAULT_RECOMMENDATION_SCORING,
        )
        score_breakdown = {
            "semantic": DEFAULT_RECOMMENDATION_SCORING.semantic_weight * item["score"],
            "graph": DEFAULT_RECOMMENDATION_SCORING.graph_weight * graph_score,
        }
        reasons = [
            *semantic_artist_reasons(item),
            *graph_reasons,
        ][:5]
        recommendations.append(
            ArtistRecommendationItem(
                id=item["entity_id"],
                name=item["name"],
                score=final_score,
                semanticScore=item["score"],
                graphScore=graph_score,
                embeddingScore=item["embedding_score"],
                styleScore=item["style_score"],
                tagScore=item["tag_score"],
                scoreBreakdown=score_breakdown,
                semanticBreakdown=item["score_breakdown"],
                reasons=reasons,
                sharedStyles=item["shared_styles"],
                sharedTags=item["shared_tags"],
            )
        )

    return ArtistRecommendationResponse(
        entityId=artist_id,
        model=source["model"],
        dimensions=source["dimensions"],
        recommendations=sorted(
            recommendations,
            key=lambda recommendation: (-recommendation.score, recommendation.id),
        )[:limit],
    )


def date_recency_score(value: DateValue | datetime | None) -> float:
    if value is None:
        return 0.0
    event_date = value.date() if isinstance(value, datetime) else value
    age_days = max((DateValue.today() - event_date).days, 0)
    return max(0.0, 1.0 - age_days / 365)


def promoter_recommendation_reasons(row: dict) -> list[str]:
    reasons = [
        f"{row['matched_artist_count']} similar artists connected",
        f"{row['event_count']} related promoter events",
    ]
    if row["latest_event_date"] is not None:
        reasons.append(f"latest related event on {row['latest_event_date']}")
    return reasons


def promoter_recommendation_graph(
    *,
    source_artist_id: int,
    source_artist_name: str,
    recommendations: list[PromoterRecommendationItem],
    evidence_rows: list[dict],
) -> GraphResponse:
    nodes: dict[str, GraphNode] = {
        graph_node_id("artist", source_artist_id): GraphNode(
            id=graph_node_id("artist", source_artist_id),
            entityId=source_artist_id,
            type="artist",
            name=source_artist_name,
        )
    }
    links: list[GraphLink] = []
    seen_links: set[tuple[str, str, str]] = set()

    for recommendation in recommendations:
        promoter_node_id = graph_node_id("promoter", recommendation.id)
        nodes[promoter_node_id] = GraphNode(
            id=promoter_node_id,
            entityId=recommendation.id,
            type="promoter",
            name=recommendation.name,
            eventCount=recommendation.eventCount,
        )

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

    for row in evidence_rows:
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

    return GraphResponse(nodes=list(nodes.values()), links=links)


def promoter_recommendation_evidence(
    connection: Connection,
    *,
    promoter_ids: list[int],
    semantic_scores: dict[int, float],
) -> list[dict]:
    if not promoter_ids:
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


def build_artist_promoter_recommendation_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
) -> PromoterRecommendationResponse:
    source, semantic_candidates = build_artist_semantic_candidates(
        connection,
        artist_id=artist_id,
        debug=False,
    )
    source_metadata = recommendation_item_metadata(connection, "artist", [artist_id])
    source_artist = source_metadata.get(artist_id)
    if source_artist is None:
        raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

    candidate_scores = {
        item["entity_id"]: item["score"]
        for item in semantic_candidates[:500]
        if item["score"] > 0
    }
    if not candidate_scores:
        return PromoterRecommendationResponse(
            entityId=artist_id,
            model=source["model"],
            dimensions=source["dimensions"],
            recommendations=[],
            graph=GraphResponse(nodes=[], links=[]),
        )

    artist_ids = list(candidate_scores.keys())
    artist_scores = [candidate_scores[artist_id] for artist_id in artist_ids]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH semantic_candidates AS (
                SELECT *
                FROM unnest(%(artist_ids)s::bigint[], %(artist_scores)s::double precision[])
                    AS candidate(artist_id, semantic_score)
            )
            SELECT
                p.id,
                p.name,
                count(DISTINCT sc.artist_id)::int AS matched_artist_count,
                count(DISTINCT e.id)::int AS event_count,
                max(sc.semantic_score)::double precision AS semantic_score,
                max(e.event_date)::date AS latest_event_date
            FROM semantic_candidates sc
            JOIN event_artists ea
                ON ea.artist_id = sc.artist_id
            JOIN events e
                ON e.id = ea.event_id
            JOIN event_promoters ep
                ON ep.event_id = e.id
            JOIN promoters p
                ON p.id = ep.promoter_id
            GROUP BY p.id, p.name
            ORDER BY semantic_score DESC, event_count DESC, p.id ASC
            LIMIT 200
            """,
            {
                "artist_ids": artist_ids,
                "artist_scores": artist_scores,
            },
        )
        rows = cursor.fetchall()

    recommendations = []
    for row in rows:
        strength_score = min(
            (row["matched_artist_count"] / 5 * 0.6) + (row["event_count"] / 20 * 0.4),
            1.0,
        )
        activity_score = min(row["event_count"] / 25, 1.0)
        recency_score = date_recency_score(row["latest_event_date"])
        score_breakdown = {
            "semantic": 0.45 * row["semantic_score"],
            "strength": 0.25 * strength_score,
            "activity": 0.20 * activity_score,
            "recency": 0.10 * recency_score,
        }
        recommendations.append(
            PromoterRecommendationItem(
                id=row["id"],
                name=row["name"],
                score=sum(score_breakdown.values()),
                semanticScore=row["semantic_score"],
                strengthScore=strength_score,
                activityScore=activity_score,
                recencyScore=recency_score,
                scoreBreakdown=score_breakdown,
                reasons=promoter_recommendation_reasons(row),
                matchedArtistCount=row["matched_artist_count"],
                eventCount=row["event_count"],
                latestEventDate=row["latest_event_date"],
                status="new_relevant",
                warmConnectionCount=0,
                directConnectionCount=0,
                evidence=[
                    RecommendationEvidenceItem(
                        type="semantic_bridge",
                        path="Source Artist -> Similar Artist -> Event -> Promoter",
                    )
                ],
            )
        )

    recommendations = sorted(
        recommendations,
        key=lambda recommendation: (-recommendation.score, recommendation.id),
    )[:limit]
    evidence = promoter_recommendation_evidence(
        connection,
        promoter_ids=[recommendation.id for recommendation in recommendations],
        semantic_scores=candidate_scores,
    )

    return PromoterRecommendationResponse(
        entityId=artist_id,
        model=source["model"],
        dimensions=source["dimensions"],
        recommendations=recommendations,
        graph=promoter_recommendation_graph(
            source_artist_id=artist_id,
            source_artist_name=source_artist["name"],
            recommendations=recommendations,
            evidence_rows=evidence,
        ),
    )


def as_id_set(values: list[int | None] | None) -> set[int]:
    return {int(value) for value in values or [] if value is not None}


def recommendation_feature_sets(
    connection: Connection,
    entity_type: EntityType,
    entity_ids: list[int],
) -> dict[int, dict[str, set[int]]]:
    if not entity_ids:
        return {}

    if entity_type == "event":
        query = """
            SELECT
                e.id,
                array_remove(array_agg(DISTINCT ea.artist_id), NULL) AS artists,
                array_remove(array_agg(DISTINCT ep.promoter_id), NULL) AS promoters,
                array_remove(array_agg(DISTINCT eg.genre_id), NULL) AS genres,
                array_remove(ARRAY[e.venue_id], NULL) AS venues
            FROM events e
            LEFT JOIN event_artists ea
                ON ea.event_id = e.id
            LEFT JOIN event_promoters ep
                ON ep.event_id = e.id
            LEFT JOIN event_genres eg
                ON eg.event_id = e.id
            WHERE e.id = ANY(%s)
            GROUP BY e.id, e.venue_id
        """
    else:
        query = """
            SELECT
                a.id,
                array_remove(array_agg(DISTINCT ea.event_id), NULL) AS events,
                array_remove(array_agg(DISTINCT e.venue_id), NULL) AS venues,
                array_remove(array_agg(DISTINCT ep.promoter_id), NULL) AS promoters,
                array_remove(array_agg(DISTINCT eg.genre_id), NULL) AS genres
            FROM artists a
            LEFT JOIN event_artists ea
                ON ea.artist_id = a.id
            LEFT JOIN events e
                ON e.id = ea.event_id
            LEFT JOIN event_promoters ep
                ON ep.event_id = ea.event_id
            LEFT JOIN event_genres eg
                ON eg.event_id = ea.event_id
            WHERE a.id = ANY(%s)
            GROUP BY a.id
        """

    with connection.cursor() as cursor:
        cursor.execute(query, (entity_ids,))
        rows = cursor.fetchall()

    return {
        row["id"]: {
            key: as_id_set(row.get(key))
            for key in ("artists", "events", "venues", "promoters", "genres")
        }
        for row in rows
    }


def artist_indirect_feature_sets(
    connection: Connection,
    *,
    source_artist_id: int,
    candidate_artist_ids: list[int],
) -> dict[int, dict[str, set[int]]]:
    if not candidate_artist_ids:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT event_id
            FROM event_artists
            WHERE artist_id = %s
            """,
            (source_artist_id,),
        )
        source_event_ids = [row["event_id"] for row in cursor.fetchall()]

    if not source_event_ids:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH source_events AS (
                SELECT unnest(%(source_event_ids)s::bigint[]) AS event_id
            )
            SELECT
                a.id,
                array_remove(array_agg(DISTINCT ea.event_id), NULL) AS events,
                array_remove(array_agg(DISTINCT e.venue_id), NULL) AS venues,
                array_remove(array_agg(DISTINCT ep.promoter_id), NULL) AS promoters,
                array_remove(array_agg(DISTINCT eg.genre_id), NULL) AS genres
            FROM artists a
            LEFT JOIN event_artists ea
                ON ea.artist_id = a.id
                AND NOT EXISTS (
                    SELECT 1
                    FROM source_events se
                    WHERE se.event_id = ea.event_id
                )
            LEFT JOIN events e
                ON e.id = ea.event_id
            LEFT JOIN event_promoters ep
                ON ep.event_id = ea.event_id
            LEFT JOIN event_genres eg
                ON eg.event_id = ea.event_id
            WHERE a.id = ANY(%(candidate_artist_ids)s)
               OR a.id = %(source_artist_id)s
            GROUP BY a.id
            """,
            {
                "source_artist_id": source_artist_id,
                "source_event_ids": source_event_ids,
                "candidate_artist_ids": candidate_artist_ids,
            },
        )
        rows = cursor.fetchall()

    return {
        row["id"]: {
            key: as_id_set(row.get(key))
            for key in ("events", "venues", "promoters", "genres")
        }
        for row in rows
    }


def apply_artist_indirect_features(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    candidate_ids: list[int],
    features: dict[int, dict[str, set[int]]],
) -> dict[int, dict[str, set[int]]]:
    if entity_type != "artist":
        return features
    if entity_id not in features:
        return features

    indirect_features = artist_indirect_feature_sets(
        connection,
        source_artist_id=entity_id,
        candidate_artist_ids=candidate_ids,
    )
    if entity_id in indirect_features:
        for key in ("venues", "promoters", "genres"):
            features[entity_id][key] = indirect_features[entity_id].get(key, set())

    for candidate_id in candidate_ids:
        if candidate_id not in features or candidate_id not in indirect_features:
            continue
        for key in ("venues", "promoters", "genres"):
            features[candidate_id][key] = indirect_features[candidate_id].get(key, set())

    return features


def rerank_similar_entities(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    ranked: list[dict],
    limit: int,
) -> list[dict]:
    candidate_ids = [item["entity_id"] for item in ranked]
    features = recommendation_feature_sets(connection, entity_type, [entity_id, *candidate_ids])
    features = apply_artist_indirect_features(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        candidate_ids=candidate_ids,
        features=features,
    )
    source_features = features.get(entity_id)
    if not source_features:
        return ranked[:limit]

    rescored = []
    for item in ranked:
        candidate_features = features.get(item["entity_id"])
        if not candidate_features:
            continue

        graph_score, reasons = hybrid_graph_score(entity_type, source_features, candidate_features)
        semantic_score = item["score"]
        if not is_similarity_candidate_eligible(
            entity_type,
            semantic_score,
            graph_score,
            DEFAULT_RECOMMENDATION_SCORING,
        ):
            continue

        final_score = final_recommendation_score(
            semantic_score,
            graph_score,
            DEFAULT_RECOMMENDATION_SCORING,
        )
        rescored.append(
            {
                **item,
                "score": final_score,
                "semantic_score": semantic_score,
                "graph_score": graph_score,
                "reasons": reasons or ["semantic similarity"],
            }
        )

    return sorted(
        rescored,
        key=lambda candidate: (-candidate["score"], candidate["entity_id"]),
    )[:limit]


def build_similarity_response(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    limit: int,
) -> SimilarityResponse:
    config = EmbeddingConfig.from_env()
    candidate_limit = 10_000 if entity_type == "artist" else max(limit * 10, 100)
    source, ranked = rank_similar_embeddings(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        config=config,
        limit=candidate_limit,
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {config.model} embedding found for {entity_type} {entity_id}. "
                "Run scripts/generate_embeddings.py first."
            ),
        )

    reranked = rerank_similar_entities(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        ranked=ranked,
        limit=limit,
    )
    metadata = recommendation_item_metadata(
        connection,
        entity_type,
        [item["entity_id"] for item in reranked],
    )
    similar = [
        SimilarityItem(
            id=item["entity_id"],
            type=entity_type,
            name=metadata[item["entity_id"]]["name"],
            score=item["score"],
            semanticScore=item["semantic_score"],
            graphScore=item["graph_score"],
            reasons=item["reasons"],
            date=metadata[item["entity_id"]]["date"],
            venueName=metadata[item["entity_id"]]["venue_name"],
        )
        for item in reranked
        if item["entity_id"] in metadata
    ]

    return SimilarityResponse(
        entityId=entity_id,
        entityType=entity_type,
        model=source["model"],
        dimensions=source["dimensions"],
        similar=similar,
    )


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


@app.get(
    "/api/semantic/artists/{artist_id}",
    response_model=SemanticArtistResponse,
    response_model_exclude_none=True,
)
async def semantic_artists(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    debug: bool = Query(default=False),
    connection: Connection = Depends(get_db),
) -> SemanticArtistResponse:
    return build_artist_semantic_response(
        connection,
        artist_id=artist_id,
        limit=limit,
        debug=debug,
    )


@app.get(
    "/api/artists/{artist_id}/tags",
    response_model=ArtistTagsResponse,
    response_model_exclude_none=True,
)
async def artist_tags(
    artist_id: int,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, alias="minConfidence"),
    connection: Connection = Depends(get_db),
) -> ArtistTagsResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name
            FROM artists
            WHERE id = %s
            """,
            (artist_id,),
        )
        artist = cursor.fetchone()
        if artist is None:
            raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

        cursor.execute(
            """
            SELECT
                tag_type,
                tag_value,
                source,
                confidence,
                extractor,
                evidence
            FROM artist_extracted_tags
            WHERE artist_id = %s
              AND confidence >= %s
            ORDER BY tag_type ASC, confidence DESC, tag_value ASC
            """,
            (artist_id, min_confidence),
        )
        tags = cursor.fetchall()

    return ArtistTagsResponse(
        artistId=artist["id"],
        artistName=artist["name"],
        tags=[
            ArtistTagItem(
                type=tag["tag_type"],
                value=tag["tag_value"],
                source=tag["source"],
                confidence=tag["confidence"],
                extractor=tag["extractor"],
                evidence=tag["evidence"],
            )
            for tag in tags
        ],
    )


@app.post(
    "/api/recommendation-feedback",
    response_model=RecommendationFeedbackItem,
    response_model_exclude_none=True,
)
async def upsert_recommendation_feedback(
    request: RecommendationFeedbackRequest,
    connection: Connection = Depends(get_db),
) -> RecommendationFeedbackItem:
    ensure_feedback_entity_exists(
        connection,
        entity_type=request.sourceEntityType,
        entity_id=request.sourceEntityId,
    )
    ensure_feedback_entity_exists(
        connection,
        entity_type=request.candidateEntityType,
        entity_id=request.candidateEntityId,
    )

    reason = request.reason.strip() if request.reason else None
    if reason == "":
        reason = None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO recommendation_feedback (
                source_entity_type,
                source_entity_id,
                candidate_entity_type,
                candidate_entity_id,
                feedback,
                reason
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (
                source_entity_type,
                source_entity_id,
                candidate_entity_type,
                candidate_entity_id
            )
            DO UPDATE SET
                feedback = EXCLUDED.feedback,
                reason = EXCLUDED.reason,
                updated_at = CURRENT_TIMESTAMP
            RETURNING
                id,
                source_entity_type,
                source_entity_id,
                candidate_entity_type,
                candidate_entity_id,
                feedback,
                reason,
                created_at,
                updated_at
            """,
            (
                request.sourceEntityType,
                request.sourceEntityId,
                request.candidateEntityType,
                request.candidateEntityId,
                request.feedback,
                reason,
            ),
        )
        row = cursor.fetchone()

    return feedback_item_from_row(row)


@app.get(
    "/api/recommendation-feedback",
    response_model=RecommendationFeedbackResponse,
    response_model_exclude_none=True,
)
async def list_recommendation_feedback(
    source_entity_type: EntityKind | None = Query(default=None, alias="sourceEntityType"),
    source_entity_id: int | None = Query(default=None, ge=1, alias="sourceEntityId"),
    candidate_entity_type: EntityKind | None = Query(default=None, alias="candidateEntityType"),
    candidate_entity_id: int | None = Query(default=None, ge=1, alias="candidateEntityId"),
    connection: Connection = Depends(get_db),
) -> RecommendationFeedbackResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                source_entity_type,
                source_entity_id,
                candidate_entity_type,
                candidate_entity_id,
                feedback,
                reason,
                created_at,
                updated_at
            FROM recommendation_feedback
            WHERE (%s::text IS NULL OR source_entity_type = %s)
              AND (%s::bigint IS NULL OR source_entity_id = %s)
              AND (%s::text IS NULL OR candidate_entity_type = %s)
              AND (%s::bigint IS NULL OR candidate_entity_id = %s)
            ORDER BY updated_at DESC, id DESC
            LIMIT 500
            """,
            (
                source_entity_type,
                source_entity_type,
                source_entity_id,
                source_entity_id,
                candidate_entity_type,
                candidate_entity_type,
                candidate_entity_id,
                candidate_entity_id,
            ),
        )
        rows = cursor.fetchall()

    return RecommendationFeedbackResponse(
        feedback=[feedback_item_from_row(row) for row in rows],
    )


@app.get(
    "/api/recommendations/events/{event_id}",
    response_model=SimilarityResponse,
    response_model_exclude_none=True,
    include_in_schema=False,
)
async def recommend_events_alias(
    event_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    connection: Connection = Depends(get_db),
) -> SimilarityResponse:
    return build_similarity_response(
        connection,
        entity_type="event",
        entity_id=event_id,
        limit=limit,
    )


@app.get(
    "/api/recommendations/artists/{artist_id}/promoters",
    response_model=PromoterRecommendationResponse,
    response_model_exclude_none=True,
)
async def recommend_promoters_for_artist(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    connection: Connection = Depends(get_db),
) -> PromoterRecommendationResponse:
    return build_artist_promoter_recommendation_response(
        connection,
        artist_id=artist_id,
        limit=limit,
    )


@app.get(
    "/api/recommendations/artists/{artist_id}",
    response_model=ArtistRecommendationResponse,
    response_model_exclude_none=True,
)
async def recommend_artists(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    connection: Connection = Depends(get_db),
) -> ArtistRecommendationResponse:
    return build_artist_recommendation_response(
        connection,
        artist_id=artist_id,
        limit=limit,
    )


@app.get(
    "/api/graph",
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
