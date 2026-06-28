from collections.abc import Generator

from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


ADMIN_USER_ID = 1
TEMP_USER_ID = 94_001
TEMP_ARTIST_ID = 94_002

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(ADMIN_USER_ID)})}"}


def temp_user_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(TEMP_USER_ID)})}"}


def _cleanup() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (TEMP_USER_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))


def _seed_user() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (TEMP_USER_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name)
                VALUES (%s, %s, %s)
                """,
                (
                    TEMP_ARTIST_ID,
                    f"admin-deactivate-test-artist-{TEMP_ARTIST_ID}",
                    "Admin Deactivate Test Artist",
                ),
            )
            cursor.execute(
                """
                INSERT INTO users (
                    id,
                    username,
                    email,
                    password_hash,
                    role,
                    status,
                    artist_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    TEMP_USER_ID,
                    f"admin-deactivate-test-user-{TEMP_USER_ID}",
                    f"admin-deactivate-test-user-{TEMP_USER_ID}@example.com",
                    "hash",
                    "artist",
                    "approved",
                    TEMP_ARTIST_ID,
                ),
            )


def test_deactivate_user_unclaims_artist_profile():
    _seed_user()
    try:
        response = client.post(
            f"/api/admin/users/{TEMP_USER_ID}/deactivate",
            headers=admin_headers(),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["user"]["status"] == "deactivated"
        assert payload["user"]["artist_id"] is None

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status, artist_id FROM users WHERE id = %s",
                    (TEMP_USER_ID,),
                )
                row = cursor.fetchone()

        assert row is not None
        assert row["status"] == "deactivated"
        assert row["artist_id"] is None

        protected_response = client.get("/api/me", headers=temp_user_headers())
        assert protected_response.status_code == 403
    finally:
        _cleanup()
