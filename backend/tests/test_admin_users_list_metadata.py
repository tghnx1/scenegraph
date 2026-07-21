from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app

ADMIN_USER_ID = 97_001
APPROVED_USER_ID = 97_002
APPROVED_ARTIST_ID = 97_003
APPROVED_CLAIM_ID = 97_004
SECOND_APPROVED_ARTIST_ID = 97_005
SECOND_APPROVED_CLAIM_ID = 97_006

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(ADMIN_USER_ID)})}"}


def cleanup() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM artist_claims WHERE id = %s", (APPROVED_CLAIM_ID,))
            cursor.execute("DELETE FROM artist_claims WHERE id = %s", (SECOND_APPROVED_CLAIM_ID,))
            cursor.execute("DELETE FROM users WHERE id IN (%s, %s)", (ADMIN_USER_ID, APPROVED_USER_ID))
            cursor.execute("DELETE FROM artists WHERE id = %s", (APPROVED_ARTIST_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (SECOND_APPROVED_ARTIST_ID,))
            connection.commit()


def test_admin_users_list_returns_null_source_for_admin_without_artist_and_instagram_for_approved_claim():
    cleanup()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status)
                    VALUES (%s, %s, %s, 'hash', 'admin', 'approved')
                    """,
                    (ADMIN_USER_ID, 'admin-list-test', 'admin-list-test@example.com'),
                )
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name)
                    VALUES (%s, %s, %s)
                    """,
                    (APPROVED_ARTIST_ID, 'admin-users-list-test-ra', 'Admin Users List Test Artist'),
                )
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status, artist_id)
                    VALUES (%s, %s, %s, 'hash', 'artist', 'approved', %s)
                    """,
                    (
                        APPROVED_USER_ID,
                        'approved-list-test',
                        'approved-list-test@example.com',
                        APPROVED_ARTIST_ID,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO artist_claims (id, user_id, artist_id, instagram_url, status, reason)
                    VALUES (%s, %s, %s, %s, 'approved', %s)
                    """,
                    (
                        APPROVED_CLAIM_ID,
                        APPROVED_USER_ID,
                        APPROVED_ARTIST_ID,
                        'https://www.instagram.com/approvedlisttest/',
                        'Approved in test',
                    ),
                )
                connection.commit()

        response = client.get('/api/admin/users', headers=admin_headers())
        assert response.status_code == 200
        users = response.json()['users']

        admin_row = next(user for user in users if user['id'] == ADMIN_USER_ID)
        approved_row = next(user for user in users if user['id'] == APPROVED_USER_ID)

        assert admin_row['artist_source'] is None
        assert admin_row['artist_name'] is None
        assert admin_row['artist_instagram_url'] is None
        assert approved_row['artist_source'] == 'resident_advisor'
        assert approved_row['artist_instagram_url'] == 'https://www.instagram.com/approvedlisttest/'
    finally:
        cleanup()


def test_admin_users_list_joins_approved_claim_by_current_artist_only():
    cleanup()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status)
                    VALUES (%s, %s, %s, 'hash', 'admin', 'approved')
                    """,
                    (ADMIN_USER_ID, 'admin-list-test', 'admin-list-test@example.com'),
                )
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name)
                    VALUES (%s, %s, %s)
                    """,
                    (APPROVED_ARTIST_ID, 'admin-users-list-test-ra', 'Admin Users List Test Artist'),
                )
                cursor.execute(
                    """
                    INSERT INTO artists (id, ra_artist_id, name)
                    VALUES (%s, %s, %s)
                    """,
                    (SECOND_APPROVED_ARTIST_ID, 'admin-users-list-test-ra-2', 'Admin Users List Test Artist 2'),
                )
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status, artist_id)
                    VALUES (%s, %s, %s, 'hash', 'artist', 'approved', %s)
                    """,
                    (
                        APPROVED_USER_ID,
                        'approved-list-test',
                        'approved-list-test@example.com',
                        APPROVED_ARTIST_ID,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO artist_claims (id, user_id, artist_id, instagram_url, status, reason)
                    VALUES (%s, %s, %s, %s, 'approved', %s)
                    """,
                    (
                        APPROVED_CLAIM_ID,
                        APPROVED_USER_ID,
                        APPROVED_ARTIST_ID,
                        'https://www.instagram.com/approvedlisttest/',
                        'Approved in test',
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO artist_claims (id, user_id, artist_id, instagram_url, status, reason)
                    VALUES (%s, %s, %s, %s, 'approved', %s)
                    """,
                    (
                        SECOND_APPROVED_CLAIM_ID,
                        APPROVED_USER_ID,
                        SECOND_APPROVED_ARTIST_ID,
                        'https://www.instagram.com/approvedlisttest2/',
                        'Approved in test',
                    ),
                )
                connection.commit()

        response = client.get('/api/admin/users', headers=admin_headers())
        assert response.status_code == 200
        users = response.json()['users']

        approved_rows = [user for user in users if user['id'] == APPROVED_USER_ID]
        assert len(approved_rows) == 1
        approved_row = approved_rows[0]
        assert approved_row['artist_instagram_url'] == 'https://www.instagram.com/approvedlisttest/'
        assert approved_row['artist_name'] == 'Admin Users List Test Artist'
        assert approved_row['artist_source'] == 'resident_advisor'
    finally:
        cleanup()
