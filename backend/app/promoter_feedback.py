from __future__ import annotations

import math
import os
from dataclasses import dataclass

from psycopg import Connection

from app.schemas import PromoterRecommendationItem


DEFAULT_EXACT_POSITIVE_BOOST = 0.10
DEFAULT_SIMILAR_POSITIVE_BOOST = 0.03
DEFAULT_MAX_TOTAL_BOOST = 0.15


@dataclass(frozen=True)
class PromoterFeedbackConfig:
    exact_positive_boost: float
    similar_positive_boost: float
    max_total_boost: float


def _non_negative_float(name: str, default: float) -> float:
    value = float(os.environ.get(name, default))
    if value < 0:
        raise ValueError(f"{name} must be greater than or equal to 0")
    return value


def promoter_feedback_config_from_env() -> PromoterFeedbackConfig:
    return PromoterFeedbackConfig(
        exact_positive_boost=_non_negative_float(
            "PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST",
            DEFAULT_EXACT_POSITIVE_BOOST,
        ),
        similar_positive_boost=_non_negative_float(
            "PROMOTER_FEEDBACK_SIMILAR_POSITIVE_BOOST",
            DEFAULT_SIMILAR_POSITIVE_BOOST,
        ),
        max_total_boost=_non_negative_float(
            "PROMOTER_FEEDBACK_MAX_TOTAL_BOOST",
            DEFAULT_MAX_TOTAL_BOOST,
        ),
    )


def load_promoter_feedback(
    connection: Connection,
    *,
    user_id: int,
    artist_id: int,
) -> dict[int, str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT candidate_entity_id, feedback
            FROM recommendation_feedback
            WHERE user_id = %s
              AND source_entity_type = 'artist'
              AND source_entity_id = %s
              AND candidate_entity_type = 'promoter'
            """,
            (user_id, artist_id),
        )
        return {
            int(row["candidate_entity_id"]): str(row["feedback"])
            for row in cursor.fetchall()
        }


def _signal_similarity(
    left: PromoterRecommendationItem,
    right: PromoterRecommendationItem,
) -> float:
    keys = sorted(set(left.scoreBreakdown) | set(right.scoreBreakdown))
    left_values = [max(float(left.scoreBreakdown.get(key, 0.0)), 0.0) for key in keys]
    right_values = [max(float(right.scoreBreakdown.get(key, 0.0)), 0.0) for key in keys]
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left_values, right_values, strict=True)) / (
        left_norm * right_norm
    )


def apply_promoter_feedback_reranking(
    recommendations: list[PromoterRecommendationItem],
    *,
    feedback_by_promoter_id: dict[int, str],
    config: PromoterFeedbackConfig,
) -> list[PromoterRecommendationItem]:
    positive_items = [
        item for item in recommendations if feedback_by_promoter_id.get(item.id) == "positive"
    ]
    reranked: list[PromoterRecommendationItem] = []

    for item in recommendations:
        feedback_state = feedback_by_promoter_id.get(item.id)
        if feedback_state == "negative":
            continue

        base_score = float(item.score)
        feedback_boost = 0.0
        if feedback_state == "positive":
            feedback_boost += config.exact_positive_boost
        elif positive_items:
            similarity = max(_signal_similarity(item, positive) for positive in positive_items)
            feedback_boost += config.similar_positive_boost * similarity

        feedback_boost = min(feedback_boost, config.max_total_boost)
        reranked.append(
            item.model_copy(
                update={
                    "baseScore": base_score,
                    "feedbackBoost": feedback_boost,
                    "feedbackState": feedback_state,
                    "score": min(base_score + feedback_boost, 1.0),
                }
            )
        )

    return reranked
