from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


ADMIN_USER_ID = 95_001
ARTIST_ID = 95_002

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(ADMIN_USER_ID)})}"}


def cleanup(username: str, email: str) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM artist_claims
                WHERE user_id IN (SELECT id FROM users WHERE username = %s OR email = %s)
                   OR artist_id = %s
                """,
                (username, email, ARTIST_ID),
            )
            cursor.execute("DELETE FROM users WHERE username = %s OR email = %s", (username, email))
            cursor.execute("DELETE FROM users WHERE id = %s", (ADMIN_USER_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (ARTIST_ID,))


def seed_admin_and_artist(username: str, email: str) -> None:
    cleanup(username, email)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name)
                VALUES (%s, %s, %s)
                """,
                (ARTIST_ID, f"registration-claim-test-{ARTIST_ID}", "Registration Claim Artist"),
            )
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, status)
                VALUES (%s, %s, %s, 'test-password-hash', 'admin', 'approved')
                """,
                (
                    ADMIN_USER_ID,
                    f"registration-claim-admin-{ADMIN_USER_ID}",
                    f"registration-claim-admin-{ADMIN_USER_ID}@example.com",
                ),
            )


def test_artist_registration_claim_is_approved_with_user_once():
    username = "registration-claim-user"
    email = "registration-claim-user@example.com"
    seed_admin_and_artist(username, email)
    try:
        register_response = client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "password": "Password123",
                "password_confirm": "Password123",
                "role": "artist",
                "artist_id": ARTIST_ID,
            },
        )
        assert register_response.status_code == 200
        register_payload = register_response.json()
        assert register_payload["success"] is True
        user_id = register_payload["user_id"]

        pending_response = client.get("/api/admin/users/pending", headers=admin_headers())
        assert pending_response.status_code == 200
        pending_user = next(
            user for user in pending_response.json()["users"]
            if user["id"] == user_id
        )
        assert pending_user["artist_id"] == ARTIST_ID
        assert pending_user["artist_name"] == "Registration Claim Artist"

        approve_response = client.post(f"/api/admin/users/{user_id}/approve", headers=admin_headers())
        assert approve_response.status_code == 200
        assert approve_response.json()["success"] is True

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, artist_id
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                user_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT status, decided_by
                    FROM artist_claims
                    WHERE user_id = %s
                      AND artist_id = %s
                    """,
                    (user_id, ARTIST_ID),
                )
                claim_row = cursor.fetchone()

        assert user_row["status"] == "approved"
        assert user_row["artist_id"] == ARTIST_ID
        assert claim_row["status"] == "approved"
        assert claim_row["decided_by"] == ADMIN_USER_ID
    finally:
        cleanup(username, email)


def test_artist_registration_requires_artist_profile_selection():
    response = client.post(
        "/api/register",
        json={
            "username": "claim_missing_artist",
            "email": "registration-claim-missing-artist@example.com",
            "password": "Password123",
            "password_confirm": "Password123",
            "role": "artist",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "message": "Please select your artist profile",
    }
