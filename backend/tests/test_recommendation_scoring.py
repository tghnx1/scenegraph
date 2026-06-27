from copy import deepcopy
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml

from app.recommendations.config_loader import RecommendationConfig
from app.recommendations.services import promoter_recommendation_adjusted_score
from app.recommendations.scoring import (
    DEFAULT_RECOMMENDATION_SCORING,
    PromoterRecommendationScoringConfig,
    SemanticArtistScoringConfig,
    SemanticArtistTagScoringConfig,
    artist_recommendation_min_semantic_score_from_env,
    final_recommendation_score,
    hybrid_graph_score,
    is_similarity_candidate_eligible,
    normalized_weights,
    promoter_segment_quota_ratios_from_config,
    promoter_segment_warm_share_from_config,
    promoter_recommendation_api_limit_max_from_config,
    promoter_recommendation_scoring_from_config,
    recommendation_scoring_from_env,
    semantic_artist_score,
    semantic_artist_scoring_from_env,
    semantic_artist_tag_scoring_from_env,
)


CANONICAL_RECOMMENDATION_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "app" / "recommendations" / "config.yaml"
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


def _set_promoter_config(monkeypatch: pytest.MonkeyPatch, **overrides) -> None:
    config_data = deepcopy(_canonical_recommendation_config_data())
    config_data["promoter_recommendations"].update(overrides)
    monkeypatch.setattr(
        "app.recommendations.scoring._recommendation_config",
        lambda: _recommendation_config_from_data(config_data),
    )


def test_event_graph_score_uses_capped_overlap_counts():
    source = {
        "artists": {1, 2, 3, 4},
        "promoters": {10, 11},
        "venues": {20},
        "genres": {30, 31, 32},
        "extracted_genres": {"electro", "breaks", "dark disco"},
    }
    candidate = {
        "artists": {1, 2},
        "promoters": {10, 11, 12},
        "venues": {20},
        "genres": {31},
        "extracted_genres": {"electro", "dark disco"},
    }

    score, reasons = hybrid_graph_score("event", source, candidate)

    assert round(score, 4) == round(
        (2 / 3 * 0.50) + 0.20 + 0.08 + (1 / 3 * 0.05) + (2 / 3 * 0.17),
        4,
    )
    assert reasons == ["2 shared artists", "2 shared promoters", "2 shared extracted genres"]


def test_artist_graph_score_uses_default_config():
    source = {
        "events": {1, 2},
        "promoters": {10, 11, 12},
        "venues": {20},
        "extracted_genres": {"ebm", "dark disco"},
    }
    candidate = {
        "events": {1, 2, 3},
        "promoters": {10},
        "venues": {21},
        "extracted_genres": {"ebm", "dark disco", "new wave"},
    }

    score, reasons = hybrid_graph_score("artist", source, candidate)

    assert round(score, 4) == round(0.40 + (1 / 3 * 0.25) + (2 / 3 * 0.15), 4)
    assert reasons == ["2 played same events", "2 shared styles", "1 shared promoters"]


def test_artist_graph_score_can_isolate_direct_event_overlap():
    source = {
        "events": {1, 2},
        "promoters": set(),
        "venues": set(),
        "genres": set(),
    }
    candidate = {
        "events": {1, 2},
        "promoters": set(),
        "venues": set(),
        "genres": set(),
    }

    score, reasons = hybrid_graph_score("artist", source, candidate)

    assert score == 0.40
    assert reasons == ["2 played same events"]


def test_final_recommendation_score_mixes_semantic_and_graph_weights():
    score = final_recommendation_score(0.8, 0.4, DEFAULT_RECOMMENDATION_SCORING)

    assert score == 0.65 * 0.8 + 0.35 * 0.4


def test_semantic_artist_score_uses_configured_weights():
    score = semantic_artist_score(
        0.8,
        0.5,
        0.25,
        SemanticArtistScoringConfig(
            embedding_weight=0.5,
            style_weight=0.3,
            tag_weight=0.2,
        ),
    )

    assert score == 0.5 * 0.8 + 0.3 * 0.5 + 0.2 * 0.25


def test_semantic_artist_scoring_reads_and_normalizes_env(monkeypatch):
    monkeypatch.setenv("SEMANTIC_ARTIST_EMBEDDING_WEIGHT", "65")
    monkeypatch.setenv("SEMANTIC_ARTIST_STYLE_WEIGHT", "25")
    monkeypatch.setenv("SEMANTIC_ARTIST_TAG_WEIGHT", "10")

    config = semantic_artist_scoring_from_env()

    assert config == SemanticArtistScoringConfig(
        embedding_weight=0.65,
        style_weight=0.25,
        tag_weight=0.10,
    )


def test_semantic_artist_tag_scoring_reads_and_normalizes_env(monkeypatch):
    monkeypatch.setenv("SEMANTIC_ARTIST_TAG_LABEL_WEIGHT", "35")
    monkeypatch.setenv("SEMANTIC_ARTIST_TAG_COLLECTIVE_WEIGHT", "30")
    monkeypatch.setenv("SEMANTIC_ARTIST_TAG_RESIDENCY_WEIGHT", "25")
    monkeypatch.setenv("SEMANTIC_ARTIST_TAG_ROLE_WEIGHT", "10")
    monkeypatch.setenv("SEMANTIC_ARTIST_TAG_ROLE_OVERLAP_CAP", "3")

    config = semantic_artist_tag_scoring_from_env()

    assert config == SemanticArtistTagScoringConfig(
        label_weight=0.35,
        collective_weight=0.30,
        residency_weight=0.25,
        role_weight=0.10,
        role_overlap_cap=3,
    )


def test_promoter_recommendation_scoring_reads_and_normalizes_config(monkeypatch):
    _set_promoter_config(
        monkeypatch,
        PROMOTER_REC_SEMANTIC_WEIGHT=35.0,
        PROMOTER_REC_STRENGTH_WEIGHT=18.0,
        PROMOTER_REC_CO_PLAYED_CONNECTION_WEIGHT=8.0,
        PROMOTER_REC_MANUAL_CONNECTION_WEIGHT=4.0,
        PROMOTER_REC_EVENT_SIMILARITY_WEIGHT=5.0,
        PROMOTER_REC_SCALE_FIT_WEIGHT=5.0,
        PROMOTER_REC_ACTIVITY_WEIGHT=5.0,
        PROMOTER_REC_RECENCY_WEIGHT=5.0,
        PROMOTER_REC_STRENGTH_MATCHED_ARTIST_WEIGHT=70.0,
        PROMOTER_REC_STRENGTH_EVENT_WEIGHT=30.0,
        PROMOTER_REC_STRENGTH_MATCHED_ARTIST_CAP=6,
        PROMOTER_REC_STRENGTH_EVENT_CAP=24,
        PROMOTER_REC_WARM_CONNECTION_CAP=5,
        PROMOTER_REC_MANUAL_WARM_CONNECTION_CAP=2,
        PROMOTER_REC_MANUAL_WARM_MIN_ARTIST_SEMANTIC_SCORE=0.52,
        PROMOTER_REC_EVENT_SIMILARITY_COUNT_CAP=9,
        PROMOTER_REC_EVENT_SIMILARITY_MIN_TOTAL_SCORE=0.58,
        PROMOTER_REC_EVENT_SIMILARITY_MIN_EMBEDDING_SCORE=0.41,
        PROMOTER_REC_EVENT_SIMILARITY_SEMANTIC_ONLY=False,
        PROMOTER_REC_EVENT_SIMILARITY_PER_PROMOTER_LIMIT=12,
        PROMOTER_REC_EVENT_SIMILARITY_SYMBOLIC_WEIGHT=55.0,
        PROMOTER_REC_EVENT_SIMILARITY_EMBEDDING_WEIGHT=45.0,
        PROMOTER_REC_EVENT_SIMILARITY_SAME_VENUE_WEIGHT=40.0,
        PROMOTER_REC_EVENT_SIMILARITY_SHARED_GENRE_WEIGHT=10.0,
        PROMOTER_REC_EVENT_SIMILARITY_SHARED_LINEUP_WEIGHT=30.0,
        PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_GENRE_WEIGHT=20.0,
        PROMOTER_REC_ACTIVITY_EVENT_CAP=30,
        PROMOTER_REC_WARM_RELEVANT_CONNECTION_MIN=1,
        PROMOTER_REC_WARM_EDGE_STRENGTH_MIN=0.45,
        PROMOTER_REC_WARM_EDGE_STRENGTH_MAX=0.78,
        PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MIN=0.22,
        PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MAX=0.66,
        PROMOTER_REC_SCALE_FIT_ALPHA=80.0,
        PROMOTER_REC_SCALE_FIT_TAU=0.6,
        PROMOTER_REC_SQL_CANDIDATE_LIMIT=260,
        PROMOTER_REC_SEMANTIC_ARTIST_POOL_LIMIT=21,
        PROMOTER_REC_SEMANTIC_ARTIST_MIN_SCORE=0.51,
        PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MULTIPLIER=24,
        PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MIN=640,
        PROMOTER_REC_SOURCE_EVENT_RELEVANCE_GATE_ENABLED=True,
        PROMOTER_REC_SOURCE_EVENT_RELEVANCE_MIN_EMBEDDING_SCORE=0.57,
        PROMOTER_REC_SOURCE_EVENT_RELEVANCE_TOP_K=4,
    )

    config = promoter_recommendation_scoring_from_config()

    assert config == PromoterRecommendationScoringConfig(
        semantic_weight=35 / 85,
        strength_weight=18 / 85,
        co_played_connection_weight=8 / 85,
        manual_connection_weight=4 / 85,
        event_similarity_weight=5 / 85,
        scale_fit_weight=5 / 85,
        activity_weight=5 / 85,
        recency_weight=5 / 85,
        strength_matched_artist_weight=0.70,
        strength_event_weight=0.30,
        strength_matched_artist_cap=6,
        strength_event_cap=24,
        warm_connection_cap=5,
        manual_warm_connection_cap=2,
        manual_warm_min_artist_semantic_score=0.52,
        event_similarity_count_cap=9,
        event_similarity_min_total_score=0.58,
        event_similarity_min_embedding_score=0.41,
        event_similarity_semantic_only=False,
        event_similarity_per_promoter_limit=12,
        event_similarity_symbolic_weight=0.55,
        event_similarity_embedding_weight=0.45,
        event_similarity_same_venue_weight=0.40,
        event_similarity_shared_genre_weight=0.10,
        event_similarity_shared_lineup_weight=0.30,
        event_similarity_extracted_genre_weight=0.20,
        activity_event_cap=30,
        warm_relevant_connection_min=1,
        warm_edge_strength_min=0.45,
        warm_edge_strength_max=0.78,
        event_similarity_edge_strength_min=0.22,
        event_similarity_edge_strength_max=0.66,
        scale_fit_alpha=80,
        scale_fit_tau=0.6,
        sql_candidate_limit=260,
        semantic_artist_pool_limit=21,
        semantic_artist_min_score=0.51,
        event_similarity_overfetch_multiplier=24,
        event_similarity_overfetch_min=640,
        source_event_relevance_gate_enabled=True,
        source_event_relevance_min_embedding_score=0.57,
        source_event_relevance_top_k=4,
    )


def test_recommendation_scoring_reads_event_graph_weights_from_env(monkeypatch):
    monkeypatch.setenv("EVENT_GRAPH_SHARED_ARTISTS_WEIGHT", "40")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_PROMOTERS_WEIGHT", "20")
    monkeypatch.setenv("EVENT_GRAPH_SAME_VENUE_WEIGHT", "5")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_GENRES_WEIGHT", "5")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_EXTRACTED_GENRES_WEIGHT", "30")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_EXTRACTED_GENRES_CAP", "4")

    config = recommendation_scoring_from_env()
    weights = {item.feature: item for item in config.event_graph_weights}

    assert round(weights["artists"].weight, 4) == 0.4
    assert round(weights["promoters"].weight, 4) == 0.2
    assert round(weights["venues"].weight, 4) == 0.05
    assert round(weights["genres"].weight, 4) == 0.05
    assert round(weights["extracted_genres"].weight, 4) == 0.3
    assert weights["extracted_genres"].cap == 4


def test_recommendation_scoring_supports_legacy_extracted_styles_env_keys(monkeypatch):
    monkeypatch.delenv("EVENT_GRAPH_SHARED_EXTRACTED_GENRES_WEIGHT", raising=False)
    monkeypatch.delenv("EVENT_GRAPH_SHARED_EXTRACTED_GENRES_CAP", raising=False)
    monkeypatch.setenv("EVENT_GRAPH_SHARED_ARTISTS_WEIGHT", "40")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_PROMOTERS_WEIGHT", "20")
    monkeypatch.setenv("EVENT_GRAPH_SAME_VENUE_WEIGHT", "5")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_GENRES_WEIGHT", "5")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_EXTRACTED_STYLES_WEIGHT", "30")
    monkeypatch.setenv("EVENT_GRAPH_SHARED_EXTRACTED_STYLES_CAP", "4")

    config = recommendation_scoring_from_env()
    weights = {item.feature: item for item in config.event_graph_weights}

    assert round(weights["artists"].weight, 4) == 0.4
    assert round(weights["promoters"].weight, 4) == 0.2
    assert round(weights["venues"].weight, 4) == 0.05
    assert round(weights["genres"].weight, 4) == 0.05
    assert round(weights["extracted_genres"].weight, 4) == 0.3
    assert weights["extracted_genres"].cap == 4


def test_promoter_recommendation_scoring_uses_config_genre_weight_without_alias(monkeypatch):
    _set_promoter_config(
        monkeypatch,
        PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_GENRE_WEIGHT=20.0,
        PROMOTER_REC_EVENT_SIMILARITY_SAME_VENUE_WEIGHT=40.0,
        PROMOTER_REC_EVENT_SIMILARITY_SHARED_GENRE_WEIGHT=10.0,
        PROMOTER_REC_EVENT_SIMILARITY_SHARED_LINEUP_WEIGHT=30.0,
    )

    config = promoter_recommendation_scoring_from_config()

    assert round(config.event_similarity_extracted_genre_weight, 4) == 0.2


def test_promoter_recommendation_api_limit_max_reads_config(monkeypatch):
    _set_promoter_config(monkeypatch, PROMOTER_REC_API_LIMIT_MAX=75)
    assert promoter_recommendation_api_limit_max_from_config() == 75


def test_promoter_segment_quota_ratios_read_from_config(monkeypatch):
    _set_promoter_config(
        monkeypatch,
        PROMOTER_REC_SEGMENT_QUOTA_SMALL_SMALL=0.7,
        PROMOTER_REC_SEGMENT_QUOTA_SMALL_MEDIUM=0.2,
        PROMOTER_REC_SEGMENT_QUOTA_SMALL_LARGE=0.1,
        PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_SMALL=0.2,
        PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_MEDIUM=0.5,
        PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_LARGE=0.3,
        PROMOTER_REC_SEGMENT_QUOTA_LARGE_SMALL=0.1,
        PROMOTER_REC_SEGMENT_QUOTA_LARGE_MEDIUM=0.2,
        PROMOTER_REC_SEGMENT_QUOTA_LARGE_LARGE=0.7,
    )

    ratios = promoter_segment_quota_ratios_from_config()

    assert ratios["small"]["small"] == pytest.approx(0.7)
    assert ratios["small"]["medium"] == pytest.approx(0.2)
    assert ratios["small"]["large"] == pytest.approx(0.1)
    assert ratios["medium"]["small"] == pytest.approx(0.2)
    assert ratios["medium"]["medium"] == pytest.approx(0.5)
    assert ratios["medium"]["large"] == pytest.approx(0.3)
    assert ratios["large"]["small"] == pytest.approx(0.1)
    assert ratios["large"]["medium"] == pytest.approx(0.2)
    assert ratios["large"]["large"] == pytest.approx(0.7)


def test_promoter_segment_warm_share_reads_config(monkeypatch):
    _set_promoter_config(monkeypatch, PROMOTER_REC_SEGMENT_WARM_SHARE=0.65)
    assert promoter_segment_warm_share_from_config() == 0.65


def test_artist_recommendation_min_semantic_score_reads_env(monkeypatch):
    monkeypatch.setenv("ARTIST_REC_MIN_SEMANTIC_SCORE", "0.52")
    assert artist_recommendation_min_semantic_score_from_env() == 0.52


def test_artist_recommendation_min_semantic_score_rejects_invalid(monkeypatch):
    monkeypatch.setenv("ARTIST_REC_MIN_SEMANTIC_SCORE", "1.2")
    try:
        artist_recommendation_min_semantic_score_from_env()
    except ValueError as exc:
        assert "ARTIST_REC_MIN_SEMANTIC_SCORE" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_normalized_weights_rejects_zero_total():
    try:
        normalized_weights((0, 0, 0))
    except ValueError as exc:
        assert "greater than zero" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_artist_similarity_requires_graph_or_strong_semantic_evidence():
    assert not is_similarity_candidate_eligible("artist", 0.79, 0.0)
    assert is_similarity_candidate_eligible("artist", 0.80, 0.0)
    assert is_similarity_candidate_eligible("artist", 0.60, 0.1)


def test_event_similarity_allows_semantic_only_candidates():
    assert not is_similarity_candidate_eligible("event", 0.60, 0.0)
    assert is_similarity_candidate_eligible("event", 0.75, 0.0)
    assert is_similarity_candidate_eligible("event", 0.60, 0.08)


def test_promoter_recommendation_adjusted_score_keeps_warm_connections_above_discovery():
    warm_score = promoter_recommendation_adjusted_score(0.35, has_warm_path=True)
    discovery_score = promoter_recommendation_adjusted_score(0.90, has_warm_path=False)

    assert 0.0 <= discovery_score <= 1.0
    assert 0.0 <= warm_score <= 1.0
    assert warm_score > discovery_score
