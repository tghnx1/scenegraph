from copy import deepcopy
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml

from app.recommendations.promoter_feedback import (
    PromoterContentProfile,
    PromoterFeedbackConfig,
    PromoterFeedbackTuning,
    apply_promoter_feedback_reranking,
    promoter_content_similarity,
    promoter_feedback_config_from_config,
)
from app.recommendations.config_loader import RecommendationConfig
from app.schemas import PromoterRecommendationItem


CANONICAL_RECOMMENDATION_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "app" / "recommendations" / "config.yaml"
)


def recommendation(
    promoter_id: int,
    *,
    score: float,
    semantic: float,
    event_similarity: float,
) -> PromoterRecommendationItem:
    return PromoterRecommendationItem(
        id=promoter_id,
        name=f"Promoter {promoter_id}",
        score=score,
        semanticScore=semantic,
        strengthScore=0.2,
        activityScore=0.1,
        recencyScore=0.1,
        scoreBreakdown={
            "semantic": semantic,
            "eventSimilarity": event_similarity,
        },
        matchedArtistCount=1,
        eventCount=1,
    )


@pytest.fixture
def config() -> PromoterFeedbackConfig:
    return PromoterFeedbackConfig(
        exact_positive_boost=0.10,
        similar_positive_boost=0.03,
        max_total_boost=0.15,
        similarity_min=0.30,
        similar_promoter_limit=10,
    )


@pytest.fixture
def feedback_tuning() -> PromoterFeedbackTuning:
    return PromoterFeedbackTuning(
        profile_event_limit=20,
        shared_artists_weight=0.45,
        shared_genres_tags_weight=0.25,
        similar_events_weight=0.20,
        shared_venues_weight=0.10,
    )


def _canonical_recommendation_config_data() -> dict:
    with CANONICAL_RECOMMENDATION_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def _recommendation_config_from_data(config_data: dict) -> RecommendationConfig:
    metadata = dict(config_data["metadata"])
    metadata["legacy_aliases"] = MappingProxyType(dict(metadata["legacy_aliases"]))
    return RecommendationConfig(
        promoter_recommendations=MappingProxyType(dict(config_data["promoter_recommendations"])),
        promoter_feedback=MappingProxyType(dict(config_data["promoter_feedback"])),
        metadata=MappingProxyType(metadata),
    )


def _set_feedback_config(monkeypatch: pytest.MonkeyPatch, **overrides) -> None:
    config_data = deepcopy(_canonical_recommendation_config_data())
    config_data["promoter_feedback"].update(overrides)
    monkeypatch.setattr(
        "app.recommendations.promoter_feedback._recommendation_config",
        lambda: _recommendation_config_from_data(config_data),
    )


def test_negative_feedback_excludes_only_exact_promoter(config):
    items = [
        recommendation(1, score=0.50, semantic=0.40, event_similarity=0.10),
        recommendation(2, score=0.45, semantic=0.39, event_similarity=0.10),
    ]

    reranked = apply_promoter_feedback_reranking(
        items,
        feedback_by_promoter_id={1: "negative"},
        content_similarity_by_promoter_id={},
        config=config,
    )

    assert [item.id for item in reranked] == [2]
    assert reranked[0].feedbackBoost == 0
    assert reranked[0].score == reranked[0].baseScore


def test_negative_feedback_map_does_not_affect_another_user(config):
    items = [recommendation(1, score=0.50, semantic=0.40, event_similarity=0.10)]

    first_user = apply_promoter_feedback_reranking(
        items,
        feedback_by_promoter_id={1: "negative"},
        content_similarity_by_promoter_id={},
        config=config,
    )
    second_user = apply_promoter_feedback_reranking(
        items,
        feedback_by_promoter_id={},
        content_similarity_by_promoter_id={},
        config=config,
    )

    assert first_user == []
    assert [item.id for item in second_user] == [1]


def test_positive_feedback_boosts_exact_and_content_similar_promoters(config):
    exact = recommendation(1, score=0.50, semantic=0.40, event_similarity=0.10)
    similar = recommendation(2, score=0.45, semantic=0.39, event_similarity=0.10)
    different = recommendation(3, score=0.40, semantic=0.00, event_similarity=0.50)

    reranked = apply_promoter_feedback_reranking(
        [exact, similar, different],
        feedback_by_promoter_id={1: "positive"},
        content_similarity_by_promoter_id={2: 0.90, 3: 0.40},
        config=config,
    )
    by_id = {item.id: item for item in reranked}

    assert by_id[1].feedbackState == "positive"
    assert by_id[1].feedbackBoost == pytest.approx(0.10)
    assert by_id[1].score == pytest.approx(by_id[1].baseScore + 0.10)
    assert by_id[2].feedbackBoost == pytest.approx(0.027)
    assert by_id[2].feedbackBoost > by_id[3].feedbackBoost


def test_similarity_boost_works_when_positive_promoter_is_not_in_current_results(config):
    item = recommendation(2, score=0.45, semantic=0.39, event_similarity=0.10)

    reranked = apply_promoter_feedback_reranking(
        [item],
        feedback_by_promoter_id={1: "positive"},
        content_similarity_by_promoter_id={2: 0.80},
        config=config,
    )

    assert reranked[0].feedbackBoost == pytest.approx(0.024)


def test_content_similarity_uses_promoter_content_not_recommendation_scores(
    feedback_tuning,
):
    left = PromoterContentProfile(
        artist_ids=frozenset({1, 2, 3}),
        genre_tags=frozenset({"ebm", "techno"}),
        venue_ids=frozenset({10}),
    )
    right = PromoterContentProfile(
        artist_ids=frozenset({2, 3, 4}),
        genre_tags=frozenset({"ebm", "industrial"}),
        venue_ids=frozenset({10}),
    )

    similarity = promoter_content_similarity(left, right, event_similarity=0.75, tuning=feedback_tuning)

    assert similarity == pytest.approx(
        0.45 * (2 / 3)
        + 0.25 * (1 / 2)
        + 0.20 * 0.75
        + 0.10
    )


def test_feedback_boost_is_capped():
    item = recommendation(1, score=0.50, semantic=0.40, event_similarity=0.10)
    reranked = apply_promoter_feedback_reranking(
        [item],
        feedback_by_promoter_id={1: "positive"},
        content_similarity_by_promoter_id={},
        config=PromoterFeedbackConfig(
            exact_positive_boost=0.50,
            similar_positive_boost=0.30,
            max_total_boost=0.15,
            similarity_min=0.30,
            similar_promoter_limit=10,
        ),
    )

    assert reranked[0].feedbackBoost == pytest.approx(0.15)


def test_promoter_feedback_config_uses_config_defaults():
    config = promoter_feedback_config_from_config()

    assert config.exact_positive_boost == pytest.approx(0.10)
    assert config.similar_positive_boost == pytest.approx(0.03)
    assert config.max_total_boost == pytest.approx(0.15)
    assert config.similarity_min == pytest.approx(0.30)
    assert config.similar_promoter_limit == 10


def test_promoter_feedback_config_reads_config_override(monkeypatch):
    _set_feedback_config(
        monkeypatch,
        PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST=0.12,
        PROMOTER_FEEDBACK_SIMILAR_POSITIVE_BOOST=0.04,
        PROMOTER_FEEDBACK_MAX_TOTAL_BOOST=0.2,
        PROMOTER_FEEDBACK_SIMILARITY_MIN=0.25,
        PROMOTER_FEEDBACK_SIMILAR_PROMOTER_LIMIT=7,
    )

    config = promoter_feedback_config_from_config()

    assert config == PromoterFeedbackConfig(
        exact_positive_boost=0.12,
        similar_positive_boost=0.04,
        max_total_boost=0.2,
        similarity_min=0.25,
        similar_promoter_limit=7,
    )
