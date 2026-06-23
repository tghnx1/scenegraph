from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.db import get_connection
from app.main import app


TEMP_USER_ID = 99_001
TEMP_ARTIST_ID = 98_001
TEMP_JOB_PARAMS = {"limit": 17, "excludeExisting": True, "debug": False}

client = TestClient(app)


def _headers() -> dict[str, str]:
    return {"X-User-Id": str(TEMP_USER_ID)}


@pytest.fixture(autouse=True)
def temp_recommendation_job_entities() -> Generator[None, None, None]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE user_id = %s OR artist_id = %s",
                (TEMP_USER_ID, TEMP_ARTIST_ID),
            )
            cursor.execute("DELETE FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))
            cursor.execute("DELETE FROM users WHERE id = %s", (TEMP_USER_ID,))
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    TEMP_USER_ID,
                    f"recommendation-job-test-{TEMP_USER_ID}",
                    f"recommendation-job-test-{TEMP_USER_ID}@example.com",
                    "hash",
                    "artist",
                    "approved",
                ),
            )
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name)
                VALUES (%s, %s, %s)
                """,
                (
                    TEMP_ARTIST_ID,
                    f"recommendation-job-test-{TEMP_ARTIST_ID}",
                    "Recommendation Job Test Artist",
                ),
            )

    yield

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE user_id = %s OR artist_id = %s",
                (TEMP_USER_ID, TEMP_ARTIST_ID),
            )
            cursor.execute("DELETE FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))
            cursor.execute("DELETE FROM users WHERE id = %s", (TEMP_USER_ID,))


def test_recommendation_job_creation_reuses_identical_jobs():
    first = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert first.status_code == 202
    first_payload = first.json()
    assert first_payload["status"] == "queued"
    assert first_payload["jobId"]

    second = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert second.status_code == 202
    second_payload = second.json()
    assert second_payload["jobId"] == first_payload["jobId"]
    assert second_payload["status"] in {"queued", "running", "completed"}

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) AS job_count
                FROM recommendation_jobs
                WHERE user_id = %s
                  AND artist_id = %s
                  AND job_type = 'artist_promoters'
                  AND params_json = %s::jsonb
                """,
                (TEMP_USER_ID, TEMP_ARTIST_ID, Jsonb(TEMP_JOB_PARAMS)),
            )
            row = cursor.fetchone()

    assert row is not None
    assert row["job_count"] == 1
