from app.promoter_graph import promoter_recommendation_reasons, promoter_recommendation_status
from app.recommendation_scoring import DEFAULT_PROMOTER_RECOMMENDATION_SCORING


def test_promoter_recommendation_reasons_use_displayed_titles_count_for_event_reasons():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 0,
        "matched_artist_count": 0,
        "event_similarity_count": 1,
        "event_similarity_event_titles": ["A", "B"],
        "event_count": 1,
        "related_event_titles": ["A", "B", "C"],
        "latest_event_date": None,
    }

    reasons = promoter_recommendation_reasons(row)

    assert reasons == [
        "2 similar promoter events: A, B",
        "3 related promoter events: A, B, C",
    ]


def test_promoter_recommendation_reasons_show_manual_even_without_coplayed():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 0,
        "manual_warm_connection_count": 1,
        "matched_artist_count": 0,
        "event_similarity_count": 0,
        "event_count": 0,
        "latest_event_date": None,
    }

    reasons = promoter_recommendation_reasons(row)

    assert reasons == ["1 manually added trusted artist links"]


def test_promoter_recommendation_status_marks_manual_as_warm_relevant():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 0,
        "manual_warm_connection_count": 1,
    }

    status = promoter_recommendation_status(row, DEFAULT_PROMOTER_RECOMMENDATION_SCORING)

    assert status == "warm_relevant"
