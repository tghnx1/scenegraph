from app.text_profiles import (
    compose_artist_text_profile,
    compose_event_text_profile,
    normalize_biography_text,
    normalize_text,
    rank_recurring_names,
    truncate_text,
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


def test_truncate_text_caps_at_word_boundary():
    assert truncate_text("one two three four", 11) == "one two..."
    assert truncate_text("short text", 100) == "short text"


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
        genre_names=["Techno", "Electro"],
        venue_name="Club Ost",
    )

    assert "Event title: CYBERFLEX" in profile
    assert "Description: Bass-heavy electro and breaks." in profile
    assert "Genres: Techno, Electro" in profile
    assert "Extracted genres: bass, breakbeat, electro" in profile
    assert "Structured lineup: BabaBass3000, Structured Artist" in profile
    assert "Lineup context: Guest Artist live" in profile
    assert "Raw lineup:" not in profile
    assert "Venue: Club Ost" in profile
    assert "Promoters: Emotional Voyage" in profile


def test_artist_text_profile_uses_intrinsic_artist_text_only():
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
    assert "Styles: bass, electro, leftfield" in profile
    assert "Played event titles:" not in profile
    assert "Played event descriptions:" not in profile
    assert "Played event lineup context:" not in profile
    assert "Recurring venues:" not in profile
    assert "Recurring promoters:" not in profile
    assert "CYBERFLEX" not in profile


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


def test_artist_text_profile_includes_extracted_tags():
    profile = compose_artist_text_profile(
        {
            "name": "Tagged Artist",
            "biography": "Dark disco producer.",
            "biography_normalized": None,
        },
        extracted_tags={
            "style": ["ebm"],
            "label": ["Laut & Luise"],
            "collective": ["Local Crew"],
            "role": ["producer"],
            "residency": ["Radio Night"],
        },
    )

    assert "Styles: dark disco, ebm" in profile
    assert "Labels: Laut & Luise" in profile
    assert "Collectives: Local Crew" in profile
    assert "Roles: producer" in profile
    assert "Residencies: Radio Night" in profile


def test_artist_text_profile_recanonicalizes_stored_style_tags():
    profile = compose_artist_text_profile(
        {
            "name": "Tagged Artist",
            "biography": "No explicit genre.",
            "biography_normalized": None,
        },
        extracted_tags={"style": ["dnb", "drum & bass", "sensual deep electric"]},
    )

    assert "Styles: drum and bass" in profile
    assert "dnb" not in profile
    assert "sensual deep electric" not in profile


def test_artist_text_profile_caps_long_biography():
    profile = compose_artist_text_profile(
        {
            "name": "Long Bio Artist",
            "biography": " ".join(["word"] * 2000),
            "biography_normalized": None,
        },
    )

    assert len(profile) < 5500
    assert profile.endswith("...")


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
    assert "Played event titles:" not in profile
    assert "Warehouse Night" not in profile


def test_rank_recurring_names_sorts_by_frequency_then_name():
    assert rank_recurring_names(["RSO", "Club Ost", "RSO", "about blank", "Club Ost", "RSO"]) == [
        "RSO",
        "Club Ost",
        "about blank",
    ]
