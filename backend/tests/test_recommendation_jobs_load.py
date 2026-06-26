from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.db import get_connection
from app.recommendation_jobs import claim_next_recommendation_job, complete_recommendation_job, requeue_stale_running_jobs
from app.recommendation_worker import _drain_queued_jobs
from app.schemas import GraphResponse, PromoterRecommendationResponse
from app.main import app


ARTIST_ID = 2178
JOB_PARAMS = {"limit": 12, "excludeExisting": True, "debug": False}
FAKE_RESULT = PromoterRecommendationResponse(
    entityId=ARTIST_ID,
    model="test-model",
    dimensions=1536,
    recommendations=[],
    graph=GraphResponse(nodes=[], links=[], graphMode="compact"),
).model_dump(mode="json", exclude_none=True)

TEST_USERS = [
    {"id": 92_001, "username": "rec-load-user-1", "email": "rec-load-user-1@example.com"},
    {"id": 92_002, "username": "rec-load-user-2", "email": "rec-load-user-2@example.com"},
    {"id": 92_003, "username": "rec-load-user-3", "email": "rec-load-user-3@example.com"},
    {"id": 92_004, "username": "rec-load-user-4", "email": "rec-load-user-4@example.com"},
    {"id": 92_005, "username": "rec-load-user-5", "email": "rec-load-user-5@example.com"},
    {"id": 92_006, "username": "rec-load-user-6", "email": "rec-load-user-6@example.com"},
]


def _headers(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


@contextmanager
def seeded_test_users() -> Generator[None, None, None]:
    """Create approved users so parallel recommendation jobs have stable FK targets."""
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
                    INSERT INTO users (id, username, email, password_hash, role, status, must_change_password)
                    VALUES (%s, %s, %s, 'test-password-hash', 'artist', 'approved', FALSE)
                    """,
                    (user["id"], user["username"], user["email"]),
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


def _create_job(client: TestClient, user_id: int) -> dict[str, object]:
    response = client.post(
        f"/api/recommendations/artists/{ARTIST_ID}/promoters/jobs",
        headers=_headers(user_id),
        json=JOB_PARAMS,
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["jobId"]
    return {"user_id": user_id, **payload}


def _claim_and_complete_jobs() -> list[str]:
    claimed: list[str] = []
    with get_connection() as connection:
        while True:
            job = claim_next_recommendation_job(connection)
            if job is None:
                break
            claimed.append(str(job["id"]))
            complete_recommendation_job(
                connection,
                job_id=str(job["id"]),
                result=FAKE_RESULT,
            )
    return claimed


def test_parallel_recommendation_job_create_read_complete_flow():
    created_jobs: list[dict[str, object]] = []
    read_job_ids: list[str] = []
    user_ids = [user["id"] for user in TEST_USERS]
    jobs_per_user = 4

    with seeded_test_users():
        with TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=len(TEST_USERS) * jobs_per_user) as executor:
                created_jobs = list(
                    executor.map(
                        lambda user_id: _create_job(client, user_id),
                        [user_id for user_id in user_ids for _ in range(jobs_per_user)],
                    )
                )

            job_ids = [job["jobId"] for job in created_jobs]
            assert len(job_ids) == len(set(job_ids))
            assert {job["status"] for job in created_jobs} == {"queued"}

            with ThreadPoolExecutor(max_workers=len(created_jobs)) as executor:
                read_responses = list(
                    executor.map(
                        lambda job: client.get(
                            f"/api/recommendations/jobs/{job['jobId']}",
                            headers=_headers(int(job["user_id"])),
                        ),
                        created_jobs,
                    )
                )

                for response, job in zip(read_responses, created_jobs, strict=True):
                    assert response.status_code == 200
                    payload = response.json()
                    read_job_ids.append(payload["jobId"])
                    assert payload["jobId"] == job["jobId"]
                    # Initial read must reflect queued state
                    assert payload["status"] == "queued"
                    assert payload.get("result") is None

            with ThreadPoolExecutor(max_workers=4) as executor:
                claimed_job_ids = list(executor.map(lambda _: _claim_and_complete_jobs(), range(4)))

                flattened_claims = [job_id for batch in claimed_job_ids for job_id in batch]
                assert len(flattened_claims) == len(job_ids)
            assert len(flattened_claims) == len(set(flattened_claims))

            with ThreadPoolExecutor(max_workers=len(created_jobs)) as executor:
                completed_reads = list(
                    executor.map(
                        lambda job: client.get(
                            f"/api/recommendations/jobs/{job['jobId']}",
                            headers=_headers(int(job["user_id"])),
                        ),
                        created_jobs,
                    )
                )

            assert read_job_ids == job_ids
            for response in completed_reads:
                assert response.status_code == 200
                payload = response.json()
                assert payload["status"] == "completed"
                assert payload.get("result") is not None
                assert payload["result"]["entityId"] == ARTIST_ID
                assert payload["result"]["recommendations"] == []

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE id = ANY(%s::uuid[])",
                (job_ids,),
            )


def test_multiple_workers_claim_jobs_exactly_once_under_parallel_load():
    created_jobs: list[dict[str, object]] = []
    user_ids = [user["id"] for user in TEST_USERS]
    jobs_per_user = 5

    with seeded_test_users():
        with TestClient(app) as client:
            created_jobs = [
                _create_job(client, user_id)
                for user_id in [user_id for user_id in user_ids for _ in range(jobs_per_user)]
            ]

        expected_job_ids = {str(job["jobId"]) for job in created_jobs}

        with ThreadPoolExecutor(max_workers=4) as executor:
            claimed_batches = list(executor.map(lambda _: _claim_and_complete_jobs(), range(4)))

        claimed_job_ids = [job_id for batch in claimed_batches for job_id in batch]
        assert set(claimed_job_ids) == expected_job_ids
        assert len(claimed_job_ids) == len(expected_job_ids)

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, count(*) AS row_count
                    FROM recommendation_jobs
                    WHERE id = ANY(%s::uuid[])
                    GROUP BY status
                    """,
                    (list(expected_job_ids),),
                )
                rows = cursor.fetchall()

        assert rows == [{"status": "completed", "row_count": len(expected_job_ids)}]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE id = ANY(%s::uuid[])",
                ([job["jobId"] for job in created_jobs],),
            )


def test_worker_restart_requeues_stale_running_jobs_and_drains_them(monkeypatch):
    created_jobs: list[dict[str, object]] = []
    user_ids = [user["id"] for user in TEST_USERS[:2]]

    with seeded_test_users():
        with TestClient(app) as client:
            created_jobs = [
                _create_job(client, user_id)
                for user_id in user_ids
            ]

        stale_job_id = str(created_jobs[0]["jobId"])
        queued_job_id = str(created_jobs[1]["jobId"])

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE recommendation_jobs
                    SET status = 'running',
                        started_at = CURRENT_TIMESTAMP - INTERVAL '1 day',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s::uuid
                    """,
                    (stale_job_id,),
                )

        requeued_rows: list[dict[str, object]] = []
        with get_connection() as connection:
            requeued_rows = requeue_stale_running_jobs(connection)

        assert {str(row["id"]) for row in requeued_rows} == {stale_job_id}

        drained_job_ids = _claim_and_complete_jobs()

        assert set(drained_job_ids) == {stale_job_id, queued_job_id}
        assert len(drained_job_ids) == 2

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id::text AS id, status
                    FROM recommendation_jobs
                    WHERE id IN (%s::uuid, %s::uuid)
                    ORDER BY id
                    """,
                    (stale_job_id, queued_job_id),
                )
                rows = cursor.fetchall()

        assert {row["status"] for row in rows} == {"completed"}

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE id = ANY(%s::uuid[])",
                ([job["jobId"] for job in created_jobs],),
            )
