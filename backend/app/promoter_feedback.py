from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from psycopg import Connection

from app.event_similarity import event_embedding_similarity_by_candidate
from app.recommendation_config_loader import load_recommendation_config
from app.schemas import PromoterRecommendationItem


@dataclass(frozen=True)
class PromoterFeedbackConfig:
    exact_positive_boost: float
    similar_positive_boost: float
    max_total_boost: float
    similarity_min: float
    similar_promoter_limit: int


@dataclass(frozen=True)
class PromoterFeedbackTuning:
    profile_event_limit: int
    shared_artists_weight: float
    shared_genres_tags_weight: float
    similar_events_weight: float
    shared_venues_weight: float


@dataclass(frozen=True)
class PromoterContentProfile:
    artist_ids: frozenset[int] = frozenset()
    genre_tags: frozenset[str] = frozenset()
    venue_ids: frozenset[int] = frozenset()
    event_ids: tuple[int, ...] = ()

@lru_cache(maxsize=1)
def _recommendation_config():
    return load_recommendation_config()


def promoter_feedback_config_from_env() -> PromoterFeedbackConfig:
    config_values = _recommendation_config().promoter_feedback
    return PromoterFeedbackConfig(
        exact_positive_boost=config_values["PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST"],
        similar_positive_boost=config_values["PROMOTER_FEEDBACK_SIMILAR_POSITIVE_BOOST"],
        max_total_boost=config_values["PROMOTER_FEEDBACK_MAX_TOTAL_BOOST"],
        similarity_min=config_values["PROMOTER_FEEDBACK_SIMILARITY_MIN"],
        similar_promoter_limit=config_values["PROMOTER_FEEDBACK_SIMILAR_PROMOTER_LIMIT"],
    )


def promoter_feedback_tuning_from_config() -> PromoterFeedbackTuning:
    config_values = _recommendation_config().promoter_feedback
    return PromoterFeedbackTuning(
        profile_event_limit=config_values["PROMOTER_PROFILE_EVENT_LIMIT"],
        shared_artists_weight=config_values["SHARED_ARTISTS_WEIGHT"],
        shared_genres_tags_weight=config_values["SHARED_GENRES_TAGS_WEIGHT"],
        similar_events_weight=config_values["SIMILAR_EVENTS_WEIGHT"],
        shared_venues_weight=config_values["SHARED_VENUES_WEIGHT"],
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


def _set_cosine_similarity(left: frozenset[object], right: frozenset[object]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / math.sqrt(len(left) * len(right))


def promoter_content_similarity(
    left: PromoterContentProfile,
    right: PromoterContentProfile,
    *,
    event_similarity: float = 0.0,
    tuning: PromoterFeedbackTuning | None = None,
) -> float:
    tuning = tuning or promoter_feedback_tuning_from_config()
    return min(
        tuning.shared_artists_weight * _set_cosine_similarity(left.artist_ids, right.artist_ids)
        + tuning.shared_genres_tags_weight * _set_cosine_similarity(left.genre_tags, right.genre_tags)
        + tuning.similar_events_weight * max(min(event_similarity, 1.0), 0.0)
        + tuning.shared_venues_weight * _set_cosine_similarity(left.venue_ids, right.venue_ids),
        1.0,
    )


def load_promoter_content_profiles(
    connection: Connection,
    promoter_ids: list[int],
) -> dict[int, PromoterContentProfile]:
    tuning = promoter_feedback_tuning_from_config()
    unique_promoter_ids = sorted(set(promoter_ids))
    if not unique_promoter_ids:
        return {}

    profiles: dict[int, dict[str, object]] = {
        promoter_id: {
            "artist_ids": set(),
            "genre_tags": set(),
            "venue_ids": set(),
            "event_ids": [],
        }
        for promoter_id in unique_promoter_ids
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH ranked_events AS (
                SELECT
                    ep.promoter_id,
                    e.id AS event_id,
                    e.venue_id,
                    row_number() OVER (
                        PARTITION BY ep.promoter_id
                        ORDER BY e.event_date DESC NULLS LAST, e.id DESC
                    ) AS event_rank
                FROM event_promoters ep
                JOIN events e ON e.id = ep.event_id
                WHERE ep.promoter_id = ANY(%s)
            )
            SELECT promoter_id, event_id, venue_id
            FROM ranked_events
            WHERE event_rank <= %s
            """,
            (unique_promoter_ids, tuning.profile_event_limit),
        )
        for row in cursor.fetchall():
            profile = profiles[int(row["promoter_id"])]
            profile["event_ids"].append(int(row["event_id"]))
            if row["venue_id"] is not None:
                profile["venue_ids"].add(int(row["venue_id"]))

        cursor.execute(
            """
            SELECT DISTINCT ep.promoter_id, ea.artist_id
            FROM event_promoters ep
            JOIN event_artists ea ON ea.event_id = ep.event_id
            WHERE ep.promoter_id = ANY(%s)
            """,
            (unique_promoter_ids,),
        )
        for row in cursor.fetchall():
            profiles[int(row["promoter_id"])]["artist_ids"].add(int(row["artist_id"]))

        cursor.execute(
            """
            SELECT DISTINCT ep.promoter_id, lower(g.name) AS genre_tag
            FROM event_promoters ep
            JOIN event_genres eg ON eg.event_id = ep.event_id
            JOIN genres g ON g.id = eg.genre_id
            WHERE ep.promoter_id = ANY(%s)
              AND btrim(g.name) <> ''
            UNION
            SELECT DISTINCT ep.promoter_id, lower(eet.tag_value) AS genre_tag
            FROM event_promoters ep
            JOIN event_extracted_tags eet ON eet.event_id = ep.event_id
            WHERE ep.promoter_id = ANY(%s)
              AND eet.tag_type IN ('genre', 'style')
              AND btrim(eet.tag_value) <> ''
            """,
            (unique_promoter_ids, unique_promoter_ids),
        )
        for row in cursor.fetchall():
            profiles[int(row["promoter_id"])]["genre_tags"].add(str(row["genre_tag"]))

    return {
        promoter_id: PromoterContentProfile(
            artist_ids=frozenset(profile["artist_ids"]),
            genre_tags=frozenset(profile["genre_tags"]),
            venue_ids=frozenset(profile["venue_ids"]),
            event_ids=tuple(profile["event_ids"]),
        )
        for promoter_id, profile in profiles.items()
    }


def promoter_content_similarities(
    connection: Connection,
    *,
    candidate_promoter_ids: list[int],
    positive_promoter_ids: list[int],
    config: PromoterFeedbackConfig,
) -> dict[int, float]:
    tuning = promoter_feedback_tuning_from_config()
    candidate_ids = sorted(set(candidate_promoter_ids) - set(positive_promoter_ids))
    positive_ids = sorted(set(positive_promoter_ids))
    if not candidate_ids or not positive_ids:
        return {}

    profiles = load_promoter_content_profiles(connection, [*candidate_ids, *positive_ids])
    candidate_event_owners: dict[int, set[int]] = {}
    for promoter_id in candidate_ids:
        for event_id in profiles.get(promoter_id, PromoterContentProfile()).event_ids:
            candidate_event_owners.setdefault(event_id, set()).add(promoter_id)
    candidate_event_ids = sorted(candidate_event_owners)
    similarities: dict[int, float] = {}

    for positive_id in positive_ids:
        positive_profile = profiles.get(positive_id)
        if positive_profile is None:
            continue
        event_scores, _ = event_embedding_similarity_by_candidate(
            connection,
            source_event_ids=list(positive_profile.event_ids),
            candidate_event_ids=candidate_event_ids,
        )
        event_similarity_by_promoter: dict[int, float] = {}
        for event_id, score in event_scores.items():
            for promoter_id in candidate_event_owners.get(event_id, set()):
                event_similarity_by_promoter[promoter_id] = max(
                    event_similarity_by_promoter.get(promoter_id, 0.0),
                    score,
                )

        for candidate_id in candidate_ids:
            candidate_profile = profiles.get(candidate_id)
            if candidate_profile is None:
                continue
            similarity = promoter_content_similarity(
                candidate_profile,
                positive_profile,
                event_similarity=event_similarity_by_promoter.get(candidate_id, 0.0),
                tuning=tuning,
            )
            similarities[candidate_id] = max(similarities.get(candidate_id, 0.0), similarity)

    eligible = [
        (promoter_id, similarity)
        for promoter_id, similarity in similarities.items()
        if similarity >= config.similarity_min
    ]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    return dict(eligible[: config.similar_promoter_limit])


def apply_promoter_feedback_reranking(
    recommendations: list[PromoterRecommendationItem],
    *,
    feedback_by_promoter_id: dict[int, str],
    content_similarity_by_promoter_id: dict[int, float],
    config: PromoterFeedbackConfig,
) -> list[PromoterRecommendationItem]:
    reranked: list[PromoterRecommendationItem] = []

    for item in recommendations:
        feedback_state = feedback_by_promoter_id.get(item.id)
        if feedback_state == "negative":
            continue

        base_score = float(item.score)
        feedback_boost = 0.0
        if feedback_state == "positive":
            feedback_boost += config.exact_positive_boost
        else:
            similarity = content_similarity_by_promoter_id.get(item.id, 0.0)
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
