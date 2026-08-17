from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


ADMIN_USER_ID = 95_101
ADMIN_USERNAME = f"registration-auto-approve-admin-{ADMIN_USER_ID}"

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(ADMIN_USER_ID)})}"}


def cleanup(username: str, email: str, artist_name: str) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM artist_claims
                WHERE user_id IN (SELECT id FROM users WHERE username = %s OR email = %s)
                   OR artist_id IN (SELECT id FROM artists WHERE name = %s)
                """,
                (username, email, artist_name),
            )
            cursor.execute("DELETE FROM users WHERE username = %s OR email = %s", (username, email))
            cursor.execute("DELETE FROM artists WHERE name = %s", (artist_name,))
            cursor.execute("DELETE FROM users WHERE id = %s", (ADMIN_USER_ID,))
            cursor.execute(
                "DELETE FROM app_settings WHERE setting_key = 'auto_approve_pending_users'",
            )
            connection.commit()


def seed_admin(username: str, email: str) -> None:
    cleanup(username, email, artist_name=f"auto-approve-{ADMIN_USER_ID}")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, status)
                VALUES (%s, %s, %s, 'test-password-hash', 'admin', 'approved')
                """,
                (
                    ADMIN_USER_ID,
                    ADMIN_USERNAME,
                    f"{ADMIN_USERNAME}@example.com",
                ),
            )
            connection.commit()


def test_registration_auto_approve_setting_returns_approved_status_and_user_record():
    username = "registration-auto-approve-user"
    email = "registration-auto-approve-user@example.com"
    artist_name = "Registration Auto Approve Artist"
    seed_admin(username, email)
    try:
        settings_response = client.put(
            "/api/admin/settings/registration",
            headers=admin_headers(),
            json={"auto_approve_pending_users": True},
        )
        assert settings_response.status_code == 200
        assert settings_response.json()["auto_approve_pending_users"] is True

        register_response = client.post(
            "/api/register",
            json={
                "email": email,
                "password": "Password123",
                "password_confirm": "Password123",
                "new_artist_name": artist_name,
            },
        )
        assert register_response.status_code == 200
        register_payload = register_response.json()
        assert register_payload["success"] is True
        assert register_payload["status"] == "approved"

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT users.username, users.email, users.status, users.artist_id, artists.name
                    FROM users
                    JOIN artists
                      ON artists.id = users.artist_id
                    WHERE users.email = %s
                    """,
                    (email,),
                )
                user_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT status, decided_by, instagram_url
                    FROM artist_claims
                    WHERE user_id = (SELECT id FROM users WHERE email = %s)
                      AND artist_id = (SELECT id FROM artists WHERE name = %s)
                    """,
                    (email, artist_name),
                )
                claim_row = cursor.fetchone()

        assert user_row["status"] == "approved"
        assert user_row["username"] == email
        assert user_row["email"] == email
        assert user_row["name"] == artist_name
        assert user_row["artist_id"] is not None
        assert claim_row["status"] == "approved"
        assert claim_row["decided_by"] is None
        assert claim_row["instagram_url"] is None

        login_response = client.post(
            "/api/login",
            json={"email": email, "password": "Password123"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["success"] is True
        assert login_response.json()["username"] == email
    finally:
        cleanup(username, email, artist_name)
