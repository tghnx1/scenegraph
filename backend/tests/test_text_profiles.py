from app.text_profiles import (
    compose_artist_text_profile,
    compose_event_text_profile,
    normalize_biography_text,
    normalize_text,
    rank_recurring_names,
)


def test_normalize_text_collapses_whitespace():
    assert normalize_text("  dark\n\n electro\t night  ") == "dark electro night"
    assert normalize_text(None) == ""


def test_normalize_biography_text_drops_ra_prefix():
    assert (
        normalize_biography_text("̸ BIOGRAPHY 🌙 MUTANTE DEL SWANA 🌙\nBlitz Munich resident.")
        == "🌙 MUTANTE DEL SWANA 🌙 Blitz Munich resident."
    )
    assert normalize_biography_text("Biography: Leftfield electro.") == "Leftfield electro."
    assert normalize_biography_text(None) == ""


def test_event_text_profile_uses_structured_and_residual_lineup():
    profile = compose_event_text_profile(
        {
            "title": "CYBERFLEX",
            "description_text": "Bass-heavy electro and breaks.",
            "lineup_raw": "BabaBass3000 b2b Guest Artist",
            "lineup_residual_text": "Guest Artist live",
        },
        artist_names=["BabaBass3000", "Structured Artist"],
        promoter_names=["Emotional Voyage"],
        venue_name="Club Ost",
    )

    assert "Event title: CYBERFLEX" in profile
    assert "Description: Bass-heavy electro and breaks." in profile
    assert "Structured lineup: BabaBass3000, Structured Artist" in profile
    assert "Lineup context: Guest Artist live" in profile
    assert "Raw lineup:" not in profile
    assert "Venue: Club Ost" in profile
    assert "Promoters: Emotional Voyage" in profile


def test_artist_text_profile_combines_biography_and_event_context():
    profile = compose_artist_text_profile(
        {
            "name": "BabaBass3000",
            "biography": "Leftfield electro and bass-focused club music.",
            "biography_normalized": None,
        },
        event_contexts=[
            {
                "title": "CYBERFLEX",
                "description_text": "Fast electro pressure.",
                "lineup_raw": "BabaBass3000, Artist X",
                "lineup_residual_text": "Artist X",
            },
            {
                "title": "Emotional Voyage",
                "description_text": "Breaks, bass, and trippy club sounds.",
                "lineup_raw": "BabaBass3000 b2b Artist Y",
                "lineup_residual_text": "Artist Y live",
            },
        ],
        venue_names=["Club Ost", "RSO", "Club Ost"],
        promoter_names=["Emotional Voyage", "Emotional Voyage", "CYBERFLEX"],
    )

    assert "Artist name: BabaBass3000" in profile
    assert "Biography: Leftfield electro and bass-focused club music." in profile
    assert "Played event titles: CYBERFLEX, Emotional Voyage" in profile
    assert "Played event descriptions: Fast electro pressure." in profile
    assert "Breaks, bass, and trippy club sounds." in profile
    assert "Played event lineup context: Artist X, Artist Y live" in profile
    assert "Recurring venues: Club Ost, RSO" in profile
    assert "Recurring promoters: Emotional Voyage, CYBERFLEX" in profile


def test_artist_text_profile_prefers_stored_normalized_biography():
    profile = compose_artist_text_profile(
        {
            "name": "Stored Bio Artist",
            "biography": "̸ BIOGRAPHY Raw bio should not be used.",
            "biography_normalized": "Clean stored bio.",
        },
    )

    assert "Biography: Clean stored bio." in profile
    assert "Raw bio should not be used." not in profile


def test_artist_text_profile_works_without_biography():
    profile = compose_artist_text_profile(
        {"name": "No Bio Artist", "biography": None},
        event_contexts=[
            {
                "title": "Warehouse Night",
                "description_text": "Industrial club music.",
                "lineup_raw": "",
            },
        ],
        venue_names=[],
        promoter_names=[],
    )

    assert "Artist name: No Bio Artist" in profile
    assert "Biography:" not in profile
    assert "Played event titles: Warehouse Night" in profile
    assert "Played event descriptions: Industrial club music." in profile


def test_rank_recurring_names_sorts_by_frequency_then_name():
    assert rank_recurring_names(["RSO", "Club Ost", "RSO", "about blank", "Club Ost", "RSO"]) == [
        "RSO",
        "Club Ost",
        "about blank",
    ]
