from __future__ import annotations

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
