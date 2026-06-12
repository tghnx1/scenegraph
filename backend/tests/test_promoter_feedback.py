import pytest

from app.promoter_feedback import (
    PromoterFeedbackConfig,
    apply_promoter_feedback_reranking,
    promoter_feedback_config_from_env,
)
from app.schemas import PromoterRecommendationItem


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
    )


def test_negative_feedback_excludes_only_exact_promoter(config):
    items = [
        recommendation(1, score=0.50, semantic=0.40, event_similarity=0.10),
        recommendation(2, score=0.45, semantic=0.39, event_similarity=0.10),
    ]

    reranked = apply_promoter_feedback_reranking(
        items,
        feedback_by_promoter_id={1: "negative"},
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
        config=config,
    )
    second_user = apply_promoter_feedback_reranking(
        items,
        feedback_by_promoter_id={},
        config=config,
    )

    assert first_user == []
    assert [item.id for item in second_user] == [1]


def test_positive_feedback_boosts_exact_and_similar_promoters(config):
    exact = recommendation(1, score=0.50, semantic=0.40, event_similarity=0.10)
    similar = recommendation(2, score=0.45, semantic=0.39, event_similarity=0.10)
    different = recommendation(3, score=0.40, semantic=0.00, event_similarity=0.50)

    reranked = apply_promoter_feedback_reranking(
        [exact, similar, different],
        feedback_by_promoter_id={1: "positive"},
        config=config,
    )
    by_id = {item.id: item for item in reranked}

    assert by_id[1].feedbackState == "positive"
    assert by_id[1].feedbackBoost == pytest.approx(0.10)
    assert by_id[1].score == pytest.approx(by_id[1].baseScore + 0.10)
    assert 0 < by_id[2].feedbackBoost <= 0.03
    assert by_id[2].feedbackBoost > by_id[3].feedbackBoost


def test_feedback_boost_is_capped():
    item = recommendation(1, score=0.50, semantic=0.40, event_similarity=0.10)
    reranked = apply_promoter_feedback_reranking(
        [item],
        feedback_by_promoter_id={1: "positive"},
        config=PromoterFeedbackConfig(
            exact_positive_boost=0.50,
            similar_positive_boost=0.30,
            max_total_boost=0.15,
        ),
    )

    assert reranked[0].feedbackBoost == pytest.approx(0.15)


def test_promoter_feedback_config_uses_defaults(monkeypatch):
    for name in (
        "PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST",
        "PROMOTER_FEEDBACK_SIMILAR_POSITIVE_BOOST",
        "PROMOTER_FEEDBACK_MAX_TOTAL_BOOST",
    ):
        monkeypatch.delenv(name, raising=False)

    config = promoter_feedback_config_from_env()

    assert config.exact_positive_boost == pytest.approx(0.10)
    assert config.similar_positive_boost == pytest.approx(0.03)
    assert config.max_total_boost == pytest.approx(0.15)
