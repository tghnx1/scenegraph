from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app


ARTIST_ID = 96_003
RA_ARTIST_ID = "search-metadata-test-96003"
EVENT_ID = 96_004
EVENT_RA_ID = "search-metadata-test-event-96004"
PENDING_USER_ID = 96_005
PENDING_ARTIST_ID = 96_006
APPROVED_USER_ID = 96_007
APPROVED_ARTIST_ID = 96_008

client = TestClient(app)


def cleanup() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM event_artists WHERE artist_id = %s OR event_id = %s", (ARTIST_ID, EVENT_ID))
            cursor.execute("DELETE FROM artist_extracted_tags WHERE artist_id = %s", (ARTIST_ID,))
            cursor.execute("DELETE FROM events WHERE id = %s", (EVENT_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (ARTIST_ID,))
            cursor.execute("DELETE FROM users WHERE id IN (%s, %s)", (PENDING_USER_ID, APPROVED_USER_ID))
            cursor.execute("DELETE FROM artists WHERE id IN (%s, %s)", (PENDING_ARTIST_ID, APPROVED_ARTIST_ID))
            connection.commit()


def test_artist_search_includes_claim_disambiguation_metadata():
    cleanup()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name, biography)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (ARTIST_ID, RA_ARTIST_ID, "Search Metadata Artist", "A short test biography."),
                )
                cursor.execute(
                    """
                    INSERT INTO artist_extracted_tags
                        (artist_id, tag_type, tag_value, source, confidence, extractor)
                    VALUES
                        (%s, 'style', 'techno', 'biography', 0.91, 'llm_artist_tags_v2:test'),
                        (%s, 'style', 'house', 'biography', 0.72, 'llm_artist_tags_v2:test')
                    """,
                    (ARTIST_ID, ARTIST_ID),
                )
                cursor.execute(
                    """
                    INSERT INTO events (id, ra_event_id, title, event_date)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (EVENT_ID, EVENT_RA_ID, "Search Metadata Latest Event", "2026-07-05T00:00:00+00:00"),
                )
                cursor.execute(
                    "INSERT INTO event_artists (event_id, artist_id) VALUES (%s, %s)",
                    (EVENT_ID, ARTIST_ID),
                )
                connection.commit()

        response = client.get("/api/search", params={"q": "Search Metadata", "type": "artist"})

        assert response.status_code == 200
        artist = next(result for result in response.json()["results"] if result["id"] == ARTIST_ID)
        assert artist["ra_artist_id"] == RA_ARTIST_ID
        assert artist["event_count"] == 1
        assert artist["has_biography"] is True
        assert artist["genres"] == ["techno", "house"]
        assert artist["biography_preview"] is not None
        assert "biography" in artist["biography_preview"].lower()
        assert artist["latest_event_title"] == "Search Metadata Latest Event"
        assert artist["latest_event_date"] == "2026-07-05"
    finally:
        cleanup()


def test_artist_search_returns_case_insensitive_exact_matches():
    cleanup()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name)
                    VALUES (%s, %s, %s)
                    """,
                    (ARTIST_ID, RA_ARTIST_ID, "Exact Match Artist"),
                )
                connection.commit()

        response = client.get("/api/search", params={"q": "exact match artist", "type": "artist"})

        assert response.status_code == 200
        results = response.json()["results"]
        assert any(result["id"] == ARTIST_ID and result["name"] == "Exact Match Artist" for result in results)
    finally:
        cleanup()


def test_artist_search_hides_pending_user_created_profiles():
    cleanup()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name)
                    VALUES (%s, NULL, %s)
                    """,
                    (PENDING_ARTIST_ID, "Pending Search Artist"),
                )
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status, artist_id)
                    VALUES (%s, %s, %s, 'hash', 'artist', 'pending', %s)
                    """,
                    (
                        PENDING_USER_ID,
                        "pending-search-artist-user",
                        "pending-search-artist-user@example.com",
                        PENDING_ARTIST_ID,
                    ),
                )
                connection.commit()

        response = client.get("/api/search", params={"q": "Pending Search Artist", "type": "artist"})

        assert response.status_code == 200
        assert response.json()["results"] == []
    finally:
        cleanup()


def test_artist_search_shows_approved_user_created_profiles():
    cleanup()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name)
                    VALUES (%s, NULL, %s)
                    """,
                    (APPROVED_ARTIST_ID, "Approved Search Artist"),
                )
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status, artist_id)
                    VALUES (%s, %s, %s, 'hash', 'artist', 'approved', %s)
                    """,
                    (
                        APPROVED_USER_ID,
                        "approved-search-artist-user",
                        "approved-search-artist-user@example.com",
                        APPROVED_ARTIST_ID,
                    ),
                )
                connection.commit()

        response = client.get("/api/search", params={"q": "Approved Search Artist", "type": "artist"})

        assert response.status_code == 200
        results = response.json()["results"]
        assert any(result["id"] == APPROVED_ARTIST_ID for result in results)
    finally:
        cleanup()
