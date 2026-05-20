from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from app.embeddings import EntityType


GraphFeature = Literal["artists", "events", "venues", "promoters", "genres"]


@dataclass(frozen=True)
class GraphFeatureWeight:
    label: str
    feature: GraphFeature
    weight: float
    cap: int | None = None
    boolean: bool = False


@dataclass(frozen=True)
class RecommendationScoringConfig:
    semantic_weight: float
    graph_weight: float
    artist_semantic_only_threshold: float
    event_graph_weights: tuple[GraphFeatureWeight, ...]
    artist_graph_weights: tuple[GraphFeatureWeight, ...]


@dataclass(frozen=True)
class SemanticArtistScoringConfig:
    embedding_weight: float
    style_weight: float
    tag_weight: float


@dataclass(frozen=True)
class SemanticArtistTagScoringConfig:
    label_weight: float
    collective_weight: float
    residency_weight: float
    role_weight: float
    role_overlap_cap: int


@dataclass(frozen=True)
class PromoterRecommendationScoringConfig:
    semantic_weight: float
    strength_weight: float
    direct_connection_weight: float
    warm_network_weight: float
    activity_weight: float
    recency_weight: float
    strength_matched_artist_weight: float
    strength_event_weight: float
    strength_matched_artist_cap: int
    strength_event_cap: int
    direct_connection_cap: int
    warm_connection_cap: int
    activity_event_cap: int
    existing_partner_direct_min: int
    warm_relevant_connection_min: int
    direct_edge_strength_min: float
    direct_edge_strength_max: float
    warm_edge_strength_min: float
    warm_edge_strength_max: float


DEFAULT_SEMANTIC_ARTIST_SCORING = SemanticArtistScoringConfig(
    embedding_weight=0.65,
    style_weight=0.25,
    tag_weight=0.10,
)


DEFAULT_SEMANTIC_ARTIST_TAG_SCORING = SemanticArtistTagScoringConfig(
    label_weight=0.35,
    collective_weight=0.30,
    residency_weight=0.25,
    role_weight=0.10,
    role_overlap_cap=2,
)


DEFAULT_RECOMMENDATION_SCORING = RecommendationScoringConfig(
    semantic_weight=0.65,
    graph_weight=0.35,
    artist_semantic_only_threshold=0.80,
    event_graph_weights=(
        GraphFeatureWeight("shared artists", "artists", 0.45, cap=3),
        GraphFeatureWeight("shared promoters", "promoters", 0.25, cap=2),
        GraphFeatureWeight("same venue", "venues", 0.20, boolean=True),
        GraphFeatureWeight("shared genres", "genres", 0.10, cap=3),
    ),
    artist_graph_weights=(
        GraphFeatureWeight("played same events", "events", 0.40, cap=2),
        GraphFeatureWeight("shared promoters", "promoters", 0.25, cap=3),
        GraphFeatureWeight("shared venues", "venues", 0.20, cap=3),
        GraphFeatureWeight("shared genres", "genres", 0.15, cap=3),
    ),
)


DEFAULT_PROMOTER_RECOMMENDATION_SCORING = PromoterRecommendationScoringConfig(
    semantic_weight=0.35,
    strength_weight=0.18,
    direct_connection_weight=0.15,
    warm_network_weight=0.12,
    activity_weight=0.12,
    recency_weight=0.08,
    strength_matched_artist_weight=0.60,
    strength_event_weight=0.40,
    strength_matched_artist_cap=5,
    strength_event_cap=20,
    direct_connection_cap=3,
    warm_connection_cap=3,
    activity_event_cap=25,
    existing_partner_direct_min=1,
    warm_relevant_connection_min=1,
    direct_edge_strength_min=0.8,
    direct_edge_strength_max=1.0,
    warm_edge_strength_min=0.5,
    warm_edge_strength_max=0.8,
)


def normalized_weights(values: tuple[float, ...]) -> tuple[float, ...]:
    if any(value < 0 for value in values):
        raise ValueError("Scoring weights must be non-negative")

    total = sum(values)
    if total <= 0:
        raise ValueError("At least one scoring weight must be greater than zero")

    return tuple(value / total for value in values)


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def semantic_artist_scoring_from_env() -> SemanticArtistScoringConfig:
    weights = normalized_weights(
        (
            env_float(
                "SEMANTIC_ARTIST_EMBEDDING_WEIGHT",
                DEFAULT_SEMANTIC_ARTIST_SCORING.embedding_weight,
            ),
            env_float(
                "SEMANTIC_ARTIST_STYLE_WEIGHT",
                DEFAULT_SEMANTIC_ARTIST_SCORING.style_weight,
            ),
            env_float(
                "SEMANTIC_ARTIST_TAG_WEIGHT",
                DEFAULT_SEMANTIC_ARTIST_SCORING.tag_weight,
            ),
        )
    )

    return SemanticArtistScoringConfig(
        embedding_weight=weights[0],
        style_weight=weights[1],
        tag_weight=weights[2],
    )


def semantic_artist_tag_scoring_from_env() -> SemanticArtistTagScoringConfig:
    weights = normalized_weights(
        (
            env_float(
                "SEMANTIC_ARTIST_TAG_LABEL_WEIGHT",
                DEFAULT_SEMANTIC_ARTIST_TAG_SCORING.label_weight,
            ),
            env_float(
                "SEMANTIC_ARTIST_TAG_COLLECTIVE_WEIGHT",
                DEFAULT_SEMANTIC_ARTIST_TAG_SCORING.collective_weight,
            ),
            env_float(
                "SEMANTIC_ARTIST_TAG_RESIDENCY_WEIGHT",
                DEFAULT_SEMANTIC_ARTIST_TAG_SCORING.residency_weight,
            ),
            env_float(
                "SEMANTIC_ARTIST_TAG_ROLE_WEIGHT",
                DEFAULT_SEMANTIC_ARTIST_TAG_SCORING.role_weight,
            ),
        )
    )
    role_overlap_cap = env_int(
        "SEMANTIC_ARTIST_TAG_ROLE_OVERLAP_CAP",
        DEFAULT_SEMANTIC_ARTIST_TAG_SCORING.role_overlap_cap,
    )
    if role_overlap_cap <= 0:
        raise ValueError("SEMANTIC_ARTIST_TAG_ROLE_OVERLAP_CAP must be greater than zero")

    return SemanticArtistTagScoringConfig(
        label_weight=weights[0],
        collective_weight=weights[1],
        residency_weight=weights[2],
        role_weight=weights[3],
        role_overlap_cap=role_overlap_cap,
    )


def promoter_recommendation_scoring_from_env() -> PromoterRecommendationScoringConfig:
    weights = normalized_weights(
        (
            env_float(
                "PROMOTER_REC_SEMANTIC_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.semantic_weight,
            ),
            env_float(
                "PROMOTER_REC_STRENGTH_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.strength_weight,
            ),
            env_float(
                "PROMOTER_REC_DIRECT_CONNECTION_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.direct_connection_weight,
            ),
            env_float(
                "PROMOTER_REC_WARM_NETWORK_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.warm_network_weight,
            ),
            env_float(
                "PROMOTER_REC_ACTIVITY_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.activity_weight,
            ),
            env_float(
                "PROMOTER_REC_RECENCY_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.recency_weight,
            ),
        )
    )
    strength_weights = normalized_weights(
        (
            env_float(
                "PROMOTER_REC_STRENGTH_MATCHED_ARTIST_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.strength_matched_artist_weight,
            ),
            env_float(
                "PROMOTER_REC_STRENGTH_EVENT_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.strength_event_weight,
            ),
        )
    )

    strength_matched_artist_cap = env_int(
        "PROMOTER_REC_STRENGTH_MATCHED_ARTIST_CAP",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.strength_matched_artist_cap,
    )
    strength_event_cap = env_int(
        "PROMOTER_REC_STRENGTH_EVENT_CAP",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.strength_event_cap,
    )
    direct_connection_cap = env_int(
        "PROMOTER_REC_DIRECT_CONNECTION_CAP",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.direct_connection_cap,
    )
    warm_connection_cap = env_int(
        "PROMOTER_REC_WARM_CONNECTION_CAP",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.warm_connection_cap,
    )
    activity_event_cap = env_int(
        "PROMOTER_REC_ACTIVITY_EVENT_CAP",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.activity_event_cap,
    )
    existing_partner_direct_min = env_int(
        "PROMOTER_REC_EXISTING_PARTNER_DIRECT_MIN",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.existing_partner_direct_min,
    )
    warm_relevant_connection_min = env_int(
        "PROMOTER_REC_WARM_RELEVANT_CONNECTION_MIN",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.warm_relevant_connection_min,
    )
    direct_edge_strength_min = env_float(
        "PROMOTER_REC_DIRECT_EDGE_STRENGTH_MIN",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.direct_edge_strength_min,
    )
    direct_edge_strength_max = env_float(
        "PROMOTER_REC_DIRECT_EDGE_STRENGTH_MAX",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.direct_edge_strength_max,
    )
    warm_edge_strength_min = env_float(
        "PROMOTER_REC_WARM_EDGE_STRENGTH_MIN",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.warm_edge_strength_min,
    )
    warm_edge_strength_max = env_float(
        "PROMOTER_REC_WARM_EDGE_STRENGTH_MAX",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.warm_edge_strength_max,
    )

    if strength_matched_artist_cap <= 0:
        raise ValueError("PROMOTER_REC_STRENGTH_MATCHED_ARTIST_CAP must be greater than zero")
    if strength_event_cap <= 0:
        raise ValueError("PROMOTER_REC_STRENGTH_EVENT_CAP must be greater than zero")
    if direct_connection_cap <= 0:
        raise ValueError("PROMOTER_REC_DIRECT_CONNECTION_CAP must be greater than zero")
    if warm_connection_cap <= 0:
        raise ValueError("PROMOTER_REC_WARM_CONNECTION_CAP must be greater than zero")
    if activity_event_cap <= 0:
        raise ValueError("PROMOTER_REC_ACTIVITY_EVENT_CAP must be greater than zero")
    if existing_partner_direct_min <= 0:
        raise ValueError("PROMOTER_REC_EXISTING_PARTNER_DIRECT_MIN must be greater than zero")
    if warm_relevant_connection_min <= 0:
        raise ValueError("PROMOTER_REC_WARM_RELEVANT_CONNECTION_MIN must be greater than zero")
    if not (0.0 <= direct_edge_strength_min <= 1.0):
        raise ValueError("PROMOTER_REC_DIRECT_EDGE_STRENGTH_MIN must be between 0 and 1")
    if not (0.0 <= direct_edge_strength_max <= 1.0):
        raise ValueError("PROMOTER_REC_DIRECT_EDGE_STRENGTH_MAX must be between 0 and 1")
    if direct_edge_strength_min > direct_edge_strength_max:
        raise ValueError(
            "PROMOTER_REC_DIRECT_EDGE_STRENGTH_MIN must be less than or equal to "
            "PROMOTER_REC_DIRECT_EDGE_STRENGTH_MAX"
        )
    if not (0.0 <= warm_edge_strength_min <= 1.0):
        raise ValueError("PROMOTER_REC_WARM_EDGE_STRENGTH_MIN must be between 0 and 1")
    if not (0.0 <= warm_edge_strength_max <= 1.0):
        raise ValueError("PROMOTER_REC_WARM_EDGE_STRENGTH_MAX must be between 0 and 1")
    if warm_edge_strength_min > warm_edge_strength_max:
        raise ValueError(
            "PROMOTER_REC_WARM_EDGE_STRENGTH_MIN must be less than or equal to "
            "PROMOTER_REC_WARM_EDGE_STRENGTH_MAX"
        )

    return PromoterRecommendationScoringConfig(
        semantic_weight=weights[0],
        strength_weight=weights[1],
        direct_connection_weight=weights[2],
        warm_network_weight=weights[3],
        activity_weight=weights[4],
        recency_weight=weights[5],
        strength_matched_artist_weight=strength_weights[0],
        strength_event_weight=strength_weights[1],
        strength_matched_artist_cap=strength_matched_artist_cap,
        strength_event_cap=strength_event_cap,
        direct_connection_cap=direct_connection_cap,
        warm_connection_cap=warm_connection_cap,
        activity_event_cap=activity_event_cap,
        existing_partner_direct_min=existing_partner_direct_min,
        warm_relevant_connection_min=warm_relevant_connection_min,
        direct_edge_strength_min=direct_edge_strength_min,
        direct_edge_strength_max=direct_edge_strength_max,
        warm_edge_strength_min=warm_edge_strength_min,
        warm_edge_strength_max=warm_edge_strength_max,
    )


def semantic_artist_score(
    embedding_score: float,
    style_score: float,
    tag_score: float,
    config: SemanticArtistScoringConfig | None = None,
) -> float:
    config = config or DEFAULT_SEMANTIC_ARTIST_SCORING
    return (
        config.embedding_weight * embedding_score
        + config.style_weight * style_score
        + config.tag_weight * tag_score
    )


def capped_overlap_score(left: set[int], right: set[int], cap: int) -> float:
    if not left or not right:
        return 0.0
    return min(len(left & right) / cap, 1.0)


def boolean_overlap_score(left: set[int], right: set[int]) -> float:
    return 1.0 if left and right and bool(left & right) else 0.0


def graph_feature_score(
    weight: GraphFeatureWeight,
    source: dict[str, set[int]],
    candidate: dict[str, set[int]],
) -> float:
    source_values = source.get(weight.feature, set())
    candidate_values = candidate.get(weight.feature, set())

    if weight.boolean:
        return weight.weight * boolean_overlap_score(source_values, candidate_values)
    if weight.cap is None:
        raise ValueError(f"Graph feature {weight.label} needs either cap or boolean=True")
    return weight.weight * capped_overlap_score(source_values, candidate_values, weight.cap)


def graph_feature_reason(
    weight: GraphFeatureWeight,
    source: dict[str, set[int]],
    candidate: dict[str, set[int]],
) -> str:
    overlap_count = len(source.get(weight.feature, set()) & candidate.get(weight.feature, set()))
    if weight.boolean:
        return weight.label
    return f"{overlap_count} {weight.label}"


def hybrid_graph_score(
    entity_type: EntityType,
    source: dict[str, set[int]],
    candidate: dict[str, set[int]],
    config: RecommendationScoringConfig = DEFAULT_RECOMMENDATION_SCORING,
) -> tuple[float, list[str]]:
    weights = config.event_graph_weights if entity_type == "event" else config.artist_graph_weights
    components = [
        (
            graph_feature_score(weight, source, candidate),
            graph_feature_reason(weight, source, candidate),
        )
        for weight in weights
    ]

    reasons = [
        reason
        for score, reason in sorted(components, key=lambda item: -item[0])
        if score > 0
    ][:3]
    return sum(score for score, _ in components), reasons


def final_recommendation_score(
    semantic_score: float,
    graph_score: float,
    config: RecommendationScoringConfig = DEFAULT_RECOMMENDATION_SCORING,
) -> float:
    return config.semantic_weight * semantic_score + config.graph_weight * graph_score


def is_similarity_candidate_eligible(
    entity_type: EntityType,
    semantic_score: float,
    graph_score: float,
    config: RecommendationScoringConfig = DEFAULT_RECOMMENDATION_SCORING,
) -> bool:
    if entity_type != "artist":
        return True

    return graph_score > 0 or semantic_score >= config.artist_semantic_only_threshold
