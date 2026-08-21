from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.auth import create_access_token
from app.db import get_connection
from app.main import app
from app.recommendations import jobs as recommendation_jobs
from app.schemas import GraphResponse, PromoterRecommendationItem, PromoterRecommendationResponse


TEMP_USER_ID = 99_001
TEMP_ARTIST_ID = 98_001
TEMP_JOB_PARAMS = {"limit": 17, "debug": False}

client = TestClient(app)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(TEMP_USER_ID)})}"}


@pytest.fixture(autouse=True)
def temp_recommendation_job_entities() -> Generator[None, None, None]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE user_id = %s OR artist_id = %s",
                (TEMP_USER_ID, TEMP_ARTIST_ID),
            )
            cursor.execute("DELETE FROM users WHERE id = %s", (TEMP_USER_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))
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
                "UPDATE users SET artist_id = %s WHERE id = %s",
                (TEMP_ARTIST_ID, TEMP_USER_ID),
            )

    yield

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_jobs WHERE user_id = %s OR artist_id = %s",
                (TEMP_USER_ID, TEMP_ARTIST_ID),
            )
            cursor.execute("DELETE FROM users WHERE id = %s", (TEMP_USER_ID,))
            cursor.execute("DELETE FROM artists WHERE id = %s", (TEMP_ARTIST_ID,))


def test_recommendation_job_creation_reuses_active_identical_job(monkeypatch: pytest.MonkeyPatch):
    notify_calls: list[tuple[str, str]] = []

    def fake_notify(connection, channel: str, payload: str) -> None:
        notify_calls.append((channel, payload))

    monkeypatch.setattr(recommendation_jobs, '_notify', fake_notify)

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
    assert second_payload["status"] == "queued"
    assert second_payload["jobId"]
    assert second_payload["jobId"] == first_payload["jobId"]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) AS job_count
                FROM recommendation_jobs
                WHERE user_id = %s
                  AND artist_id = %s
                  AND job_type = 'artist_promoters'
                  AND params_hash = (
                    SELECT params_hash
                    FROM recommendation_jobs
                    WHERE id = %s::uuid
                  )
                """,
                (TEMP_USER_ID, TEMP_ARTIST_ID, first_payload["jobId"]),
            )
            row = cursor.fetchone()

    assert row is not None
    assert row["job_count"] == 1
    assert notify_calls == [('scenegraph_recommendation_job_created', f'{{"jobId":"{first_payload["jobId"]}"}}')]


def test_recommendation_job_creation_reuses_active_running_job(monkeypatch: pytest.MonkeyPatch):
    notify_calls: list[tuple[str, str]] = []

    def fake_notify(connection, channel: str, payload: str) -> None:
        notify_calls.append((channel, payload))

    monkeypatch.setattr(recommendation_jobs, '_notify', fake_notify)

    first = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert first.status_code == 202
    first_payload = first.json()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'running',
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                """,
                (first_payload["jobId"],),
            )

    second = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert second.status_code == 202
    second_payload = second.json()
    assert second_payload["jobId"] == first_payload["jobId"]
    assert second_payload["status"] == "running"

    assert notify_calls == [('scenegraph_recommendation_job_created', f'{{"jobId":"{first_payload["jobId"]}"}}')]


def test_recommendation_job_creation_starts_new_job_after_completion(monkeypatch: pytest.MonkeyPatch):
    notify_calls: list[tuple[str, str]] = []

    def fake_notify(connection, channel: str, payload: str) -> None:
        notify_calls.append((channel, payload))

    monkeypatch.setattr(recommendation_jobs, '_notify', fake_notify)

    first = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert first.status_code == 202
    first_payload = first.json()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                """,
                (first_payload["jobId"],),
            )

    second = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert second.status_code == 202
    second_payload = second.json()
    assert second_payload["status"] == "queued"
    assert second_payload["jobId"] != first_payload["jobId"]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) AS job_count,
                    count(*) FILTER (WHERE status IN ('queued', 'running')) AS active_job_count
                FROM recommendation_jobs
                WHERE user_id = %s
                  AND artist_id = %s
                  AND job_type = 'artist_promoters'
                  AND params_hash = (
                    SELECT params_hash
                    FROM recommendation_jobs
                    WHERE id = %s::uuid
                  )
                """,
                (TEMP_USER_ID, TEMP_ARTIST_ID, first_payload["jobId"]),
            )
            row = cursor.fetchone()

    assert row is not None
    assert row["job_count"] == 2
    assert row["active_job_count"] == 1
    assert len(notify_calls) == 2


def test_recommendation_job_creation_starts_new_job_after_failure(monkeypatch: pytest.MonkeyPatch):
    notify_calls: list[tuple[str, str]] = []

    def fake_notify(connection, channel: str, payload: str) -> None:
        notify_calls.append((channel, payload))

    monkeypatch.setattr(recommendation_jobs, '_notify', fake_notify)

    first = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert first.status_code == 202
    first_payload = first.json()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'failed',
                    error_message = 'simulated failure',
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                """,
                (first_payload["jobId"],),
            )

    second = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert second.status_code == 202
    second_payload = second.json()
    assert second_payload["status"] == "queued"
    assert second_payload["jobId"] != first_payload["jobId"]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) AS job_count,
                    count(*) FILTER (WHERE status IN ('queued', 'running')) AS active_job_count
                FROM recommendation_jobs
                WHERE user_id = %s
                  AND artist_id = %s
                  AND job_type = 'artist_promoters'
                  AND params_hash = (
                    SELECT params_hash
                    FROM recommendation_jobs
                    WHERE id = %s::uuid
                  )
                """,
                (TEMP_USER_ID, TEMP_ARTIST_ID, first_payload["jobId"]),
            )
            row = cursor.fetchone()

    assert row is not None
    assert row["job_count"] == 2
    assert row["active_job_count"] == 1
    assert len(notify_calls) == 2


def test_recommendation_job_creation_creates_distinct_job_for_different_params(monkeypatch: pytest.MonkeyPatch):
    notify_calls: list[tuple[str, str]] = []

    def fake_notify(connection, channel: str, payload: str) -> None:
        notify_calls.append((channel, payload))

    monkeypatch.setattr(recommendation_jobs, '_notify', fake_notify)

    first = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert first.status_code == 202
    first_payload = first.json()

    second = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json={"limit": 18, "debug": False},
    )
    assert second.status_code == 202
    second_payload = second.json()
    assert second_payload["jobId"] != first_payload["jobId"]
    assert second_payload["status"] == "queued"

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) AS job_count,
                    count(*) FILTER (WHERE status IN ('queued', 'running')) AS active_job_count
                FROM recommendation_jobs
                WHERE user_id = %s
                  AND artist_id = %s
                  AND job_type = 'artist_promoters'
                """,
                (TEMP_USER_ID, TEMP_ARTIST_ID),
            )
            row = cursor.fetchone()

    assert row is not None
    assert row["job_count"] == 2
    assert row["active_job_count"] == 2
    assert len(notify_calls) == 2


def test_recommendation_job_result_can_be_paged():
    created = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=TEMP_JOB_PARAMS,
    )
    assert created.status_code == 202
    job_id = created.json()["jobId"]

    full_result = PromoterRecommendationResponse(
        entityId=TEMP_ARTIST_ID,
        model="test-model",
        dimensions=1536,
        recommendations=[
            PromoterRecommendationItem(
                id=1,
                name="Alpha Promoter",
                score=0.95,
                semanticScore=0.92,
                strengthScore=0.85,
                activityScore=0.71,
                recencyScore=0.62,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=3,
                eventCount=9,
                promoterSizeSegment="small",
            ),
            PromoterRecommendationItem(
                id=2,
                name="Beta Promoter",
                score=0.90,
                semanticScore=0.88,
                strengthScore=0.79,
                activityScore=0.68,
                recencyScore=0.58,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=4,
                eventCount=11,
                promoterSizeSegment="medium",
            ),
            PromoterRecommendationItem(
                id=3,
                name="Gamma Promoter",
                score=0.80,
                semanticScore=0.77,
                strengthScore=0.70,
                activityScore=0.66,
                recencyScore=0.52,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=5,
                eventCount=13,
                promoterSizeSegment="large",
            ),
        ],
        largeRecommendations=[
            PromoterRecommendationItem(
                id=3,
                name="Gamma Promoter",
                score=0.80,
                semanticScore=0.77,
                strengthScore=0.70,
                activityScore=0.66,
                recencyScore=0.52,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=5,
                eventCount=13,
                promoterSizeSegment="large",
            ),
        ],
        mediumRecommendations=[
            PromoterRecommendationItem(
                id=2,
                name="Beta Promoter",
                score=0.90,
                semanticScore=0.88,
                strengthScore=0.79,
                activityScore=0.68,
                recencyScore=0.58,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=4,
                eventCount=11,
                promoterSizeSegment="medium",
            ),
        ],
        smallRecommendations=[
            PromoterRecommendationItem(
                id=1,
                name="Alpha Promoter",
                score=0.95,
                semanticScore=0.92,
                strengthScore=0.85,
                activityScore=0.71,
                recencyScore=0.62,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=3,
                eventCount=9,
                promoterSizeSegment="small",
            ),
        ],
        warmRecommendations=[],
        discoveryRecommendations=[],
        graph=GraphResponse(
            nodes=[
                {"id": f"artist-{TEMP_ARTIST_ID}", "entityId": TEMP_ARTIST_ID, "type": "artist", "name": "Recommendation Job Test Artist", "genres": []},
                {"id": "promoter-1", "entityId": 1, "type": "promoter", "name": "Alpha Promoter", "genres": []},
                {"id": "promoter-2", "entityId": 2, "type": "promoter", "name": "Beta Promoter", "genres": []},
            ],
            links=[
                {"source": f"artist-{TEMP_ARTIST_ID}", "target": "promoter-1", "relationship": "recommendation", "weight": 1},
                {"source": f"artist-{TEMP_ARTIST_ID}", "target": "promoter-2", "relationship": "recommendation", "weight": 1},
            ],
            graphMode="compact",
            preferredPathNodeIds={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}", "promoter-1"],
            },
            preferredPathLinkKeys={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}|promoter-1"],
            },
            preferredPathPromoterIdsByNodeId={
                f"artist-{TEMP_ARTIST_ID}": ["promoter-1"],
                "promoter-1": ["promoter-1"],
            },
            preferredPathPromoterIdsByLinkKey={
                f"artist-{TEMP_ARTIST_ID}|promoter-1": ["promoter-1"],
            },
            fallbackPathNodeIds={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}", "promoter-1"],
            },
            fallbackPathLinkKeys={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}|promoter-1"],
            },
            fallbackPathPromoterIdsByNodeId={
                f"artist-{TEMP_ARTIST_ID}": ["promoter-1"],
                "promoter-1": ["promoter-1"],
            },
            fallbackPathPromoterIdsByLinkKey={
                f"artist-{TEMP_ARTIST_ID}|promoter-1": ["promoter-1"],
            },
        ),
        analyticsGraph=GraphResponse(
            nodes=[
                {"id": f"artist-{TEMP_ARTIST_ID}", "entityId": TEMP_ARTIST_ID, "type": "artist", "name": "Recommendation Job Test Artist", "genres": []},
                {"id": "promoter-1", "entityId": 1, "type": "promoter", "name": "Alpha Promoter", "genres": []},
                {"id": "promoter-2", "entityId": 2, "type": "promoter", "name": "Beta Promoter", "genres": []},
            ],
            links=[
                {"source": f"artist-{TEMP_ARTIST_ID}", "target": "promoter-1", "relationship": "recommendation", "weight": 1},
                {"source": f"artist-{TEMP_ARTIST_ID}", "target": "promoter-2", "relationship": "recommendation", "weight": 1},
            ],
            graphMode="full",
            preferredPathNodeIds={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}", "promoter-1"],
            },
            preferredPathLinkKeys={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}|promoter-1"],
            },
            preferredPathPromoterIdsByNodeId={
                f"artist-{TEMP_ARTIST_ID}": ["promoter-1"],
                "promoter-1": ["promoter-1"],
            },
            preferredPathPromoterIdsByLinkKey={
                f"artist-{TEMP_ARTIST_ID}|promoter-1": ["promoter-1"],
            },
            fallbackPathNodeIds={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}", "promoter-1"],
            },
            fallbackPathLinkKeys={
                "promoter-1": [f"artist-{TEMP_ARTIST_ID}|promoter-1"],
            },
            fallbackPathPromoterIdsByNodeId={
                f"artist-{TEMP_ARTIST_ID}": ["promoter-1"],
                "promoter-1": ["promoter-1"],
            },
            fallbackPathPromoterIdsByLinkKey={
                f"artist-{TEMP_ARTIST_ID}|promoter-1": ["promoter-1"],
            },
        ),
    ).model_dump(mode="json", exclude_none=True)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    result_json = %s,
                    started_at = COALESCE(started_at, created_at),
                    finished_at = COALESCE(finished_at, created_at),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (Jsonb(full_result), job_id),
            )

    paged = client.get(
        f"/api/recommendations/jobs/{job_id}?recommendations_offset=1&recommendations_limit=1",
        headers=_headers(),
    )
    assert paged.status_code == 200
    payload = paged.json()
    assert payload["status"] == "completed"
    assert payload["result"]["recommendationsTotal"] == 3
    assert payload["result"]["recommendationsOffset"] == 1
    assert payload["result"]["recommendationsLimit"] == 1
    assert payload["result"]["recommendationsHasMore"] is True
    assert [item["id"] for item in payload["result"]["recommendations"]] == [2]
    assert [item["id"] for item in payload["result"]["mediumRecommendations"]] == [2]
    assert payload["result"]["largeRecommendations"] == []
    assert {node["id"] for node in payload["result"]["graph"]["nodes"]} == {
        f"artist-{TEMP_ARTIST_ID}",
        "promoter-1",
        "promoter-2",
    }
    assert {
        (link["source"], link["target"], link["relationship"])
        for link in payload["result"]["graph"]["links"]
    } == {
        (f"artist-{TEMP_ARTIST_ID}", "promoter-1", "recommendation"),
        (f"artist-{TEMP_ARTIST_ID}", "promoter-2", "fallback_recommendation"),
    }


def test_recommendation_job_state_is_empty_before_default_job_exists():
    response = client.get(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs/state",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {}


def test_recommendation_job_state_returns_latest_completed_and_active_default_jobs(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(recommendation_jobs, "_notify", lambda *_args: None)
    params = recommendation_jobs.default_artist_promoter_recommendation_params()
    completed = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=params,
    )
    assert completed.status_code == 202
    completed_job_id = completed.json()["jobId"]
    completed_result = PromoterRecommendationResponse(
        entityId=TEMP_ARTIST_ID,
        model="state-test-model",
        dimensions=3,
        recommendations=[],
        graph=GraphResponse(nodes=[], links=[]),
    ).model_dump(mode="json", exclude_none=True)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    result_json = %s,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                """,
                (Jsonb(completed_result), completed_job_id),
            )

    active = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=params,
    )
    assert active.status_code == 202

    response = client.get(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs/state",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["latestCompletedJob"]["jobId"] == completed_job_id
    assert payload["latestCompletedJob"]["result"]["model"] == "state-test-model"
    assert payload["activeJob"]["jobId"] == active.json()["jobId"]
    assert payload["activeJob"]["status"] == "queued"


def test_recommendation_job_state_pages_latest_completed_result():
    params = recommendation_jobs.default_artist_promoter_recommendation_params()
    created = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=params,
    )
    assert created.status_code == 202
    job_id = created.json()["jobId"]

    full_result = PromoterRecommendationResponse(
        entityId=TEMP_ARTIST_ID,
        model="state-page-test-model",
        dimensions=3,
        recommendations=[
            PromoterRecommendationItem(
                id=1,
                name="Alpha Promoter",
                score=0.95,
                semanticScore=0.92,
                strengthScore=0.85,
                activityScore=0.71,
                recencyScore=0.62,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=3,
                eventCount=9,
                promoterSizeSegment="small",
            ),
            PromoterRecommendationItem(
                id=2,
                name="Beta Promoter",
                score=0.90,
                semanticScore=0.88,
                strengthScore=0.79,
                activityScore=0.68,
                recencyScore=0.58,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=4,
                eventCount=11,
                promoterSizeSegment="medium",
            ),
            PromoterRecommendationItem(
                id=3,
                name="Gamma Promoter",
                score=0.80,
                semanticScore=0.77,
                strengthScore=0.70,
                activityScore=0.66,
                recencyScore=0.52,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=5,
                eventCount=13,
                promoterSizeSegment="large",
            ),
        ],
        largeRecommendations=[
            PromoterRecommendationItem(
                id=3,
                name="Gamma Promoter",
                score=0.80,
                semanticScore=0.77,
                strengthScore=0.70,
                activityScore=0.66,
                recencyScore=0.52,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=5,
                eventCount=13,
                promoterSizeSegment="large",
            ),
        ],
        mediumRecommendations=[
            PromoterRecommendationItem(
                id=2,
                name="Beta Promoter",
                score=0.90,
                semanticScore=0.88,
                strengthScore=0.79,
                activityScore=0.68,
                recencyScore=0.58,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=4,
                eventCount=11,
                promoterSizeSegment="medium",
            ),
        ],
        smallRecommendations=[
            PromoterRecommendationItem(
                id=1,
                name="Alpha Promoter",
                score=0.95,
                semanticScore=0.92,
                strengthScore=0.85,
                activityScore=0.71,
                recencyScore=0.62,
                reasons=["shared extracted genres: dark disco"],
                matchedArtistCount=3,
                eventCount=9,
                promoterSizeSegment="small",
            ),
        ],
        warmRecommendations=[],
        discoveryRecommendations=[],
        graph=GraphResponse(nodes=[], links=[]),
    ).model_dump(mode="json", exclude_none=True)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    result_json = %s,
                    started_at = COALESCE(started_at, created_at),
                    finished_at = COALESCE(finished_at, created_at),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (Jsonb(full_result), job_id),
            )

    response = client.get(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs/state?recommendations_offset=1&recommendations_limit=1",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["latestCompletedJob"]["jobId"] == job_id
    assert payload["latestCompletedJob"]["result"]["recommendationsTotal"] == 3
    assert payload["latestCompletedJob"]["result"]["recommendationsOffset"] == 1
    assert payload["latestCompletedJob"]["result"]["recommendationsLimit"] == 1
    assert [item["id"] for item in payload["latestCompletedJob"]["result"]["recommendations"]] == [2]
    assert [item["id"] for item in payload["latestCompletedJob"]["result"]["mediumRecommendations"]] == [2]


def test_recommendation_job_state_isolated_by_owning_user(monkeypatch: pytest.MonkeyPatch):
    other_user_id = 99_002
    monkeypatch.setattr(recommendation_jobs, "_notify", lambda *_args: None)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (other_user_id,))
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    other_user_id,
                    f"recommendation-job-test-{other_user_id}",
                    f"recommendation-job-test-{other_user_id}@example.com",
                    "hash",
                    "admin",
                    "approved",
                ),
            )

    created = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=recommendation_jobs.default_artist_promoter_recommendation_params(),
    )
    assert created.status_code == 202

    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(other_user_id)})}"}
    response = client.get(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs/state",
        headers=other_headers,
    )

    assert response.status_code == 200
    assert response.json() == {}


def test_newest_completed_generation_wins_by_creation_order(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(recommendation_jobs, "_notify", lambda *_args: None)
    params = recommendation_jobs.default_artist_promoter_recommendation_params()

    first = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=params,
    )
    assert first.status_code == 202
    first_job_id = first.json()["jobId"]

    completed_result = PromoterRecommendationResponse(
        entityId=TEMP_ARTIST_ID,
        model="state-order-test-model",
        dimensions=3,
        recommendations=[],
        graph=GraphResponse(nodes=[], links=[]),
    ).model_dump(mode="json", exclude_none=True)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    result_json = %s,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                """,
                (Jsonb(completed_result), first_job_id),
            )

    second = client.post(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs",
        headers=_headers(),
        json=params,
    )
    assert second.status_code == 202
    second_job_id = second.json()["jobId"]
    assert first_job_id != second_job_id

    earlier_finished_at = datetime(2026, 8, 21, 10, 0, 1, tzinfo=timezone.utc)
    later_finished_at = datetime(2026, 8, 21, 10, 0, 2, tzinfo=timezone.utc)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    result_json = %s,
                    finished_at = %s,
                    updated_at = %s
                WHERE id = %s::uuid
                """,
                (Jsonb(completed_result), earlier_finished_at, earlier_finished_at, second_job_id),
            )
            cursor.execute(
                """
                UPDATE recommendation_jobs
                SET status = 'completed',
                    result_json = %s,
                    finished_at = %s,
                    updated_at = %s
                WHERE id = %s::uuid
                """,
                (Jsonb(completed_result), later_finished_at, later_finished_at, first_job_id),
            )

    response = client.get(
        f"/api/recommendations/artists/{TEMP_ARTIST_ID}/promoters/jobs/state",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["latestCompletedJob"]["jobId"] == second_job_id


def test_default_job_enqueue_reuses_active_job(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(recommendation_jobs, "_notify", lambda *_args: None)
    with get_connection() as connection:
        first = recommendation_jobs.enqueue_default_artist_promoter_recommendation_job(
            connection,
            user_id=TEMP_USER_ID,
            artist_id=TEMP_ARTIST_ID,
        )
        second = recommendation_jobs.enqueue_default_artist_promoter_recommendation_job(
            connection,
            user_id=TEMP_USER_ID,
            artist_id=TEMP_ARTIST_ID,
        )

    assert first["id"] == second["id"]
    assert first["status"] == "queued"


def test_user_local_enqueue_skips_an_artist_not_owned_by_the_user(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(recommendation_jobs, "_notify", lambda *_args: None)
    with get_connection() as connection:
        own_job = recommendation_jobs.enqueue_user_artist_promoter_recommendation_job(
            connection,
            user_id=TEMP_USER_ID,
            artist_id=TEMP_ARTIST_ID,
        )
        unrelated_job = recommendation_jobs.enqueue_user_artist_promoter_recommendation_job(
            connection,
            user_id=TEMP_USER_ID,
            artist_id=TEMP_ARTIST_ID + 1,
        )

    assert own_job is not None
    assert unrelated_job is None
