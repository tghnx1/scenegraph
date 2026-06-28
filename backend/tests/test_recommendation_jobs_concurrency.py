from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


ARTIST_ID = 2178
TEST_USERS = [
    {"id": 91_101, "username": "rec-job-user-1", "email": "rec-job-user-1@example.com"},
    {"id": 91_102, "username": "rec-job-user-2", "email": "rec-job-user-2@example.com"},
    {"id": 91_103, "username": "rec-job-user-3", "email": "rec-job-user-3@example.com"},
    {"id": 91_104, "username": "rec-job-user-4", "email": "rec-job-user-4@example.com"},
    {"id": 91_105, "username": "rec-job-user-5", "email": "rec-job-user-5@example.com"},
]


def _create_job(client: TestClient, user_id: int) -> dict[str, object]:
    """Create one recommendation job using a shared app client."""
    response = client.post(
        f"/api/recommendations/artists/{ARTIST_ID}/promoters/jobs",
        headers={"Authorization": f"Bearer {create_access_token({'sub': str(user_id)})}"},
        json={"limit": 10, "debug": False},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["jobId"]
    return {"user_id": user_id, **payload}


@contextmanager
def seeded_test_users():
    """Create temporary approved users so parallel job requests have real FK targets."""
    user_ids = [user["id"] for user in TEST_USERS]
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE user_id = ANY(%s)",
                (user_ids,),
            )
            cursor.execute("DELETE FROM users WHERE id = ANY(%s)", (user_ids,))
            for user in TEST_USERS:
                cursor.execute(
                    """
                    INSERT INTO users (
                        id,
                        username,
                        email,
                        password_hash,
                        role,
                        status,
                        must_change_password,
                        artist_id
                    )
                    VALUES (%s, %s, %s, 'test-password-hash', 'artist', 'approved', FALSE, %s)
                    """,
                    (user["id"], user["username"], user["email"], ARTIST_ID),
                )
    try:
        yield
    finally:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM recommendation_jobs WHERE user_id = ANY(%s)",
                    (user_ids,),
                )
                cursor.execute("DELETE FROM users WHERE id = ANY(%s)", (user_ids,))


def test_concurrent_recommendation_job_creates_are_isolated():
    created_jobs: list[dict[str, object]] = []
    user_ids = [user["id"] for user in TEST_USERS]

    with seeded_test_users():
        with TestClient(app) as client:
            try:
                with ThreadPoolExecutor(max_workers=len(TEST_USERS)) as executor:
                    created_jobs = list(
                        executor.map(
                            lambda user_id: _create_job(client, user_id),
                            user_ids,
                        )
                    )

                job_ids = [job["jobId"] for job in created_jobs]
                assert len(job_ids) == len(set(job_ids))
                assert {job["status"] for job in created_jobs} == {"queued"}
                assert {job["user_id"] for job in created_jobs} == set(user_ids)

                with get_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT id::text AS id, user_id, artist_id, status, job_type
                            FROM recommendation_jobs
                            WHERE id = ANY(%s::uuid[])
                            ORDER BY created_at ASC, id ASC
                            """,
                            (job_ids,),
                        )
                        rows = cursor.fetchall()

                assert len(rows) == len(created_jobs)
                assert {row["artist_id"] for row in rows} == {ARTIST_ID}
                assert {row["user_id"] for row in rows} == set(user_ids)
                assert {row["job_type"] for row in rows} == {"artist_promoters"}
                assert {row["id"] for row in rows} == set(job_ids)
            finally:
                if created_jobs:
                    with get_connection() as connection:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "DELETE FROM recommendation_jobs WHERE id = ANY(%s::uuid[])",
                                ([job["jobId"] for job in created_jobs],),
                            )
