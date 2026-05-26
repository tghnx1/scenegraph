from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from app.embeddings import EntityType


GraphFeature = Literal["artists", "events", "venues", "promoters", "genres", "extracted_styles"]


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
    event_graph_min_threshold: float
    event_semantic_if_weak_graph_threshold: float
    event_rerank_min_graph_for_neutral: float
    event_rerank_low_graph_penalty: float
    event_rerank_extracted_genres_bonus_threshold: int
    event_rerank_extracted_genres_bonus: float
    event_rerank_shared_artists_bonus: float
    event_rerank_interested_match_relative_diff_max: float
    event_rerank_interested_mismatch_relative_diff_min: float
    event_rerank_interested_count_match_bonus: float
    event_rerank_interested_count_mismatch_penalty: float
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
    event_similarity_weight: float
    scale_fit_weight: float
    activity_weight: float
    recency_weight: float
    strength_matched_artist_weight: float
    strength_event_weight: float
    strength_matched_artist_cap: int
    strength_event_cap: int
    direct_connection_cap: int
    warm_connection_cap: int
    manual_warm_connection_cap: int
    manual_warm_boost_weight: float
    event_similarity_count_cap: int
    event_similarity_min_total_score: float
    event_similarity_per_promoter_limit: int
    event_similarity_symbolic_weight: float
    event_similarity_embedding_weight: float
    event_similarity_same_venue_weight: float
    event_similarity_shared_genre_weight: float
    event_similarity_shared_lineup_weight: float
    event_similarity_extracted_style_weight: float
    activity_event_cap: int
    existing_partner_direct_min: int
    warm_relevant_connection_min: int
    direct_edge_strength_min: float
    direct_edge_strength_max: float
    warm_edge_strength_min: float
    warm_edge_strength_max: float
    event_similarity_edge_strength_min: float
    event_similarity_edge_strength_max: float
    scale_fit_alpha: float
    scale_fit_tau: float
    sql_candidate_limit: int
    semantic_artist_pool_limit: int
    event_similarity_overfetch_multiplier: int
    event_similarity_overfetch_min: int


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
    event_graph_min_threshold=0.08,
    event_semantic_if_weak_graph_threshold=0.74,
    event_rerank_min_graph_for_neutral=0.12,
    event_rerank_low_graph_penalty=0.03,
    event_rerank_extracted_genres_bonus_threshold=2,
    event_rerank_extracted_genres_bonus=0.02,
    event_rerank_shared_artists_bonus=0.02,
    event_rerank_interested_match_relative_diff_max=0.45,
    event_rerank_interested_mismatch_relative_diff_min=0.80,
    event_rerank_interested_count_match_bonus=0.015,
    event_rerank_interested_count_mismatch_penalty=0.02,
    event_graph_weights=(
        GraphFeatureWeight("shared artists", "artists", 0.50, cap=3),
        GraphFeatureWeight("shared promoters", "promoters", 0.20, cap=2),
        GraphFeatureWeight("same venue", "venues", 0.08, boolean=True),
        GraphFeatureWeight("shared abstract genres", "genres", 0.05, cap=3),
        GraphFeatureWeight("shared extracted genres", "extracted_styles", 0.17, cap=3),
    ),
    artist_graph_weights=(
        GraphFeatureWeight("played same events", "events", 0.40, cap=2),
        GraphFeatureWeight("shared promoters", "promoters", 0.25, cap=3),
        GraphFeatureWeight("shared venues", "venues", 0.20, cap=3),
        GraphFeatureWeight("shared styles", "extracted_styles", 0.15, cap=3),
    ),
)


DEFAULT_PROMOTER_RECOMMENDATION_SCORING = PromoterRecommendationScoringConfig(
    semantic_weight=0.25,
    strength_weight=0.16,
    direct_connection_weight=0.16,
    warm_network_weight=0.25,
    event_similarity_weight=0.07,
    scale_fit_weight=0.08,
    activity_weight=0.02,
    recency_weight=0.01,
    strength_matched_artist_weight=0.60,
    strength_event_weight=0.40,
    strength_matched_artist_cap=5,
    strength_event_cap=20,
    direct_connection_cap=3,
    warm_connection_cap=3,
    manual_warm_connection_cap=1,
    manual_warm_boost_weight=0.6,
    event_similarity_count_cap=8,
    event_similarity_min_total_score=0.45,
    event_similarity_per_promoter_limit=20,
    event_similarity_symbolic_weight=0.6,
    event_similarity_embedding_weight=0.4,
    event_similarity_same_venue_weight=0.5,
    event_similarity_shared_genre_weight=0.1,
    event_similarity_shared_lineup_weight=0.2,
    event_similarity_extracted_style_weight=0.2,
    activity_event_cap=25,
    existing_partner_direct_min=1,
    warm_relevant_connection_min=1,
    direct_edge_strength_min=0.8,
    direct_edge_strength_max=1.0,
    warm_edge_strength_min=0.5,
    warm_edge_strength_max=0.8,
    event_similarity_edge_strength_min=0.2,
    event_similarity_edge_strength_max=0.7,
    scale_fit_alpha=75.0,
    scale_fit_tau=0.55,
    sql_candidate_limit=200,
    semantic_artist_pool_limit=20,
    event_similarity_overfetch_multiplier=20,
    event_similarity_overfetch_min=500,
)

# Normalize arbitrary positive weights into a unit-sum tuple.
def normalized_weights(values: tuple[float, ...]) -> tuple[float, ...]:
    if any(value < 0 for value in values):
        raise ValueError("Scoring weights must be non-negative")

    total = sum(values)
    if total <= 0:
        raise ValueError("At least one scoring weight must be greater than zero")

    return tuple(value / total for value in values)

# Read float config from environment with a fallback default.
def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)

# Read integer config from environment with a fallback default.
def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)

# Build semantic-artist scoring config from environment variables.
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

# Build extracted-tag scoring config for semantic artist ranking.
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

# Build full Artist -> Promoter scoring config from environment.
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
                "PROMOTER_REC_EVENT_SIMILARITY_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_weight,
            ),
            env_float(
                "PROMOTER_REC_SCALE_FIT_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.scale_fit_weight,
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
    manual_warm_connection_cap = env_int(
        "PROMOTER_REC_MANUAL_WARM_CONNECTION_CAP",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.manual_warm_connection_cap,
    )
    manual_warm_boost_weight = env_float(
        "PROMOTER_REC_MANUAL_WARM_BOOST_WEIGHT",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.manual_warm_boost_weight,
    )
    event_similarity_count_cap = env_int(
        "PROMOTER_REC_EVENT_SIMILARITY_COUNT_CAP",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_count_cap,
    )
    event_similarity_min_total_score = env_float(
        "PROMOTER_REC_EVENT_SIMILARITY_MIN_TOTAL_SCORE",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_min_total_score,
    )
    event_similarity_per_promoter_limit = env_int(
        "PROMOTER_REC_EVENT_SIMILARITY_PER_PROMOTER_LIMIT",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_per_promoter_limit,
    )
    event_similarity_mix_weights = normalized_weights(
        (
            env_float(
                "PROMOTER_REC_EVENT_SIMILARITY_SYMBOLIC_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_symbolic_weight,
            ),
            env_float(
                "PROMOTER_REC_EVENT_SIMILARITY_EMBEDDING_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_embedding_weight,
            ),
        )
    )
    event_similarity_signal_weights = normalized_weights(
        (
            env_float(
                "PROMOTER_REC_EVENT_SIMILARITY_SAME_VENUE_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_same_venue_weight,
            ),
            env_float(
                "PROMOTER_REC_EVENT_SIMILARITY_SHARED_GENRE_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_shared_genre_weight,
            ),
            env_float(
                "PROMOTER_REC_EVENT_SIMILARITY_SHARED_LINEUP_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_shared_lineup_weight,
            ),
            env_float(
                "PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT",
                DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_extracted_style_weight,
            ),
        )
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
    event_similarity_edge_strength_min = env_float(
        "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MIN",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_edge_strength_min,
    )
    event_similarity_edge_strength_max = env_float(
        "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MAX",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_edge_strength_max,
    )
    scale_fit_alpha = env_float(
        "PROMOTER_REC_SCALE_FIT_ALPHA",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.scale_fit_alpha,
    )
    scale_fit_tau = env_float(
        "PROMOTER_REC_SCALE_FIT_TAU",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.scale_fit_tau,
    )
    sql_candidate_limit = env_int(
        "PROMOTER_REC_SQL_CANDIDATE_LIMIT",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.sql_candidate_limit,
    )
    semantic_artist_pool_limit = env_int(
        "PROMOTER_REC_SEMANTIC_ARTIST_POOL_LIMIT",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.semantic_artist_pool_limit,
    )
    event_similarity_overfetch_multiplier = env_int(
        "PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MULTIPLIER",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_overfetch_multiplier,
    )
    event_similarity_overfetch_min = env_int(
        "PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MIN",
        DEFAULT_PROMOTER_RECOMMENDATION_SCORING.event_similarity_overfetch_min,
    )

    if strength_matched_artist_cap <= 0:
        raise ValueError("PROMOTER_REC_STRENGTH_MATCHED_ARTIST_CAP must be greater than zero")
    if strength_event_cap <= 0:
        raise ValueError("PROMOTER_REC_STRENGTH_EVENT_CAP must be greater than zero")
    if direct_connection_cap <= 0:
        raise ValueError("PROMOTER_REC_DIRECT_CONNECTION_CAP must be greater than zero")
    if warm_connection_cap <= 0:
        raise ValueError("PROMOTER_REC_WARM_CONNECTION_CAP must be greater than zero")
    if manual_warm_connection_cap <= 0:
        raise ValueError("PROMOTER_REC_MANUAL_WARM_CONNECTION_CAP must be greater than zero")
    if manual_warm_boost_weight < 0:
        raise ValueError("PROMOTER_REC_MANUAL_WARM_BOOST_WEIGHT must be non-negative")
    if event_similarity_count_cap <= 0:
        raise ValueError("PROMOTER_REC_EVENT_SIMILARITY_COUNT_CAP must be greater than zero")
    if not (0.0 <= event_similarity_min_total_score <= 1.0):
        raise ValueError("PROMOTER_REC_EVENT_SIMILARITY_MIN_TOTAL_SCORE must be between 0 and 1")
    if event_similarity_per_promoter_limit <= 0:
        raise ValueError("PROMOTER_REC_EVENT_SIMILARITY_PER_PROMOTER_LIMIT must be greater than zero")
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
    if not (0.0 <= event_similarity_edge_strength_min <= 1.0):
        raise ValueError("PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MIN must be between 0 and 1")
    if not (0.0 <= event_similarity_edge_strength_max <= 1.0):
        raise ValueError("PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MAX must be between 0 and 1")
    if event_similarity_edge_strength_min > event_similarity_edge_strength_max:
        raise ValueError(
            "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MIN must be less than or equal to "
            "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MAX"
        )
    if scale_fit_alpha <= 0.0:
        raise ValueError("PROMOTER_REC_SCALE_FIT_ALPHA must be greater than zero")
    if scale_fit_tau <= 0.0:
        raise ValueError("PROMOTER_REC_SCALE_FIT_TAU must be greater than zero")
    if sql_candidate_limit <= 0:
        raise ValueError("PROMOTER_REC_SQL_CANDIDATE_LIMIT must be greater than zero")
    if semantic_artist_pool_limit <= 0:
        raise ValueError("PROMOTER_REC_SEMANTIC_ARTIST_POOL_LIMIT must be greater than zero")
    if event_similarity_overfetch_multiplier <= 0:
        raise ValueError("PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MULTIPLIER must be greater than zero")
    if event_similarity_overfetch_min <= 0:
        raise ValueError("PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MIN must be greater than zero")

    return PromoterRecommendationScoringConfig(
        semantic_weight=weights[0],
        strength_weight=weights[1],
        direct_connection_weight=weights[2],
        warm_network_weight=weights[3],
        event_similarity_weight=weights[4],
        scale_fit_weight=weights[5],
        activity_weight=weights[6],
        recency_weight=weights[7],
        strength_matched_artist_weight=strength_weights[0],
        strength_event_weight=strength_weights[1],
        strength_matched_artist_cap=strength_matched_artist_cap,
        strength_event_cap=strength_event_cap,
        direct_connection_cap=direct_connection_cap,
        warm_connection_cap=warm_connection_cap,
        manual_warm_connection_cap=manual_warm_connection_cap,
        manual_warm_boost_weight=manual_warm_boost_weight,
        event_similarity_count_cap=event_similarity_count_cap,
        event_similarity_min_total_score=event_similarity_min_total_score,
        event_similarity_per_promoter_limit=event_similarity_per_promoter_limit,
        event_similarity_symbolic_weight=event_similarity_mix_weights[0],
        event_similarity_embedding_weight=event_similarity_mix_weights[1],
        event_similarity_same_venue_weight=event_similarity_signal_weights[0],
        event_similarity_shared_genre_weight=event_similarity_signal_weights[1],
        event_similarity_shared_lineup_weight=event_similarity_signal_weights[2],
        event_similarity_extracted_style_weight=event_similarity_signal_weights[3],
        activity_event_cap=activity_event_cap,
        existing_partner_direct_min=existing_partner_direct_min,
        warm_relevant_connection_min=warm_relevant_connection_min,
        direct_edge_strength_min=direct_edge_strength_min,
        direct_edge_strength_max=direct_edge_strength_max,
        warm_edge_strength_min=warm_edge_strength_min,
        warm_edge_strength_max=warm_edge_strength_max,
        event_similarity_edge_strength_min=event_similarity_edge_strength_min,
        event_similarity_edge_strength_max=event_similarity_edge_strength_max,
        scale_fit_alpha=scale_fit_alpha,
        scale_fit_tau=scale_fit_tau,
        sql_candidate_limit=sql_candidate_limit,
        semantic_artist_pool_limit=semantic_artist_pool_limit,
        event_similarity_overfetch_multiplier=event_similarity_overfetch_multiplier,
        event_similarity_overfetch_min=event_similarity_overfetch_min,
    )

# Read and validate API max limit for promoter recommendation endpoint.
def promoter_recommendation_api_limit_max_from_env() -> int:
    value = env_int("PROMOTER_REC_API_LIMIT_MAX", 50)
    if value <= 0:
        raise ValueError("PROMOTER_REC_API_LIMIT_MAX must be greater than zero")
    return value


def artist_recommendation_min_semantic_score_from_env() -> float:
    value = env_float("ARTIST_REC_MIN_SEMANTIC_SCORE", 0.45)
    if not (0.0 <= value <= 1.0):
        raise ValueError("ARTIST_REC_MIN_SEMANTIC_SCORE must be between 0 and 1")
    return value

# Compute semantic artist score from embedding/style/tag components.
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

# Compute capped overlap ratio for two id sets.
def capped_overlap_score(left: set[int], right: set[int], cap: int) -> float:
    if not left or not right:
        return 0.0
    return min(len(left & right) / cap, 1.0)

# Compute boolean overlap score (1 if any overlap exists, else 0).
def boolean_overlap_score(left: set[int], right: set[int]) -> float:
    return 1.0 if left and right and bool(left & right) else 0.0

# Compute weighted contribution for a single graph feature.
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

# Build reason text for a single graph feature overlap.
def graph_feature_reason(
    weight: GraphFeatureWeight,
    source: dict[str, set[int]],
    candidate: dict[str, set[int]],
) -> str:
    overlap_count = len(source.get(weight.feature, set()) & candidate.get(weight.feature, set()))
    if weight.boolean:
        return weight.label
    return f"{overlap_count} {weight.label}"

# Compute total graph score and top graph reasons for a pair of entities.
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

# Blend semantic and graph scores into final recommendation score.
def final_recommendation_score(
    semantic_score: float,
    graph_score: float,
    config: RecommendationScoringConfig = DEFAULT_RECOMMENDATION_SCORING,
) -> float:
    return config.semantic_weight * semantic_score + config.graph_weight * graph_score

# Apply entity-type specific eligibility thresholds before returning candidates.
def is_similarity_candidate_eligible(
    entity_type: EntityType,
    semantic_score: float,
    graph_score: float,
    config: RecommendationScoringConfig = DEFAULT_RECOMMENDATION_SCORING,
) -> bool:
    if entity_type == "artist":
        return graph_score > 0 or semantic_score >= config.artist_semantic_only_threshold
    return (
        graph_score >= config.event_graph_min_threshold
        or semantic_score >= config.event_semantic_if_weak_graph_threshold
    )


# Build general similarity scoring config (artists/events) from environment.
def recommendation_scoring_from_env() -> RecommendationScoringConfig:
    weights = normalized_weights(
        (
            env_float("RECOMMENDATION_SEMANTIC_WEIGHT", DEFAULT_RECOMMENDATION_SCORING.semantic_weight),
            env_float("RECOMMENDATION_GRAPH_WEIGHT", DEFAULT_RECOMMENDATION_SCORING.graph_weight),
        )
    )
    artist_semantic_only_threshold = env_float(
        "RECOMMENDATION_ARTIST_SEMANTIC_ONLY_THRESHOLD",
        DEFAULT_RECOMMENDATION_SCORING.artist_semantic_only_threshold,
    )
    if not (0.0 <= artist_semantic_only_threshold <= 1.0):
        raise ValueError("RECOMMENDATION_ARTIST_SEMANTIC_ONLY_THRESHOLD must be between 0 and 1")
    event_graph_min_threshold = env_float(
        "RECOMMENDATION_EVENT_GRAPH_MIN_THRESHOLD",
        DEFAULT_RECOMMENDATION_SCORING.event_graph_min_threshold,
    )
    event_semantic_if_weak_graph_threshold = env_float(
        "RECOMMENDATION_EVENT_SEMANTIC_IF_WEAK_GRAPH_THRESHOLD",
        DEFAULT_RECOMMENDATION_SCORING.event_semantic_if_weak_graph_threshold,
    )
    if not (0.0 <= event_graph_min_threshold <= 1.0):
        raise ValueError("RECOMMENDATION_EVENT_GRAPH_MIN_THRESHOLD must be between 0 and 1")
    if not (0.0 <= event_semantic_if_weak_graph_threshold <= 1.0):
        raise ValueError("RECOMMENDATION_EVENT_SEMANTIC_IF_WEAK_GRAPH_THRESHOLD must be between 0 and 1")
    event_rerank_min_graph_for_neutral = env_float(
        "EVENT_RERANK_MIN_GRAPH_FOR_NEUTRAL",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_min_graph_for_neutral,
    )
    event_rerank_low_graph_penalty = env_float(
        "EVENT_RERANK_LOW_GRAPH_PENALTY",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_low_graph_penalty,
    )
    event_rerank_extracted_genres_bonus_threshold = env_int(
        "EVENT_RERANK_EXTRACTED_GENRES_BONUS_THRESHOLD",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_extracted_genres_bonus_threshold,
    )
    event_rerank_extracted_genres_bonus = env_float(
        "EVENT_RERANK_EXTRACTED_GENRES_BONUS",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_extracted_genres_bonus,
    )
    event_rerank_shared_artists_bonus = env_float(
        "EVENT_RERANK_SHARED_ARTISTS_BONUS",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_shared_artists_bonus,
    )
    event_rerank_interested_match_relative_diff_max = env_float(
        "EVENT_RERANK_INTERESTED_MATCH_RELATIVE_DIFF_MAX",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_interested_match_relative_diff_max,
    )
    event_rerank_interested_mismatch_relative_diff_min = env_float(
        "EVENT_RERANK_INTERESTED_MISMATCH_RELATIVE_DIFF_MIN",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_interested_mismatch_relative_diff_min,
    )
    event_rerank_interested_count_match_bonus = env_float(
        "EVENT_RERANK_INTERESTED_COUNT_MATCH_BONUS",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_interested_count_match_bonus,
    )
    event_rerank_interested_count_mismatch_penalty = env_float(
        "EVENT_RERANK_INTERESTED_COUNT_MISMATCH_PENALTY",
        DEFAULT_RECOMMENDATION_SCORING.event_rerank_interested_count_mismatch_penalty,
    )
    if not (0.0 <= event_rerank_min_graph_for_neutral <= 1.0):
        raise ValueError("EVENT_RERANK_MIN_GRAPH_FOR_NEUTRAL must be between 0 and 1")
    if event_rerank_low_graph_penalty < 0:
        raise ValueError("EVENT_RERANK_LOW_GRAPH_PENALTY must be non-negative")
    if event_rerank_extracted_genres_bonus_threshold < 1:
        raise ValueError("EVENT_RERANK_EXTRACTED_GENRES_BONUS_THRESHOLD must be at least 1")
    if event_rerank_extracted_genres_bonus < 0:
        raise ValueError("EVENT_RERANK_EXTRACTED_GENRES_BONUS must be non-negative")
    if event_rerank_shared_artists_bonus < 0:
        raise ValueError("EVENT_RERANK_SHARED_ARTISTS_BONUS must be non-negative")
    if not (0.0 <= event_rerank_interested_match_relative_diff_max <= 1.0):
        raise ValueError("EVENT_RERANK_INTERESTED_MATCH_RELATIVE_DIFF_MAX must be between 0 and 1")
    if not (0.0 <= event_rerank_interested_mismatch_relative_diff_min <= 1.0):
        raise ValueError("EVENT_RERANK_INTERESTED_MISMATCH_RELATIVE_DIFF_MIN must be between 0 and 1")
    if event_rerank_interested_match_relative_diff_max > event_rerank_interested_mismatch_relative_diff_min:
        raise ValueError(
            "EVENT_RERANK_INTERESTED_MATCH_RELATIVE_DIFF_MAX must be <= "
            "EVENT_RERANK_INTERESTED_MISMATCH_RELATIVE_DIFF_MIN"
        )
    if event_rerank_interested_count_match_bonus < 0:
        raise ValueError("EVENT_RERANK_INTERESTED_COUNT_MATCH_BONUS must be non-negative")
    if event_rerank_interested_count_mismatch_penalty < 0:
        raise ValueError("EVENT_RERANK_INTERESTED_COUNT_MISMATCH_PENALTY must be non-negative")

    event_caps = (
        env_int("EVENT_GRAPH_SHARED_ARTISTS_CAP", 3),
        env_int("EVENT_GRAPH_SHARED_PROMOTERS_CAP", 2),
        env_int("EVENT_GRAPH_SHARED_GENRES_CAP", 3),
        env_int("EVENT_GRAPH_SHARED_EXTRACTED_STYLES_CAP", 3),
    )
    if any(cap <= 0 for cap in event_caps):
        raise ValueError("EVENT_GRAPH_*_CAP values must be greater than zero")

    event_graph_weight_values = normalized_weights(
        (
            env_float("EVENT_GRAPH_SHARED_ARTISTS_WEIGHT", 0.50),
            env_float("EVENT_GRAPH_SHARED_PROMOTERS_WEIGHT", 0.20),
            env_float("EVENT_GRAPH_SAME_VENUE_WEIGHT", 0.08),
            env_float("EVENT_GRAPH_SHARED_GENRES_WEIGHT", 0.05),
            env_float("EVENT_GRAPH_SHARED_EXTRACTED_STYLES_WEIGHT", 0.17),
        )
    )
    artist_graph_weight_values = normalized_weights(
        (
            env_float("ARTIST_GRAPH_PLAYED_SAME_EVENTS_WEIGHT", 0.40),
            env_float("ARTIST_GRAPH_SHARED_PROMOTERS_WEIGHT", 0.25),
            env_float("ARTIST_GRAPH_SHARED_VENUES_WEIGHT", 0.20),
            env_float(
                "ARTIST_GRAPH_SHARED_STYLES_WEIGHT",
                env_float("ARTIST_GRAPH_SHARED_GENRES_WEIGHT", 0.15),
            ),
        )
    )
    return RecommendationScoringConfig(
        semantic_weight=weights[0],
        graph_weight=weights[1],
        artist_semantic_only_threshold=artist_semantic_only_threshold,
        event_graph_min_threshold=event_graph_min_threshold,
        event_semantic_if_weak_graph_threshold=event_semantic_if_weak_graph_threshold,
        event_rerank_min_graph_for_neutral=event_rerank_min_graph_for_neutral,
        event_rerank_low_graph_penalty=event_rerank_low_graph_penalty,
        event_rerank_extracted_genres_bonus_threshold=event_rerank_extracted_genres_bonus_threshold,
        event_rerank_extracted_genres_bonus=event_rerank_extracted_genres_bonus,
        event_rerank_shared_artists_bonus=event_rerank_shared_artists_bonus,
        event_rerank_interested_match_relative_diff_max=event_rerank_interested_match_relative_diff_max,
        event_rerank_interested_mismatch_relative_diff_min=event_rerank_interested_mismatch_relative_diff_min,
        event_rerank_interested_count_match_bonus=event_rerank_interested_count_match_bonus,
        event_rerank_interested_count_mismatch_penalty=event_rerank_interested_count_mismatch_penalty,
        event_graph_weights=(
            GraphFeatureWeight("shared artists", "artists", event_graph_weight_values[0], cap=event_caps[0]),
            GraphFeatureWeight(
                "shared promoters",
                "promoters",
                event_graph_weight_values[1],
                cap=event_caps[1],
            ),
            GraphFeatureWeight("same venue", "venues", event_graph_weight_values[2], boolean=True),
            GraphFeatureWeight(
                "shared abstract genres",
                "genres",
                event_graph_weight_values[3],
                cap=event_caps[2],
            ),
            GraphFeatureWeight(
                "shared extracted genres",
                "extracted_styles",
                event_graph_weight_values[4],
                cap=event_caps[3],
            ),
        ),
        artist_graph_weights=(
            GraphFeatureWeight(
                "played same events",
                "events",
                artist_graph_weight_values[0],
                cap=2,
            ),
            GraphFeatureWeight(
                "shared promoters",
                "promoters",
                artist_graph_weight_values[1],
                cap=3,
            ),
            GraphFeatureWeight(
                "shared venues",
                "venues",
                artist_graph_weight_values[2],
                cap=3,
            ),
            GraphFeatureWeight(
                "shared styles",
                "extracted_styles",
                artist_graph_weight_values[3],
                cap=3,
            ),
        ),
    )
