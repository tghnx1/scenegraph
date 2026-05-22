from __future__ import annotations

from datetime import date as DateValue
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg import Connection

from app.db import get_db
from app.embeddings import EmbeddingConfig, EntityType, cosine_similarity, rank_similar_embeddings
from app.recommendation_scoring import (
    DEFAULT_RECOMMENDATION_SCORING,
    PromoterRecommendationScoringConfig,
    SemanticArtistTagScoringConfig,
    final_recommendation_score,
    hybrid_graph_score,
    is_similarity_candidate_eligible,
    promoter_recommendation_scoring_from_env,
    recommendation_scoring_from_env,
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

from app.search_routes import router as search_router
app.include_router(search_router, prefix="/api")

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

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: int | None = None  #sometimes there is an int, sometimes nothing. If not provided => None
    username: str | None = None
    access_token: str | None = None

dummy_users = [
    {"id": 1, "username": "maksim", "password": "12345"},
    {"id": 2, "username": "howard", "password": "12345"},
    {"id": 3, "username": "tarcisio", "password": "12345"},
    {"id": 4, "username": "herold", "password": "12345"},
    {"id": 5, "username": "aaron", "password": "12345"}
]

class SimilarityItem(BaseModel):
    id: int
    type: Literal["artist", "event"]
    name: str
    score: float
    semanticScore: float
    graphScore: float
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    date: DateValue | None = None
    venueName: str | None = None
    promoterId: int | None = None
    promoterName: str | None = None
    debug: dict[str, object] | None = None


class SimilarityResponse(BaseModel):
    entityId: int
    entityType: Literal["artist", "event"]
    model: str
    dimensions: int
    similar: list[SimilarityItem]
    debug: dict[str, object] | None = None


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
    debug: dict[str, object] | None = None


class PromoterRecommendationResponse(BaseModel):
    entityId: int
    entityType: Literal["artist"] = "artist"
    model: str
    dimensions: int
    recommendations: list[PromoterRecommendationItem]
    graph: GraphResponse
    debug: dict[str, object] | None = None


class ArtistSimilarEventItem(BaseModel):
    id: int
    type: Literal["event"] = "event"
    name: str
    score: float
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    eventDate: DateValue | None = None
    venueName: str | None = None
    promoterId: int | None = None
    promoterName: str | None = None
    sourceEventId: int
    sourceEventName: str
    sourceEventDate: DateValue | None = None
    reasons: list[str] = Field(default_factory=list)
    debug: dict[str, object] | None = None


class ArtistSimilarEventsResponse(BaseModel):
    entityId: int
    entityType: Literal["artist"] = "artist"
    model: str
    dimensions: int | None = None
    similarEvents: list[ArtistSimilarEventItem]
    debug: dict[str, object] | None = None


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
                e.ra_event_id,
                e.title AS name,
                e.event_date::date AS date,
                v.name AS venue_name,
                promoter.promoter_id,
                promoter.promoter_name
            FROM events e
            LEFT JOIN venues v
                ON v.id = e.venue_id
            LEFT JOIN LATERAL (
                SELECT
                    p.id AS promoter_id,
                    p.name AS promoter_name
                FROM event_promoters ep
                JOIN promoters p
                    ON p.id = ep.promoter_id
                WHERE ep.event_id = e.id
                ORDER BY p.id ASC
                LIMIT 1
            ) promoter
                ON true
            WHERE e.id = ANY(%s)
        """
    else:
        query = """
            SELECT
                id,
                NULL::text AS ra_event_id,
                name,
                NULL::date AS date,
                NULL::text AS venue_name,
                NULL::bigint AS promoter_id,
                NULL::text AS promoter_name
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
    reasons = []
    if row["direct_connection_count"] > 0:
        reasons.append(f"{row['direct_connection_count']} direct artist-promoter events")
    if row["warm_connection_count"] > 0:
        reasons.append(f"{row['warm_connection_count']} co-played artists connected")
    if row["matched_artist_count"] > 0:
        reasons.append(f"{row['matched_artist_count']} similar artists connected")
    if row["event_similarity_count"] > 0:
        reasons.append(f"{row['event_similarity_count']} similar promoter events")
    if row["event_count"] > 0:
        reasons.append(f"{row['event_count']} related promoter events")
    if row["latest_event_date"] is not None:
        reasons.append(f"latest related event on {row['latest_event_date']}")
    return reasons[:4]


def promoter_recommendation_status(
    row: dict,
    scoring_config: PromoterRecommendationScoringConfig,
) -> str:
    if row["direct_connection_count"] >= scoring_config.existing_partner_direct_min:
        return "existing_partner"
    if row["warm_connection_count"] >= scoring_config.warm_relevant_connection_min:
        return "warm_relevant"
    return "new_relevant"


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


def promoter_recommendation_graph(
    *,
    source_artist_id: int,
    source_artist_name: str,
    recommendations: list[PromoterRecommendationItem],
    semantic_evidence_rows: list[dict],
    direct_evidence_rows: list[dict],
    warm_evidence_rows: list[dict],
    event_similarity_evidence_rows: list[dict],
    scoring_config: PromoterRecommendationScoringConfig,
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
            graph_node_id("artist", source_artist_id),
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
        promoter_node_id = graph_node_id("promoter", row["promoter_id"])
        co_artist_node_id = graph_node_id("artist", row["co_artist_id"])
        shared_event_node_id = graph_node_id("event", row["shared_event_id"])
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
            entityId=row["shared_event_id"],
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
            graph_node_id("artist", source_artist_id),
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

    for row in event_similarity_evidence_rows:
        promoter_node_id = graph_node_id("promoter", row["promoter_id"])
        source_event_node_id = graph_node_id("event", row["source_event_id"])
        promoter_event_node_id = graph_node_id("event", row["promoter_event_id"])
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

    return GraphResponse(nodes=list(nodes.values()), links=links)


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
            """
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
                WHERE e.id <> cpa.shared_event_id
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
                JOIN events shared_event
                    ON shared_event.id = cpa.shared_event_id
                LEFT JOIN venues v
                    ON v.id = e.venue_id
                WHERE e.id <> cpa.shared_event_id
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


def artist_similar_events_scored_rows(
    connection: Connection,
    *,
    source_artist_id: int,
    limit: int,
    exclude_same_promoter: bool,
    scoring_config: PromoterRecommendationScoringConfig,
    collect_debug: bool = False,
) -> tuple[list[dict], int | None, dict[str, int]]:
    same_promoter_filtered_count = 0
    if collect_debug and exclude_same_promoter:
        same_promoter_filtered_count = artist_event_similarity_same_promoter_filtered_count(
            connection,
            source_artist_id=source_artist_id,
            scoring_config=scoring_config,
        )
    candidate_rows = artist_event_similarity_candidates(
        connection,
        source_artist_id=source_artist_id,
        limit=max(limit, 1),
        exclude_same_promoter=exclude_same_promoter,
        scoring_config=scoring_config,
    )
    if not candidate_rows:
        return [], None, {
            "candidateRowsFetched": 0,
            "samePromoterFiltered": same_promoter_filtered_count,
            "similarityLimitCutoff": 0,
        }

    source_event_ids = sorted({int(row["source_event_id"]) for row in candidate_rows})
    candidate_event_ids = [int(row["candidate_event_id"]) for row in candidate_rows]
    event_styles = event_style_tags_by_id(connection, source_event_ids + candidate_event_ids)
    embedding_scores, embedding_dimensions = event_embedding_similarity_by_candidate(
        connection,
        source_event_ids=source_event_ids,
        candidate_event_ids=candidate_event_ids,
    )

    scored_rows: list[dict] = []
    for row in candidate_rows:
        source_styles = event_styles.get(int(row["source_event_id"]), set())
        candidate_styles = event_styles.get(int(row["candidate_event_id"]), set())
        shared_extracted_genres = sorted(source_styles & candidate_styles)
        extracted_style_score = (
            scoring_config.event_similarity_extracted_style_weight if shared_extracted_genres else 0.0
        )
        symbolic_score = min(float(row["symbolic_score"]) + extracted_style_score, 1.0)
        embedding_score = float(embedding_scores.get(row["candidate_event_id"], 0.0))
        weighted_symbolic_score = scoring_config.event_similarity_symbolic_weight * symbolic_score
        weighted_embedding_score = scoring_config.event_similarity_embedding_weight * embedding_score

        scored_rows.append(
            {
                **row,
                "shared_extracted_genres": shared_extracted_genres,
                "extracted_style_score": extracted_style_score,
                "symbolic_score_final": symbolic_score,
                "embedding_score": embedding_score,
                "weighted_symbolic_score": weighted_symbolic_score,
                "weighted_embedding_score": weighted_embedding_score,
                "total_similarity_score": weighted_symbolic_score + weighted_embedding_score,
            }
        )

    scored_rows.sort(
        key=lambda item: (-item["total_similarity_score"], item["candidate_event_id"]),
    )
    return scored_rows[:limit], embedding_dimensions, {
        "candidateRowsFetched": len(candidate_rows),
        "samePromoterFiltered": same_promoter_filtered_count,
        "similarityLimitCutoff": max(len(scored_rows) - limit, 0),
    }


def event_embedding_similarity_by_candidate(
    connection: Connection,
    *,
    source_event_ids: list[int],
    candidate_event_ids: list[int],
) -> tuple[dict[int, float], int | None]:
    if not source_event_ids or not candidate_event_ids:
        return {}, None

    config = EmbeddingConfig.from_env()
    target_event_ids = set(source_event_ids) | set(candidate_event_ids)
    dimensions_filter = ""
    params: list[object] = ["event", list(target_event_ids), config.provider_model_key]
    if config.dimensions is not None:
        dimensions_filter = "AND dimensions = %s"
        params.append(config.dimensions)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT DISTINCT ON (entity_id)
                entity_id,
                embedding
            FROM entity_embeddings
            WHERE entity_type = %s
              AND entity_id = ANY(%s)
              AND model = %s
              {dimensions_filter}
            ORDER BY entity_id ASC, updated_at DESC
            """,
            params,
        )
        embedding_rows = cursor.fetchall()

    dimensions: int | None = None
    embeddings_by_event_id: dict[int, list[float]] = {}
    for row in embedding_rows:
        event_embedding = row["embedding"]
        if dimensions is None:
            dimensions = len(event_embedding)
        embeddings_by_event_id[int(row["entity_id"])] = event_embedding

    source_vectors = [
        embeddings_by_event_id[event_id]
        for event_id in source_event_ids
        if event_id in embeddings_by_event_id
    ]
    if not source_vectors:
        return {}, dimensions

    scores: dict[int, float] = {}
    for event_id in candidate_event_ids:
        target_vector = embeddings_by_event_id.get(event_id)
        if target_vector is None:
            continue
        scores[event_id] = max(
            max(cosine_similarity(source_vector, target_vector), 0.0) for source_vector in source_vectors
        )
    return scores, dimensions


def event_style_tags_by_id(connection: Connection, event_ids: list[int]) -> dict[int, set[str]]:
    if not event_ids:
        return {}

    unique_event_ids = sorted(set(event_ids))
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                e.id,
                e.title,
                e.description_text,
                e.lineup_raw,
                e.lineup_residual_text
            FROM events e
            WHERE e.id = ANY(%s)
            """,
            (unique_event_ids,),
        )
        rows = cursor.fetchall()

    styles_by_event_id: dict[int, set[str]] = {}
    for row in rows:
        style_input = " ".join(
            part
            for part in (
                row.get("title"),
                row.get("description_text"),
                row.get("lineup_residual_text") or row.get("lineup_raw"),
            )
            if part
        )
        styles_by_event_id[int(row["id"])] = set(extract_style_tags(style_input))
    return styles_by_event_id


def artist_event_similarity_candidates(
    connection: Connection,
    *,
    source_artist_id: int,
    limit: int,
    exclude_same_promoter: bool,
    scoring_config: PromoterRecommendationScoringConfig,
) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH source_events AS (
                SELECT DISTINCT
                    e.id AS source_event_id,
                    e.title AS source_event_title,
                    e.event_date::date AS source_event_date,
                    e.venue_id AS source_venue_id
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                WHERE ea.artist_id = %(source_artist_id)s
            ),
            source_promoters AS (
                SELECT DISTINCT ep.promoter_id
                FROM source_events se
                JOIN event_promoters ep
                    ON ep.event_id = se.source_event_id
            ),
            similarity_paths AS (
                SELECT
                    se.source_event_id,
                    se.source_event_title,
                    se.source_event_date,
                    e.id AS candidate_event_id,
                    e.title AS candidate_event_title,
                    e.event_date::date AS candidate_event_date,
                    e.venue_id AS candidate_venue_id,
                    v.name AS candidate_venue_name,
                    promoter.promoter_id,
                    promoter.promoter_name,
                    CASE WHEN e.venue_id IS NOT NULL AND e.venue_id = se.source_venue_id THEN 1.0 ELSE 0.0 END
                        AS same_venue_score,
                    (
                        SELECT count(DISTINCT eg_source.genre_id)::int
                        FROM event_genres eg_source
                        JOIN event_genres eg_candidate
                          ON eg_candidate.genre_id = eg_source.genre_id
                        WHERE eg_source.event_id = se.source_event_id
                          AND eg_candidate.event_id = e.id
                    ) AS shared_genre_count,
                    (
                        SELECT count(DISTINCT ea_source.artist_id)::int
                        FROM event_artists ea_source
                        JOIN event_artists ea_candidate
                          ON ea_candidate.artist_id = ea_source.artist_id
                        WHERE ea_source.event_id = se.source_event_id
                          AND ea_candidate.event_id = e.id
                          AND ea_source.artist_id <> %(source_artist_id)s
                    ) AS shared_lineup_count
                FROM source_events se
                JOIN events e
                    ON e.id <> se.source_event_id
                LEFT JOIN venues v
                    ON v.id = e.venue_id
                LEFT JOIN LATERAL (
                    SELECT
                        p.id AS promoter_id,
                        p.name AS promoter_name
                    FROM event_promoters ep
                    JOIN promoters p
                        ON p.id = ep.promoter_id
                    WHERE ep.event_id = e.id
                    ORDER BY p.id ASC
                    LIMIT 1
                ) promoter
                    ON true
                WHERE (
                    NOT %(exclude_same_promoter)s
                    OR NOT EXISTS (
                        SELECT 1
                        FROM event_promoters ep_same
                        JOIN source_promoters sp
                            ON sp.promoter_id = ep_same.promoter_id
                        WHERE ep_same.event_id = e.id
                    )
                )
            ),
            scored_paths AS (
                SELECT
                    *,
                    (
                        %(same_venue_weight)s * same_venue_score
                        + %(shared_genre_weight)s * CASE WHEN shared_genre_count > 0 THEN 1.0 ELSE 0.0 END
                        + %(shared_lineup_weight)s * CASE WHEN shared_lineup_count > 0 THEN 1.0 ELSE 0.0 END
                    )::double precision AS symbolic_score
                FROM similarity_paths
            ),
            matched_paths AS (
                SELECT *
                FROM scored_paths
                WHERE symbolic_score > 0
            ),
            ranked_paths AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY candidate_event_id
                        ORDER BY symbolic_score DESC, source_event_date DESC NULLS LAST, source_event_id DESC
                    ) AS row_number
                FROM matched_paths
            )
            SELECT *
            FROM ranked_paths
            WHERE row_number = 1
            ORDER BY symbolic_score DESC, candidate_event_date DESC NULLS LAST, candidate_event_id DESC
            LIMIT %(limit)s
            """,
            {
                "source_artist_id": source_artist_id,
                "limit": max(limit, 1),
                "exclude_same_promoter": exclude_same_promoter,
                "same_venue_weight": scoring_config.event_similarity_same_venue_weight,
                "shared_genre_weight": scoring_config.event_similarity_shared_genre_weight,
                "shared_lineup_weight": scoring_config.event_similarity_shared_lineup_weight,
            },
        )
        return cursor.fetchall()


def artist_event_similarity_same_promoter_filtered_count(
    connection: Connection,
    *,
    source_artist_id: int,
    scoring_config: PromoterRecommendationScoringConfig,
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH source_events AS (
                SELECT DISTINCT
                    e.id AS source_event_id,
                    e.venue_id AS source_venue_id
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                WHERE ea.artist_id = %(source_artist_id)s
            ),
            source_promoters AS (
                SELECT DISTINCT ep.promoter_id
                FROM source_events se
                JOIN event_promoters ep
                    ON ep.event_id = se.source_event_id
            ),
            similarity_paths AS (
                SELECT
                    se.source_event_id,
                    e.id AS candidate_event_id,
                    (
                        CASE WHEN e.venue_id IS NOT NULL AND e.venue_id = se.source_venue_id THEN 1.0 ELSE 0.0 END
                    ) AS same_venue_score,
                    (
                        SELECT count(DISTINCT eg_source.genre_id)::int
                        FROM event_genres eg_source
                        JOIN event_genres eg_candidate
                          ON eg_candidate.genre_id = eg_source.genre_id
                        WHERE eg_source.event_id = se.source_event_id
                          AND eg_candidate.event_id = e.id
                    ) AS shared_genre_count,
                    (
                        SELECT count(DISTINCT ea_source.artist_id)::int
                        FROM event_artists ea_source
                        JOIN event_artists ea_candidate
                          ON ea_candidate.artist_id = ea_source.artist_id
                        WHERE ea_source.event_id = se.source_event_id
                          AND ea_candidate.event_id = e.id
                          AND ea_source.artist_id <> %(source_artist_id)s
                    ) AS shared_lineup_count,
                    EXISTS (
                        SELECT 1
                        FROM event_promoters ep_same
                        JOIN source_promoters sp
                            ON sp.promoter_id = ep_same.promoter_id
                        WHERE ep_same.event_id = e.id
                    ) AS shares_source_promoter
                FROM source_events se
                JOIN events e
                    ON e.id <> se.source_event_id
            ),
            scored_paths AS (
                SELECT
                    *,
                    (
                        %(same_venue_weight)s * same_venue_score
                        + %(shared_genre_weight)s * CASE WHEN shared_genre_count > 0 THEN 1.0 ELSE 0.0 END
                        + %(shared_lineup_weight)s * CASE WHEN shared_lineup_count > 0 THEN 1.0 ELSE 0.0 END
                    )::double precision AS symbolic_score
                FROM similarity_paths
            ),
            matched_paths AS (
                SELECT *
                FROM scored_paths
                WHERE symbolic_score > 0
            ),
            ranked_paths AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY candidate_event_id
                        ORDER BY symbolic_score DESC, source_event_id DESC
                    ) AS row_number
                FROM matched_paths
            )
            SELECT count(*)::int AS filtered_count
            FROM ranked_paths
            WHERE row_number = 1
              AND shares_source_promoter
            """,
            {
                "source_artist_id": source_artist_id,
                "same_venue_weight": scoring_config.event_similarity_same_venue_weight,
                "shared_genre_weight": scoring_config.event_similarity_shared_genre_weight,
                "shared_lineup_weight": scoring_config.event_similarity_shared_lineup_weight,
            },
        )
        row = cursor.fetchone()
    return int(row["filtered_count"]) if row else 0


def build_artist_similar_events_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    debug: bool,
    exclude_same_promoter: bool,
) -> ArtistSimilarEventsResponse:
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

    config = EmbeddingConfig.from_env()
    scoring_config = promoter_recommendation_scoring_from_env()
    scored_rows, embedding_dimensions, similar_events_debug_counts = artist_similar_events_scored_rows(
        connection,
        source_artist_id=artist_id,
        limit=max(limit * 20, 200),
        exclude_same_promoter=exclude_same_promoter,
        scoring_config=scoring_config,
        collect_debug=debug,
    )
    if not scored_rows:
        return ArtistSimilarEventsResponse(
            entityId=artist_id,
            model=config.provider_model_key,
            dimensions=config.dimensions,
            similarEvents=[],
            debug={
                "candidateCounts": {
                    "scoredCandidates": 0,
                    "returnedCandidates": 0,
                },
                "filteredOut": {
                    "samePromoter": similar_events_debug_counts["samePromoterFiltered"],
                    "similarityLimitCutoff": similar_events_debug_counts["similarityLimitCutoff"],
                    "responseLimitCutoff": 0,
                },
            }
            if debug
            else None,
        )

    similar_events: list[ArtistSimilarEventItem] = []
    for row in scored_rows:
        score_breakdown = {
            "symbolic": row["weighted_symbolic_score"],
            "embedding": row["weighted_embedding_score"],
        }
        reasons: list[str] = []
        if row["same_venue_score"] > 0:
            reasons.append("same venue as one of your events")
        if row["shared_genre_count"] > 0:
            reasons.append(f"shares {row['shared_genre_count']} abstract genres with your event history")
        if row["shared_extracted_genres"]:
            reasons.append(
                f"{len(row['shared_extracted_genres'])} shared extracted genres: "
                f"{', '.join(row['shared_extracted_genres'][:5])}"
            )
        if row["shared_lineup_count"] > 0:
            reasons.append(f"shares {row['shared_lineup_count']} lineup artists with your events")
        if row["embedding_score"] >= 0.6:
            reasons.append("high semantic event profile similarity")

        similar_events.append(
            ArtistSimilarEventItem(
                id=row["candidate_event_id"],
                name=row["candidate_event_title"],
                score=row["total_similarity_score"],
                scoreBreakdown=score_breakdown,
                eventDate=row["candidate_event_date"],
                venueName=row["candidate_venue_name"],
                promoterId=row["promoter_id"],
                promoterName=row["promoter_name"],
                sourceEventId=row["source_event_id"],
                sourceEventName=row["source_event_title"],
                sourceEventDate=row["source_event_date"],
                reasons=reasons[:4] if reasons else ["event-level scene overlap"],
                debug={
                    "components": {
                        "sameVenueScore": row["same_venue_score"],
                        "sharedGenreCount": row["shared_genre_count"],
                        "sharedExtractedGenres": row["shared_extracted_genres"],
                        "sharedLineupCount": row["shared_lineup_count"],
                        "extractedStyleScore": row["extracted_style_score"],
                        "symbolicScore": row["symbolic_score_final"],
                        "embeddingScore": row["embedding_score"],
                    },
                    "weights": {
                        "symbolic": scoring_config.event_similarity_symbolic_weight,
                        "embedding": scoring_config.event_similarity_embedding_weight,
                    },
                    "weightedScores": {
                        "symbolic": score_breakdown["symbolic"],
                        "embedding": score_breakdown["embedding"],
                        "total": sum(score_breakdown.values()),
                    },
                }
                if debug
                else None,
            )
        )

    response_limit_cutoff = max(len(similar_events) - limit, 0)
    similar_events = sorted(
        similar_events,
        key=lambda item: (-item.score, item.id),
    )[:limit]
    return ArtistSimilarEventsResponse(
        entityId=artist_id,
        model=config.provider_model_key,
        dimensions=embedding_dimensions if embedding_dimensions is not None else config.dimensions,
        similarEvents=similar_events,
        debug={
            "candidateCounts": {
                "scoredCandidates": similar_events_debug_counts["candidateRowsFetched"],
                "returnedCandidates": len(similar_events),
            },
            "filteredOut": {
                "samePromoter": similar_events_debug_counts["samePromoterFiltered"],
                "similarityLimitCutoff": similar_events_debug_counts["similarityLimitCutoff"],
                "responseLimitCutoff": response_limit_cutoff,
            },
        }
        if debug
        else None,
    )


def build_artist_promoter_recommendation_response(
    connection: Connection,
    *,
    artist_id: int,
    limit: int,
    exclude_existing: bool,
    debug: bool,
) -> PromoterRecommendationResponse:
    scoring_config = promoter_recommendation_scoring_from_env()
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
    artist_ids = list(candidate_scores.keys())
    artist_scores = [candidate_scores[artist_id] for artist_id in artist_ids]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH semantic_candidates AS (
                SELECT *
                FROM unnest(%(artist_ids)s::bigint[], %(artist_scores)s::double precision[])
                    AS candidate(artist_id, semantic_score)
            ),
            source_events AS (
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
            semantic_promoters AS (
                SELECT
                    ep.promoter_id,
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
                GROUP BY ep.promoter_id
            ),
            direct_promoters AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT e.id)::int AS direct_connection_count,
                    max(e.event_date)::date AS latest_direct_event_date
                FROM event_artists ea
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                WHERE ea.artist_id = %(source_artist_id)s
                GROUP BY ep.promoter_id
            ),
            warm_promoters AS (
                SELECT
                    ep.promoter_id,
                    count(DISTINCT cpa.co_artist_id)::int AS warm_connection_count,
                    count(DISTINCT e.id)::int AS warm_event_count,
                    max(e.event_date)::date AS latest_warm_event_date
                FROM co_played_artists cpa
                JOIN event_artists ea
                    ON ea.artist_id = cpa.co_artist_id
                JOIN events e
                    ON e.id = ea.event_id
                JOIN event_promoters ep
                    ON ep.event_id = e.id
                WHERE e.id <> cpa.shared_event_id
                GROUP BY ep.promoter_id
            ),
            candidate_promoters AS (
                SELECT promoter_id FROM semantic_promoters
                UNION
                SELECT promoter_id FROM direct_promoters
                UNION
                SELECT promoter_id FROM warm_promoters
            )
            SELECT
                p.id,
                p.name,
                COALESCE(sp.matched_artist_count, 0)::int AS matched_artist_count,
                GREATEST(
                    COALESCE(sp.event_count, 0),
                    COALESCE(dp.direct_connection_count, 0),
                    COALESCE(wp.warm_event_count, 0)
                )::int AS event_count,
                COALESCE(sp.semantic_score, 0)::double precision AS semantic_score,
                COALESCE(
                    GREATEST(
                        sp.latest_event_date,
                        dp.latest_direct_event_date,
                        wp.latest_warm_event_date
                    ),
                    sp.latest_event_date,
                    dp.latest_direct_event_date,
                    wp.latest_warm_event_date
                )::date AS latest_event_date,
                COALESCE(dp.direct_connection_count, 0)::int AS direct_connection_count,
                COALESCE(wp.warm_connection_count, 0)::int AS warm_connection_count
            FROM candidate_promoters cp
            JOIN promoters p
                ON p.id = cp.promoter_id
            LEFT JOIN semantic_promoters sp
                ON sp.promoter_id = p.id
            LEFT JOIN direct_promoters dp
                ON dp.promoter_id = p.id
            LEFT JOIN warm_promoters wp
                ON wp.promoter_id = p.id
            ORDER BY semantic_score DESC, direct_connection_count DESC, warm_connection_count DESC, event_count DESC, p.id ASC
            LIMIT 200
            """,
            {
                "artist_ids": artist_ids,
                "artist_scores": artist_scores,
                "source_artist_id": artist_id,
            },
        )
        rows = cursor.fetchall()

    similar_event_rows, _, similar_event_debug_counts = artist_similar_events_scored_rows(
        connection,
        source_artist_id=artist_id,
        limit=max(limit * 20, 500),
        exclude_same_promoter=True,
        scoring_config=scoring_config,
        collect_debug=debug,
    )
    event_similarity_stats_by_promoter: dict[int, dict[str, object]] = {}
    for similar_row in similar_event_rows:
        promoter_id = similar_row.get("promoter_id")
        if promoter_id is None:
            continue
        stats = event_similarity_stats_by_promoter.setdefault(
            int(promoter_id),
            {
                "count": 0,
                "symbolic_sum": 0.0,
                "embedding_sum": 0.0,
                "latest_event_date": None,
                "rows": [],
            },
        )
        stats["count"] = int(stats["count"]) + 1
        stats["symbolic_sum"] = float(stats["symbolic_sum"]) + float(similar_row["symbolic_score_final"])
        stats["embedding_sum"] = float(stats["embedding_sum"]) + float(similar_row["embedding_score"])
        candidate_event_date = similar_row.get("candidate_event_date")
        latest_event_date = stats["latest_event_date"]
        if candidate_event_date is not None and (
            latest_event_date is None or candidate_event_date > latest_event_date
        ):
            stats["latest_event_date"] = candidate_event_date
        stats["rows"].append(similar_row)

    existing_promoter_ids = {int(row["id"]) for row in rows}
    additional_promoter_ids = sorted(
        promoter_id
        for promoter_id in event_similarity_stats_by_promoter
        if promoter_id not in existing_promoter_ids
    )
    if additional_promoter_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name
                FROM promoters
                WHERE id = ANY(%s)
                """,
                (additional_promoter_ids,),
            )
            for promoter in cursor.fetchall():
                rows.append(
                    {
                        "id": promoter["id"],
                        "name": promoter["name"],
                        "matched_artist_count": 0,
                        "event_count": 0,
                        "semantic_score": 0.0,
                        "latest_event_date": None,
                        "direct_connection_count": 0,
                        "warm_connection_count": 0,
                    }
                )

    recommendations = []
    exclude_existing_filtered_count = 0
    for row in rows:
        if exclude_existing and row["direct_connection_count"] > 0:
            exclude_existing_filtered_count += 1
            continue
        event_similarity_stats = event_similarity_stats_by_promoter.get(row["id"])
        event_similarity_count = int(event_similarity_stats["count"]) if event_similarity_stats else 0
        event_similarity_average_symbolic_score = (
            float(event_similarity_stats["symbolic_sum"]) / event_similarity_count
            if event_similarity_count > 0 and event_similarity_stats is not None
            else 0.0
        )
        event_similarity_embedding_score = (
            float(event_similarity_stats["embedding_sum"]) / event_similarity_count
            if event_similarity_count > 0 and event_similarity_stats is not None
            else 0.0
        )
        direct_connection_score = min(
            row["direct_connection_count"] / scoring_config.direct_connection_cap,
            1.0,
        )
        warm_network_score = min(
            row["warm_connection_count"] / scoring_config.warm_connection_cap,
            1.0,
        )
        event_similarity_symbolic_score = (
            min(
                event_similarity_count / scoring_config.event_similarity_count_cap,
                1.0,
            )
            * event_similarity_average_symbolic_score
        )
        event_similarity_score = (
            scoring_config.event_similarity_symbolic_weight * event_similarity_symbolic_score
            + scoring_config.event_similarity_embedding_weight * event_similarity_embedding_score
        )
        effective_event_count = max(row["event_count"], event_similarity_count)
        effective_latest_event_date = row["latest_event_date"]
        if event_similarity_stats is not None and event_similarity_stats["latest_event_date"] is not None:
            similarity_latest_event_date = event_similarity_stats["latest_event_date"]
            if effective_latest_event_date is None or similarity_latest_event_date > effective_latest_event_date:
                effective_latest_event_date = similarity_latest_event_date
        strength_score = min(
            (
                row["matched_artist_count"] / scoring_config.strength_matched_artist_cap
                * scoring_config.strength_matched_artist_weight
            )
            + (
                effective_event_count / scoring_config.strength_event_cap
                * scoring_config.strength_event_weight
            ),
            1.0,
        )
        activity_score = min(effective_event_count / scoring_config.activity_event_cap, 1.0)
        recency_score = date_recency_score(effective_latest_event_date)
        row_with_similarity = {
            **row,
            "event_similarity_count": event_similarity_count,
            "event_count": effective_event_count,
            "latest_event_date": effective_latest_event_date,
        }
        direct_weight = 0.0 if exclude_existing else scoring_config.direct_connection_weight
        score_breakdown = {
            "semantic": scoring_config.semantic_weight * row["semantic_score"],
            "strength": scoring_config.strength_weight * strength_score,
            "directConnection": direct_weight * direct_connection_score,
            "warmNetwork": scoring_config.warm_network_weight * warm_network_score,
            "eventSimilarity": scoring_config.event_similarity_weight * event_similarity_score,
            "activity": scoring_config.activity_weight * activity_score,
            "recency": scoring_config.recency_weight * recency_score,
        }
        total_score = sum(score_breakdown.values())
        recommendations.append(
            PromoterRecommendationItem(
                id=row["id"],
                name=row["name"],
                score=total_score,
                semanticScore=row["semantic_score"],
                strengthScore=strength_score,
                activityScore=activity_score,
                recencyScore=recency_score,
                scoreBreakdown=score_breakdown,
                reasons=promoter_recommendation_reasons(row_with_similarity),
                matchedArtistCount=row["matched_artist_count"],
                eventCount=effective_event_count,
                latestEventDate=effective_latest_event_date,
                status=promoter_recommendation_status(row_with_similarity, scoring_config),
                warmConnectionCount=row["warm_connection_count"],
                directConnectionCount=row["direct_connection_count"],
                evidence=promoter_recommendation_item_evidence(row_with_similarity),
                debug={
                    "rawSignals": {
                        "semanticScore": row["semantic_score"],
                        "matchedArtistCount": row["matched_artist_count"],
                        "eventCount": effective_event_count,
                        "directConnectionCount": row["direct_connection_count"],
                        "warmConnectionCount": row["warm_connection_count"],
                        "eventSimilarityCount": event_similarity_count,
                        "eventSimilaritySymbolicScore": event_similarity_symbolic_score,
                        "eventSimilarityEmbeddingScore": event_similarity_embedding_score,
                    },
                    "normalizedScores": {
                        "strength": strength_score,
                        "directConnection": direct_connection_score,
                        "warmNetwork": warm_network_score,
                        "eventSimilarity": event_similarity_score,
                        "activity": activity_score,
                        "recency": recency_score,
                    },
                    "weightedScores": {
                        **score_breakdown,
                        "total": total_score,
                    },
                }
                if debug
                else None,
            )
        )

    recommendation_limit_cutoff = max(len(recommendations) - limit, 0)
    recommendations = sorted(
        recommendations,
        key=lambda recommendation: (-recommendation.score, recommendation.id),
    )[:limit]
    if not recommendations:
        return PromoterRecommendationResponse(
            entityId=artist_id,
            model=source["model"],
            dimensions=source["dimensions"],
            recommendations=[],
            graph=GraphResponse(nodes=[], links=[]),
            debug={
                "candidateCounts": {
                    "sqlPromoterCandidates": len(rows),
                    "eventSimilarityPromotersAdded": len(additional_promoter_ids),
                    "recommendationsBeforeLimit": 0,
                    "returnedRecommendations": 0,
                },
                "filteredOut": {
                    "excludeExisting": exclude_existing_filtered_count,
                    "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                    "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                    "recommendationLimitCutoff": 0,
                },
            }
            if debug
            else None,
        )

    promoter_ids = [recommendation.id for recommendation in recommendations]
    semantic_evidence = promoter_recommendation_evidence(
        connection,
        promoter_ids=promoter_ids,
        semantic_scores=candidate_scores,
    )
    direct_evidence = (
        []
        if exclude_existing
        else promoter_direct_connection_evidence(
            connection,
            source_artist_id=artist_id,
            promoter_ids=promoter_ids,
        )
    )
    warm_evidence = promoter_warm_network_evidence(
        connection,
        source_artist_id=artist_id,
        promoter_ids=promoter_ids,
    )
    event_similarity_evidence: list[dict] = []
    for promoter_id in promoter_ids:
        similarity_stats = event_similarity_stats_by_promoter.get(promoter_id)
        if similarity_stats is None:
            continue
        ranked_rows = sorted(
            similarity_stats["rows"],
            key=lambda item: (-item["total_similarity_score"], item["candidate_event_id"]),
        )[:5]
        for item in ranked_rows:
            event_similarity_evidence.append(
                {
                    "promoter_id": promoter_id,
                    "source_event_id": item["source_event_id"],
                    "source_event_title": item["source_event_title"],
                    "source_event_date": item["source_event_date"],
                    "promoter_event_id": item["candidate_event_id"],
                    "promoter_event_title": item["candidate_event_title"],
                    "promoter_event_date": item["candidate_event_date"],
                    "promoter_venue_id": item["candidate_venue_id"],
                    "promoter_venue_name": item["candidate_venue_name"],
                    "path_similarity": item["symbolic_score_final"],
                }
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
            semantic_evidence_rows=semantic_evidence,
            direct_evidence_rows=direct_evidence,
            warm_evidence_rows=warm_evidence,
            event_similarity_evidence_rows=event_similarity_evidence,
            scoring_config=scoring_config,
        ),
        debug={
            "candidateCounts": {
                "sqlPromoterCandidates": len(rows),
                "eventSimilarityPromotersAdded": len(additional_promoter_ids),
                "recommendationsBeforeLimit": len(recommendations) + recommendation_limit_cutoff,
                "returnedRecommendations": len(recommendations),
            },
            "filteredOut": {
                "excludeExisting": exclude_existing_filtered_count,
                "eventSimilaritySamePromoter": similar_event_debug_counts["samePromoterFiltered"],
                "eventSimilarityLimitCutoff": similar_event_debug_counts["similarityLimitCutoff"],
                "recommendationLimitCutoff": recommendation_limit_cutoff,
            },
        }
        if debug
        else None,
    )


def as_id_set(values: list[int | None] | None) -> set[int]:
    return {int(value) for value in values or [] if value is not None}


def similarity_graph_debug_components(
    *,
    entity_type: EntityType,
    source_features: dict[str, set[int]],
    candidate_features: dict[str, set[int]],
    scoring_config=DEFAULT_RECOMMENDATION_SCORING,
) -> dict[str, dict[str, object]]:
    weights = (
        scoring_config.event_graph_weights
        if entity_type == "event"
        else scoring_config.artist_graph_weights
    )
    components: dict[str, dict[str, object]] = {}
    public_feature_names = {
        "genres": "abstract_genres",
        "extracted_styles": "extracted_genres",
    }
    for weight in weights:
        source_values = source_features.get(weight.feature, set())
        candidate_values = candidate_features.get(weight.feature, set())
        overlap_count = len(source_values & candidate_values)

        if weight.boolean:
            normalized = 1.0 if overlap_count > 0 else 0.0
        else:
            if weight.cap is None:
                raise ValueError(f"Graph feature {weight.label} requires cap for non-boolean scoring")
            normalized = min(overlap_count / weight.cap, 1.0)

        public_key = public_feature_names.get(weight.feature, weight.feature)
        components[public_key] = {
            "weight": weight.weight,
            "overlapCount": overlap_count,
            "cap": weight.cap,
            "boolean": weight.boolean,
            "normalizedScore": normalized,
            "graphContribution": weight.weight * normalized,
        }
    return components


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

    feature_sets = {
        row["id"]: {
            key: as_id_set(row.get(key))
            for key in ("artists", "events", "venues", "promoters", "genres")
        }
        for row in rows
    }
    if entity_type == "event":
        style_tags = event_style_tags_by_id(connection, entity_ids)
        for event_id, styles in style_tags.items():
            if event_id not in feature_sets:
                continue
            feature_sets[event_id]["extracted_styles"] = set(styles)  # type: ignore[assignment]
    return feature_sets


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
    scoring_config=DEFAULT_RECOMMENDATION_SCORING,
) -> tuple[list[dict], dict[str, int]]:
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
    interested_counts: dict[int, int] = {}
    if entity_type == "event":
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, COALESCE(interested_count, 0)::int AS interested_count
                FROM events
                WHERE id = ANY(%s)
                """,
                ([entity_id, *candidate_ids],),
            )
            interested_counts = {int(row["id"]): int(row["interested_count"]) for row in cursor.fetchall()}

    rescored = []
    missing_feature_count = 0
    ineligible_count = 0
    for item in ranked:
        candidate_features = features.get(item["entity_id"])
        if not candidate_features:
            missing_feature_count += 1
            continue

        graph_score, reasons = hybrid_graph_score(
            entity_type,
            source_features,
            candidate_features,
            config=scoring_config,
        )
        semantic_score = item["score"]
        if not is_similarity_candidate_eligible(
            entity_type,
            semantic_score,
            graph_score,
            scoring_config,
        ):
            ineligible_count += 1
            continue

        final_score = final_recommendation_score(
            semantic_score,
            graph_score,
            scoring_config,
        )
        event_rerank_adjustments: dict[str, float] = {}
        if entity_type == "event":
            extracted_overlap = len(source_features.get("extracted_styles", set()) & candidate_features.get("extracted_styles", set()))
            artist_overlap = len(source_features.get("artists", set()) & candidate_features.get("artists", set()))
            if graph_score < scoring_config.event_rerank_min_graph_for_neutral:
                event_rerank_adjustments["lowGraphPenalty"] = -scoring_config.event_rerank_low_graph_penalty
            if extracted_overlap >= scoring_config.event_rerank_extracted_genres_bonus_threshold:
                event_rerank_adjustments["extractedGenresBonus"] = scoring_config.event_rerank_extracted_genres_bonus
            if artist_overlap > 0:
                event_rerank_adjustments["sharedArtistsBonus"] = scoring_config.event_rerank_shared_artists_bonus
            source_interested_count = interested_counts.get(entity_id, 0)
            candidate_interested_count = interested_counts.get(item["entity_id"], 0)
            interested_relative_diff = None
            if source_interested_count > 0 and candidate_interested_count > 0:
                interested_relative_diff = (
                    abs(source_interested_count - candidate_interested_count)
                    / max(source_interested_count, candidate_interested_count)
                )
                if (
                    interested_relative_diff
                    <= scoring_config.event_rerank_interested_match_relative_diff_max
                ):
                    event_rerank_adjustments["interestedCountMatchBonus"] = (
                        scoring_config.event_rerank_interested_count_match_bonus
                    )
                elif (
                    interested_relative_diff
                    >= scoring_config.event_rerank_interested_mismatch_relative_diff_min
                ):
                    event_rerank_adjustments["interestedCountMismatchPenalty"] = (
                        -scoring_config.event_rerank_interested_count_mismatch_penalty
                    )
            final_score += sum(event_rerank_adjustments.values())
        rescored.append(
            {
                **item,
                "score": final_score,
                "semantic_score": semantic_score,
                "graph_score": graph_score,
                "reasons": reasons or ["semantic similarity"],
                "rerank_adjustments": event_rerank_adjustments if entity_type == "event" else {},
                "source_interested_count": interested_counts.get(entity_id) if entity_type == "event" else None,
                "candidate_interested_count": interested_counts.get(item["entity_id"]) if entity_type == "event" else None,
                "interested_count_relative_diff": interested_relative_diff if entity_type == "event" else None,
            }
        )

    sorted_rescored = sorted(
        rescored,
        key=lambda candidate: (-candidate["score"], candidate["entity_id"]),
    )
    debug_counts = {
        "embeddingCandidates": len(ranked),
        "missingFeatures": missing_feature_count,
        "ineligibleByThreshold": ineligible_count,
        "rerankedBeforeLimit": len(sorted_rescored),
        "rerankLimitCutoff": max(len(sorted_rescored) - limit, 0),
    }
    return sorted_rescored[:limit], debug_counts


def build_similarity_response(
    connection: Connection,
    *,
    entity_type: EntityType,
    entity_id: int,
    limit: int,
    debug: bool = False,
    exclude_same_promoter: bool = False,
) -> SimilarityResponse:
    config = EmbeddingConfig.from_env()
    scoring_config = recommendation_scoring_from_env()
    overfetch_multiplier = 25 if entity_type == "event" and exclude_same_promoter else 10
    candidate_limit = 10_000 if entity_type == "artist" else max(limit * overfetch_multiplier, 200)
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

    rerank_limit = max(limit * overfetch_multiplier, 200) if entity_type == "event" else limit
    reranked, rerank_debug_counts = rerank_similar_entities(
        connection,
        entity_type=entity_type,
        entity_id=entity_id,
        ranked=ranked,
        limit=rerank_limit,
        scoring_config=scoring_config,
    )
    metadata = recommendation_item_metadata(
        connection,
        entity_type,
        [item["entity_id"] for item in reranked],
    )
    candidate_ids = [item["entity_id"] for item in reranked if item["entity_id"] in metadata]
    feature_sets = recommendation_feature_sets(connection, entity_type, [entity_id, *candidate_ids])
    source_metadata = recommendation_item_metadata(connection, entity_type, [entity_id]).get(entity_id, {})
    source_features = feature_sets.get(entity_id, {})
    source_promoters = source_features.get("promoters", set())
    filtered_same_promoter_count = 0
    missing_metadata_count = 0
    similar: list[SimilarityItem] = []
    for item in reranked:
        candidate_id = item["entity_id"]
        if candidate_id not in metadata:
            missing_metadata_count += 1
            continue

        candidate_features = feature_sets.get(candidate_id, {})
        if (
            entity_type == "event"
            and exclude_same_promoter
            and bool(source_promoters & candidate_features.get("promoters", set()))
        ):
            filtered_same_promoter_count += 1
            continue

        score_breakdown = {
            "semantic": scoring_config.semantic_weight * item["semantic_score"],
            "graph": scoring_config.graph_weight * item["graph_score"],
        }
        dominant_signal: Literal["semantic", "graph", "mixed"]
        semantic_contribution = score_breakdown["semantic"]
        graph_contribution = score_breakdown["graph"]
        if semantic_contribution > graph_contribution * 1.15:
            dominant_signal = "semantic"
        elif graph_contribution > semantic_contribution * 1.15:
            dominant_signal = "graph"
        else:
            dominant_signal = "mixed"
        graph_components = similarity_graph_debug_components(
            entity_type=entity_type,
            source_features=source_features,
            candidate_features=candidate_features,
            scoring_config=scoring_config,
        )
        shared_extracted_styles: list[str] = []
        if entity_type == "event":
            source_styles = source_features.get("extracted_styles", set())
            candidate_styles = candidate_features.get("extracted_styles", set())
            shared_extracted_styles = sorted(source_styles & candidate_styles)[:10]
        similar.append(
            SimilarityItem(
                id=candidate_id,
                type=entity_type,
                name=metadata[candidate_id]["name"],
                score=item["score"],
                semanticScore=item["semantic_score"],
                graphScore=item["graph_score"],
                scoreBreakdown=score_breakdown,
                reasons=item["reasons"],
                date=metadata[candidate_id]["date"],
                venueName=metadata[candidate_id]["venue_name"],
                promoterId=metadata[candidate_id]["promoter_id"],
                promoterName=metadata[candidate_id]["promoter_name"],
                debug={
                    "raEventId": metadata[candidate_id].get("ra_event_id") if entity_type == "event" else None,
                    "sourceRaEventId": source_metadata.get("ra_event_id") if entity_type == "event" else None,
                    "rawSignals": {
                        "semanticScore": item["semantic_score"],
                        "graphScore": item["graph_score"],
                    },
                    "graphComponents": graph_components,
                    "sharedExtractedGenres": shared_extracted_styles if entity_type == "event" else None,
                    "sourceInterestedCount": item.get("source_interested_count") if entity_type == "event" else None,
                    "candidateInterestedCount": item.get("candidate_interested_count")
                    if entity_type == "event"
                    else None,
                    "interestedCountRelativeDiff": item.get("interested_count_relative_diff")
                    if entity_type == "event"
                    else None,
                    "dominantSignal": dominant_signal,
                    "rerankAdjustments": item.get("rerank_adjustments") if entity_type == "event" else None,
                    "weightedScores": {
                        **score_breakdown,
                        "adjustments": sum((item.get("rerank_adjustments") or {}).values()),
                        "total": item["score"],
                    },
                }
                if debug
                else None,
            )
        )

    response_limit_cutoff = max(len(similar) - limit, 0)
    similar = similar[:limit]

    return SimilarityResponse(
        entityId=entity_id,
        entityType=entity_type,
        model=source["model"],
        dimensions=source["dimensions"],
        similar=similar,
        debug={
            "candidateCounts": {
                "embeddingCandidates": len(ranked),
                "rerankedCandidates": len(reranked),
                "returnedCandidates": len(similar),
            },
            "filteredOut": {
                "missingFeatures": rerank_debug_counts["missingFeatures"],
                "ineligibleByThreshold": rerank_debug_counts["ineligibleByThreshold"],
                "rerankLimitCutoff": rerank_debug_counts["rerankLimitCutoff"],
                "missingMetadata": missing_metadata_count,
                "samePromoter": filtered_same_promoter_count,
                "responseLimitCutoff": response_limit_cutoff,
            },
        }
        if debug
        else None,
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

#when POST /api/login arrives, expect LoginRequest input, execute async login function, return LoginResponse output 
#response_model = LoginResponse means FastAPI should validate and document the returned JSON using LoginResponse  
#async means this function can pause while waiting without blocking whole server
@app.post("/api/login", response_model=LoginResponse, response_model_exclude_none=True)        
async def login(login_data: LoginRequest) -> LoginResponse:
    for user in dummy_users:
        if (user["username"] == login_data.username and user["password"] == login_data.password):
            return LoginResponse(
                success=True,
                message="Login successful",
                user_id=user["id"],
                username=user["username"],
                access_token="dummy-token",
            )
    return LoginResponse(
        success=False,
        message="Invalid username or password"
    )


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
    debug: bool = Query(default=False),
    exclude_same_promoter: bool = Query(default=True),
    connection: Connection = Depends(get_db),
) -> SimilarityResponse:
    return build_similarity_response(
        connection,
        entity_type="event",
        entity_id=event_id,
        limit=limit,
        debug=debug,
        exclude_same_promoter=exclude_same_promoter,
    )


@app.get(
    "/api/recommendations/events/{event_id}/similar-events",
    response_model=SimilarityResponse,
    response_model_exclude_none=True,
)
async def recommend_similar_events(
    event_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    debug: bool = Query(default=False),
    exclude_same_promoter: bool = Query(default=True),
    connection: Connection = Depends(get_db),
) -> SimilarityResponse:
    return build_similarity_response(
        connection,
        entity_type="event",
        entity_id=event_id,
        limit=limit,
        debug=debug,
        exclude_same_promoter=exclude_same_promoter,
    )


@app.get(
    "/api/recommendations/artists/{artist_id}/similar-events",
    response_model=ArtistSimilarEventsResponse,
    response_model_exclude_none=True,
)
async def recommend_similar_events_for_artist(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    debug: bool = Query(default=False),
    exclude_same_promoter: bool = Query(default=True),
    connection: Connection = Depends(get_db),
) -> ArtistSimilarEventsResponse:
    return build_artist_similar_events_response(
        connection,
        artist_id=artist_id,
        limit=limit,
        debug=debug,
        exclude_same_promoter=exclude_same_promoter,
    )


@app.get(
    "/api/recommendations/artists/{artist_id}/promoters",
    response_model=PromoterRecommendationResponse,
    response_model_exclude_none=True,
)
async def recommend_promoters_for_artist(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    exclude_existing: bool = Query(default=True),
    debug: bool = Query(default=False),
    connection: Connection = Depends(get_db),
) -> PromoterRecommendationResponse:
    return build_artist_promoter_recommendation_response(
        connection,
        artist_id=artist_id,
        limit=limit,
        exclude_existing=exclude_existing,
        debug=debug,
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
