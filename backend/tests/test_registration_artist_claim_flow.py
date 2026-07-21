from fastapi.testclient import TestClient

from app.auth import create_access_token, rate_limit_attempts
from app.db import get_connection
from app.main import app


ADMIN_USER_ID = 95_001
ARTIST_ID = 95_002
EXISTING_ARTIST_NAME = "Registration Claim Artist"
NEW_ARTIST_NAME = "Registration New Artist"
DUPLICATE_ARTIST_NAME = "Registration Duplicate Display Name"

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(ADMIN_USER_ID)})}"}


def cleanup(username: str, email: str, *, artist_name: str | None = None) -> None:
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
            if artist_name is not None:
                cursor.execute("DELETE FROM artist_claims WHERE artist_id IN (SELECT id FROM artists WHERE name = %s)", (artist_name,))
            cursor.execute("DELETE FROM users WHERE username = %s OR email = %s", (username, email))
            cursor.execute("DELETE FROM users WHERE artist_id = %s", (ARTIST_ID,))
            cursor.execute("DELETE FROM artist_claims WHERE artist_id = %s", (ARTIST_ID,))
            cursor.execute(
                """
                DELETE FROM artist_claims
                WHERE instagram_url ILIKE ANY(%s)
                """,
                ([ 
                    "%registrationclaimuser%",
                    "%registrationnewartist%",
                    "%registrationduplicateinstagram%",
                    "%registrationduplicateartistone%",
                    "%registrationduplicateartisttwo%",
                    "%registrationduplicatename%",
                    "%registrationrejectnewartist%",
                ],),
            )
            cursor.execute("DELETE FROM users WHERE id = %s", (ADMIN_USER_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (ARTIST_ID,))
            if artist_name is not None:
                cursor.execute("DELETE FROM artists WHERE name = %s", (artist_name,))
            cursor.execute(
                "DELETE FROM artists WHERE ra_artist_id IN (%s, %s)",
                (f"registration-claim-test-{ARTIST_ID}", f"registration-duplicate-name-test-{ARTIST_ID + 1}"),
            )
            connection.commit()
    rate_limit_attempts.pop(f"register:{email}", None)


def seed_admin_and_existing_artist(username: str, email: str) -> None:
    cleanup(username, email, artist_name=NEW_ARTIST_NAME)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name)
                VALUES (%s, %s, %s)
                """,
                (ARTIST_ID, f"registration-claim-test-{ARTIST_ID}", EXISTING_ARTIST_NAME),
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
            connection.commit()
            connection.commit()


def seed_admin(username: str, email: str) -> None:
    cleanup(username, email, artist_name=NEW_ARTIST_NAME)
    with get_connection() as connection:
        with connection.cursor() as cursor:
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
            connection.commit()
            connection.commit()


def test_artist_registration_claim_is_approved_with_user_once():
    username = "registration-claim-user"
    email = "registration-claim-user@example.com"
    seed_admin_and_existing_artist(username, email)
    try:
        register_response = client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "instagram_url": "https://www.instagram.com/registrationclaimuser",
                "password": "Password123",
                "password_confirm": "Password123",
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
        assert pending_user["artist_name"] == EXISTING_ARTIST_NAME
        assert pending_user["artist_source"] == "resident_advisor"
        assert pending_user["artist_instagram_url"] == "https://www.instagram.com/registrationclaimuser/"

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


def test_artist_registration_can_create_new_artist_profile_and_pending_claim():
    username = "registration-new-artist-user"
    email = "registration-new-artist-user@example.com"
    seed_admin(username, email)
    try:
        register_response = client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "instagram_url": "https://www.instagram.com/registrationnewartist",
                "password": "Password123",
                "password_confirm": "Password123",
                "new_artist_name": NEW_ARTIST_NAME,
            },
        )
        assert register_response.status_code == 200
        register_payload = register_response.json()
        assert register_payload["success"] is True
        user_id = register_payload["user_id"]

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, ra_artist_id, name, content_url
                    FROM artists
                    WHERE name = %s
                    """,
                    (NEW_ARTIST_NAME,),
                )
                artist_row = cursor.fetchone()

        assert artist_row is not None
        assert artist_row["ra_artist_id"] is None
        assert artist_row["content_url"] is None

        pending_response = client.get("/api/admin/users/pending", headers=admin_headers())
        assert pending_response.status_code == 200
        pending_user = next(
            user for user in pending_response.json()["users"]
            if user["id"] == user_id
        )
        assert pending_user["artist_name"] == NEW_ARTIST_NAME
        assert pending_user["artist_source"] == "user_created"
        assert pending_user["artist_instagram_url"] == "https://www.instagram.com/registrationnewartist/"

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
                    (user_id, artist_row["id"]),
                )
                claim_row = cursor.fetchone()

        assert user_row["status"] == "approved"
        assert user_row["artist_id"] == artist_row["id"]
        assert claim_row["status"] == "approved"
        assert claim_row["decided_by"] == ADMIN_USER_ID
    finally:
        cleanup(username, email, artist_name=NEW_ARTIST_NAME)


def test_artist_registration_allows_duplicate_display_names():
    username = "registration-duplicate-name-user"
    email = "registration-duplicate-name-user@example.com"
    seed_admin_and_existing_artist(username, email)
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM artists WHERE ra_artist_id = %s", (f"registration-duplicate-name-test-{ARTIST_ID + 1}",))
                cursor.execute(
                    """
                    INSERT INTO artists (ra_artist_id, name)
                    VALUES (%s, %s)
                    """,
                    (f"registration-duplicate-name-test-{ARTIST_ID + 1}", DUPLICATE_ARTIST_NAME),
                )

        register_response = client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "instagram_url": "https://www.instagram.com/registrationduplicatename",
                "password": "Password123",
                "password_confirm": "Password123",
                "new_artist_name": DUPLICATE_ARTIST_NAME,
            },
        )

        assert register_response.status_code == 200
        assert register_response.json()["success"] is True

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, ra_artist_id, name
                    FROM artists
                    WHERE name = %s
                    ORDER BY id
                    """,
                    (DUPLICATE_ARTIST_NAME,),
                )
                artist_rows = cursor.fetchall()

        assert len(artist_rows) == 2
        assert artist_rows[0]["name"] == DUPLICATE_ARTIST_NAME
        assert artist_rows[1]["name"] == DUPLICATE_ARTIST_NAME
        assert any(row["ra_artist_id"] is None for row in artist_rows)
        assert any(row["ra_artist_id"] is not None for row in artist_rows)
    finally:
        cleanup(username, email, artist_name=DUPLICATE_ARTIST_NAME)


def test_artist_registration_rejects_duplicate_artist_claim_targets():
    username = "dup-artist-user"
    email = "dup-artist-user@example.com"
    seed_admin_and_existing_artist(username, email)
    try:
        first_response = client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "instagram_url": "https://www.instagram.com/registrationduplicateartistone",
                "password": "Password123",
                "password_confirm": "Password123",
                "artist_id": ARTIST_ID,
            },
        )
        assert first_response.status_code == 200
        assert first_response.json()["success"] is True

        second_response = client.post(
            "/api/register",
            json={
                "username": "dup-artist-user2",
                "email": "dup-artist-user2@example.com",
                "instagram_url": "https://www.instagram.com/registrationduplicateartisttwo",
                "password": "Password123",
                "password_confirm": "Password123",
                "artist_id": ARTIST_ID,
            },
        )

        assert second_response.status_code == 200
        assert second_response.json() == {
            "success": False,
            "message": "This artist profile already has a registration in progress",
        }
    finally:
        cleanup(username, email)
        cleanup("dup-artist-user2", "dup-artist-user2@example.com")


def test_artist_registration_rejects_duplicate_instagram_url():
    username = "dup-inst-user"
    email = "dup-inst-user@example.com"
    second_username = "dup-inst-user2"
    second_email = "dup-inst-user2@example.com"
    first_artist_name = NEW_ARTIST_NAME
    second_artist_name = "Registration Orphan Artist"
    seed_admin(username, email)
    try:
        first_response = client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "instagram_url": "https://m.instagram.com/RegistrationDuplicateInstagram/?igsh=123",
                "password": "Password123",
                "password_confirm": "Password123",
                "new_artist_name": first_artist_name,
            },
        )
        assert first_response.status_code == 200
        first_payload = first_response.json()
        assert first_payload["success"] is True
        first_user_id = first_payload["user_id"]

        second_response = client.post(
            "/api/register",
            json={
                "username": second_username,
                "email": second_email,
                "instagram_url": "https://www.instagram.com/registrationduplicateinstagram/",
                "password": "Password123",
                "password_confirm": "Password123",
                "new_artist_name": second_artist_name,
            },
        )

        assert second_response.status_code == 200
        assert second_response.json() == {
            "success": False,
            "message": "This Instagram URL is already used by another registration",
        }

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM artists
                    WHERE name = %s
                    """,
                    (second_artist_name,),
                )
                second_artist_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT instagram_url
                    FROM artist_claims
                    WHERE user_id = %s
                    """,
                    (first_user_id,),
                )
                first_claim_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE username = %s OR email = %s
                    """,
                    (second_username, second_email),
                )
                second_user_row = cursor.fetchone()

        assert second_artist_row is None
        assert second_user_row is None
        assert first_claim_row is not None
        assert first_claim_row["instagram_url"] == "https://www.instagram.com/registrationduplicateinstagram/"
    finally:
        cleanup(username, email, artist_name=first_artist_name)
        cleanup(second_username, second_email, artist_name=second_artist_name)


def test_artist_registration_requires_exactly_one_artist_target():
    response = client.post(
        "/api/register",
        json={
            "username": "claim_missing_artist",
            "email": "registration-claim-missing-artist@example.com",
            "instagram_url": "https://www.instagram.com/claim_missing_artist",
            "password": "Password123",
            "password_confirm": "Password123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "message": "Select an existing artist profile or create a new artist profile",
    }


def test_rejecting_new_artist_registration_removes_unused_artist_record():
    username = "reject-new-artist"
    email = "reject-new-artist@example.com"
    seed_admin(username, email)
    try:
        register_response = client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "instagram_url": "https://www.instagram.com/registrationrejectnewartist",
                "password": "Password123",
                "password_confirm": "Password123",
                "new_artist_name": NEW_ARTIST_NAME,
            },
        )
        assert register_response.status_code == 200
        user_id = register_response.json()["user_id"]

        reject_response = client.post(f"/api/admin/users/{user_id}/reject", headers=admin_headers())
        assert reject_response.status_code == 200
        assert reject_response.json()["success"] is True

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status FROM users WHERE id = %s", (user_id,))
                user_row = cursor.fetchone()
                cursor.execute("SELECT id FROM artists WHERE name = %s", (NEW_ARTIST_NAME,))
                artist_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT status
                    FROM artist_claims
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                claim_row = cursor.fetchone()

        assert user_row["status"] == "rejected"
        assert artist_row is None
        assert claim_row is None
    finally:
        cleanup(username, email, artist_name=NEW_ARTIST_NAME)
