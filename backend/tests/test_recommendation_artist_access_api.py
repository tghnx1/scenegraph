from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


OWNED_ARTIST_ID = 2178
FORBIDDEN_ARTIST_ID = 93_201
OWNER_USER_ID = 93_211
AGENT_USER_ID = 93_212
ADMIN_USER_ID = 93_213

client = TestClient(app)


def headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user_id)})}"}


@pytest.fixture(autouse=True)
def temp_access_users() -> Generator[None, None, None]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE user_id = ANY(%s)",
                ([OWNER_USER_ID, AGENT_USER_ID, ADMIN_USER_ID],),
            )
            cursor.execute("DELETE FROM users WHERE id = ANY(%s)", ([OWNER_USER_ID, AGENT_USER_ID, ADMIN_USER_ID],))
            cursor.execute("DELETE FROM artists WHERE id = %s", (FORBIDDEN_ARTIST_ID,))
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name)
                VALUES (%s, %s, %s)
                """,
                (
                    FORBIDDEN_ARTIST_ID,
                    f"recommendation-access-test-artist-{FORBIDDEN_ARTIST_ID}",
                    "Recommendation Access Test Artist",
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
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s),
                    (%s, %s, %s, %s, %s, %s, %s),
                    (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    OWNER_USER_ID,
                    f"recommendation-access-owner-{OWNER_USER_ID}",
                    f"recommendation-access-owner-{OWNER_USER_ID}@example.com",
                    "hash",
                    "artist",
                    "approved",
                    OWNED_ARTIST_ID,
                    AGENT_USER_ID,
                    f"recommendation-access-agent-{AGENT_USER_ID}",
                    f"recommendation-access-agent-{AGENT_USER_ID}@example.com",
                    "hash",
                    "agent",
                    "approved",
                    None,
                    ADMIN_USER_ID,
                    f"recommendation-access-admin-{ADMIN_USER_ID}",
                    f"recommendation-access-admin-{ADMIN_USER_ID}@example.com",
                    "hash",
                    "admin",
                    "approved",
                    None,
                ),
            )

    try:
        yield
    finally:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM recommendation_jobs WHERE user_id = ANY(%s)",
                    ([OWNER_USER_ID, AGENT_USER_ID, ADMIN_USER_ID],),
                )
                cursor.execute("DELETE FROM users WHERE id = ANY(%s)", ([OWNER_USER_ID, AGENT_USER_ID, ADMIN_USER_ID],))
                cursor.execute("DELETE FROM artists WHERE id = %s", (FORBIDDEN_ARTIST_ID,))


def test_artist_promoter_recommendations_follow_owner_agent_and_admin_access():
    owner_response = client.get(
        f"/api/recommendations/artists/{OWNED_ARTIST_ID}/promoters",
        headers=headers(OWNER_USER_ID),
    )
    agent_response = client.get(
        f"/api/recommendations/artists/{OWNED_ARTIST_ID}/promoters",
        headers=headers(AGENT_USER_ID),
    )
    admin_response = client.get(
        f"/api/recommendations/artists/{OWNED_ARTIST_ID}/promoters",
        headers=headers(ADMIN_USER_ID),
    )

    assert owner_response.status_code == 200
    assert agent_response.status_code == 200
    assert admin_response.status_code == 200


def test_artist_promoter_recommendations_reject_other_artist_and_missing_auth():
    forbidden_response = client.get(
        f"/api/recommendations/artists/{FORBIDDEN_ARTIST_ID}/promoters",
        headers=headers(OWNER_USER_ID),
    )
    unauthenticated_response = client.get(f"/api/recommendations/artists/{OWNED_ARTIST_ID}/promoters")

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "You are not allowed to access this artist"
    assert unauthenticated_response.status_code == 401


def test_artist_promoter_jobs_follow_owner_agent_and_admin_access():
    payload = {"limit": 3, "debug": False}

    owner_response = client.post(
        f"/api/recommendations/artists/{OWNED_ARTIST_ID}/promoters/jobs",
        headers=headers(OWNER_USER_ID),
        json=payload,
    )
    agent_response = client.post(
        f"/api/recommendations/artists/{FORBIDDEN_ARTIST_ID}/promoters/jobs",
        headers=headers(AGENT_USER_ID),
        json=payload,
    )
    admin_response = client.post(
        f"/api/recommendations/artists/{FORBIDDEN_ARTIST_ID}/promoters/jobs",
        headers=headers(ADMIN_USER_ID),
        json=payload,
    )

    assert owner_response.status_code == 202
    assert agent_response.status_code == 202
    assert admin_response.status_code == 202


def test_artist_promoter_jobs_reject_other_artist_and_missing_auth():
    payload = {"limit": 3, "debug": False}

    forbidden_response = client.post(
        f"/api/recommendations/artists/{FORBIDDEN_ARTIST_ID}/promoters/jobs",
        headers=headers(OWNER_USER_ID),
        json=payload,
    )
    unauthenticated_response = client.post(
        f"/api/recommendations/artists/{OWNED_ARTIST_ID}/promoters/jobs",
        json=payload,
    )

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "You are not allowed to access this artist"
    assert unauthenticated_response.status_code == 401
