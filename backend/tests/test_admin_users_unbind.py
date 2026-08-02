from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


ADMIN_USER_ID = 96_001
TEMP_USER_ID = 96_002
TEMP_ARTIST_ID = 96_003
TEMP_CLAIM_ID = 96_004

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(ADMIN_USER_ID)})}"}


def cleanup() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM activity_log WHERE username = %s OR target = %s", ("admin-unbind-test", "unbind-user"))
            cursor.execute("DELETE FROM artist_claims WHERE id = %s", (TEMP_CLAIM_ID,))
            cursor.execute("DELETE FROM users WHERE id IN (%s, %s)", (ADMIN_USER_ID, TEMP_USER_ID))
            cursor.execute("DELETE FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))
            connection.commit()


def test_unbind_artist_removes_user_artist_link_and_claim_but_preserves_artist():
    cleanup()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status)
                    VALUES (%s, %s, %s, 'hash', 'admin', 'approved')
                    """,
                    (ADMIN_USER_ID, "admin-unbind-test", "admin-unbind-test@example.com"),
                )
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name)
                    VALUES (%s, %s, %s)
                    """,
                    (TEMP_ARTIST_ID, "unbind-test-ra-artist", "Unbind Test Artist"),
                )
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status, artist_id)
                    VALUES (%s, %s, %s, 'hash', 'artist', 'approved', %s)
                    """,
                    (
                        TEMP_USER_ID,
                        "unbind-user",
                        "unbind-user@example.com",
                        TEMP_ARTIST_ID,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO artist_claims (id, user_id, artist_id, instagram_url, status, reason)
                    VALUES (%s, %s, %s, %s, 'approved', %s)
                    """,
                    (
                        TEMP_CLAIM_ID,
                        TEMP_USER_ID,
                        TEMP_ARTIST_ID,
                        "https://www.instagram.com/unbinduser/",
                        "Unbind test",
                    ),
                )
                connection.commit()

        response = client.post(f"/api/admin/users/{TEMP_USER_ID}/unbind-artist", headers=admin_headers())
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["message"] == "Artist unbound"
        assert payload["user"]["artist_id"] is None

        users_response = client.get("/api/admin/users", headers=admin_headers())
        assert users_response.status_code == 200
        user_row = next(user for user in users_response.json()["users"] if user["id"] == TEMP_USER_ID)
        assert user_row["artist_id"] is None
        assert user_row["artist_name"] is None
        assert user_row["artist_instagram_url"] is None

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status, artist_id FROM users WHERE id = %s", (TEMP_USER_ID,))
                stored_user = cursor.fetchone()
                cursor.execute("SELECT id FROM artist_claims WHERE id = %s", (TEMP_CLAIM_ID,))
                claim_row = cursor.fetchone()
                cursor.execute("SELECT id, username, event_type, target FROM activity_log WHERE event_type = 'artist unbound from account' ORDER BY id DESC LIMIT 1")
                activity_row = cursor.fetchone()
                cursor.execute("SELECT id, ra_artist_id FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))
                artist_row = cursor.fetchone()

        assert stored_user["status"] == "approved"
        assert stored_user["artist_id"] is None
        assert claim_row is None
        assert artist_row is not None
        assert artist_row["ra_artist_id"] == "unbind-test-ra-artist"
        assert activity_row is not None
        assert activity_row["username"] == "admin-unbind-test"
        assert activity_row["target"] == "unbind-user"
    finally:
        cleanup()
