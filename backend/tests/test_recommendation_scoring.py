from app.recommendation_scoring import (
    DEFAULT_RECOMMENDATION_SCORING,
    final_recommendation_score,
    hybrid_graph_score,
    is_similarity_candidate_eligible,
)


def test_event_graph_score_uses_capped_overlap_counts():
    source = {
        "artists": {1, 2, 3, 4},
        "promoters": {10, 11},
        "venues": {20},
        "genres": {30, 31, 32},
    }
    candidate = {
        "artists": {1, 2},
        "promoters": {10, 11, 12},
        "venues": {20},
        "genres": {31},
    }

    score, reasons = hybrid_graph_score("event", source, candidate)

    assert round(score, 4) == round((2 / 3 * 0.45) + 0.25 + 0.20 + (1 / 3 * 0.10), 4)
    assert reasons == ["2 shared artists", "2 shared promoters", "same venue"]


def test_artist_graph_score_uses_default_config():
    source = {
        "events": {1, 2},
        "promoters": {10, 11, 12},
        "venues": {20},
        "genres": {30, 31},
    }
    candidate = {
        "events": {1, 2, 3},
        "promoters": {10},
        "venues": {21},
        "genres": {30, 31, 32},
    }

    score, reasons = hybrid_graph_score("artist", source, candidate)

    assert round(score, 4) == round(0.40 + (1 / 3 * 0.25) + (2 / 3 * 0.15), 4)
    assert reasons == ["2 played same events", "2 shared genres", "1 shared promoters"]


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


def test_artist_similarity_requires_graph_or_strong_semantic_evidence():
    assert not is_similarity_candidate_eligible("artist", 0.79, 0.0)
    assert is_similarity_candidate_eligible("artist", 0.80, 0.0)
    assert is_similarity_candidate_eligible("artist", 0.60, 0.1)


def test_event_similarity_allows_semantic_only_candidates():
    assert is_similarity_candidate_eligible("event", 0.60, 0.0)
