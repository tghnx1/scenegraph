from app.text_profiles import (
    compose_artist_text_profile,
    compose_event_text_profile,
    build_event_text_profile,
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

    assert "Description: Bass-heavy electro and breaks." in profile
    assert "Genres: Techno, Electro" in profile
    assert "Extracted genres: bass, breakbeat, electro" in profile
    assert "Venue: Club Ost" in profile
    assert "Promoters: Emotional Voyage" in profile
    assert "Event title:" not in profile
    assert "Structured lineup:" not in profile
    assert "Lineup context:" not in profile


def test_event_text_profile_prioritizes_saved_event_genres_over_raw_text():
    profile = compose_event_text_profile(
        {
            "title": "Acid Night",
            "description_text": "acid techno and rave in the room",
            "lineup_raw": "DJ A",
            "lineup_residual_text": "",
        },
        artist_names=["DJ A"],
        promoter_names=["Promoter X"],
        genre_names=["Warehouse"],
        venue_name="Club Ost",
        extracted_genres=["dark disco", "ebm"],
    )

    assert profile.startswith("Extracted genres: dark disco, ebm")
    assert profile.index("Extracted genres: dark disco, ebm") < profile.index(
        "Description: acid techno and rave in the room"
    )
    assert "Event title:" not in profile


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


class FakeCursor:
    def __init__(self):
        self.last_query = ""
        self.last_params = None
        self.event_row = None
        self.artist_rows = []
        self.promoter_rows = []
        self.genre_rows = []
        self.extracted_genre_rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, query, params=None):
        self.last_query = " ".join(query.split())
        self.last_params = params

    def fetchone(self):
        if "to_regclass('public.event_extracted_genres')" in self.last_query:
            return {"table_name": "event_extracted_genres"}
        if "FROM events e" in self.last_query:
            return self.event_row
        raise AssertionError(f"Unexpected fetchone query: {self.last_query}")

    def fetchall(self):
        if "JOIN event_artists ea" in self.last_query:
            return self.artist_rows
        if "FROM promoters p" in self.last_query:
            return self.promoter_rows
        if "FROM genres g" in self.last_query:
            return self.genre_rows
        if "FROM event_extracted_tags" in self.last_query:
            return self.extracted_genre_rows
        raise AssertionError(f"Unexpected fetchall query: {self.last_query}")


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


def test_build_event_text_profile_uses_saved_event_genres():
    connection = FakeConnection()
    connection.cursor_instance.event_row = {
        "id": 1,
        "title": "Acid Night",
        "description_text": "acid techno and rave in the room",
        "lineup_raw": "DJ A",
        "lineup_residual_text": "",
        "venue_name": "Club Ost",
    }
    connection.cursor_instance.artist_rows = [{"name": "DJ A"}]
    connection.cursor_instance.promoter_rows = [{"name": "Promoter X"}]
    connection.cursor_instance.genre_rows = [{"name": "Warehouse"}]
    connection.cursor_instance.extracted_genre_rows = [
        {"event_id": 1, "tag_type": "style", "tag_value": "dark disco", "confidence": 0.9},
        {"event_id": 1, "tag_type": "style", "tag_value": "ebm", "confidence": 0.8},
    ]

    profile = build_event_text_profile(connection, 1)

    assert "Extracted genres: dark disco, ebm" in profile
    assert "Extracted genres: acid" not in profile


def test_build_event_text_profile_includes_saved_event_theme_and_mood():
    connection = FakeConnection()
    connection.cursor_instance.event_row = {
        "id": 2,
        "title": "Safe & Queer Night",
        "description_text": "inclusive and energetic party",
        "lineup_raw": "DJ A",
        "lineup_residual_text": "",
        "venue_name": "Club Ost",
    }
    connection.cursor_instance.artist_rows = [{"name": "DJ A"}]
    connection.cursor_instance.promoter_rows = [{"name": "Promoter X"}]
    connection.cursor_instance.genre_rows = [{"name": "Warehouse"}]
    connection.cursor_instance.extracted_genre_rows = [
        {"event_id": 2, "tag_type": "style", "tag_value": "dark disco", "confidence": 0.9},
        {"event_id": 2, "tag_type": "theme", "tag_value": "queer", "confidence": 0.9},
        {"event_id": 2, "tag_type": "mood", "tag_value": "energetic", "confidence": 0.9},
    ]

    profile = build_event_text_profile(connection, 2)

    assert "Extracted genres: dark disco" in profile
    assert "Extracted themes: queer" in profile
    assert "Extracted moods: energetic" in profile
    assert profile.index("Extracted genres: dark disco") < profile.index(
        "Description: inclusive and energetic party"
    )
