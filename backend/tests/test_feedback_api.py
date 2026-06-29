from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.auth import create_access_token
from app.db import get_connection
from app.main import app


SOURCE_ARTIST_ID = 9_100_001
CANDIDATE_PROMOTER_ID = 9_200_001
OTHER_PROMOTER_ID = 9_200_002
USER_ONE = 91_001
USER_TWO = 91_002

client = TestClient(app)


def headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user_id)})}"}


def payload(**updates) -> dict:
    return {
        "sourceEntityType": "artist",
        "sourceEntityId": SOURCE_ARTIST_ID,
        "candidateEntityType": "promoter",
        "candidateEntityId": CANDIDATE_PROMOTER_ID,
        "feedback": "positive",
        **updates,
    }


@pytest.fixture(autouse=True)
def feedback_entities() -> Generator[None, None, None]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO artists (id, ra_artist_id, name)
                VALUES (%s, %s, 'Feedback Test Artist')
                ON CONFLICT (id) DO NOTHING
                """,
                (SOURCE_ARTIST_ID, f"feedback-test-artist-{SOURCE_ARTIST_ID}"),
            )
            cursor.execute(
                """
                INSERT INTO promoters (id, ra_promoter_id, name)
                VALUES
                    (%s, %s, 'Feedback Test Promoter'),
                    (%s, %s, 'Other Feedback Test Promoter')
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    CANDIDATE_PROMOTER_ID,
                    f"feedback-test-promoter-{CANDIDATE_PROMOTER_ID}",
                    OTHER_PROMOTER_ID,
                    f"feedback-test-promoter-{OTHER_PROMOTER_ID}",
                ),
            )
            cursor.execute("DELETE FROM users WHERE id = ANY(%s)", ([USER_ONE, USER_TWO],))
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
                    (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    USER_ONE,
                    f"feedback-test-user-{USER_ONE}",
                    f"feedback-test-user-{USER_ONE}@example.com",
                    "hash",
                    "artist",
                    "approved",
                    None,
                    USER_TWO,
                    f"feedback-test-user-{USER_TWO}",
                    f"feedback-test-user-{USER_TWO}@example.com",
                    "hash",
                    "artist",
                    "approved",
                    None,
                ),
            )
            cursor.execute(
                "DELETE FROM recommendation_feedback WHERE user_id = ANY(%s)",
                ([USER_ONE, USER_TWO],),
            )

    yield

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM recommendation_feedback WHERE user_id = ANY(%s)",
                ([USER_ONE, USER_TWO],),
            )
            cursor.execute("DELETE FROM users WHERE id = ANY(%s)", ([USER_ONE, USER_TWO],))
            cursor.execute(
                "DELETE FROM promoters WHERE id = ANY(%s)",
                ([CANDIDATE_PROMOTER_ID, OTHER_PROMOTER_ID],),
            )
            cursor.execute("DELETE FROM artists WHERE id = %s", (SOURCE_ARTIST_ID,))


def test_create_and_update_feedback_for_current_user():
    created = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        json=payload(reason="Good style fit"),
    )
    assert created.status_code == 200
    created_item = created.json()
    assert created_item["userId"] == USER_ONE
    assert created_item["feedback"] == "positive"
    assert created_item["reason"] == "Good style fit"

    updated = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        json=payload(feedback="negative", reason="  "),
    )
    assert updated.status_code == 200
    updated_item = updated.json()
    assert updated_item["id"] == created_item["id"]
    assert updated_item["feedback"] == "negative"
    assert "reason" not in updated_item


def test_feedback_is_isolated_between_users():
    first = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        json=payload(feedback="positive"),
    ).json()
    second = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_TWO),
        json=payload(feedback="negative"),
    ).json()

    assert first["id"] != second["id"]
    assert client.get(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
    ).json()["feedback"] == [first]
    assert client.get(
        "/api/recommendation-feedback",
        headers=headers(USER_TWO),
    ).json()["feedback"] == [second]
    filtered = client.get(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        params={
            "sourceEntityType": "artist",
            "sourceEntityId": SOURCE_ARTIST_ID,
            "candidateEntityType": "promoter",
            "candidateEntityId": CANDIDATE_PROMOTER_ID,
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()["feedback"] == [first]


def test_delete_only_removes_current_users_feedback():
    item = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        json=payload(),
    ).json()

    denied = client.delete(
        f"/api/recommendation-feedback/{item['id']}",
        headers=headers(USER_TWO),
    )
    assert denied.status_code == 404
    deleted = client.delete(
        f"/api/recommendation-feedback/{item['id']}",
        headers=headers(USER_ONE),
    )
    assert deleted.status_code == 200


@pytest.mark.parametrize(
    "updates",
    [
        {"sourceEntityType": "event"},
        {"candidateEntityType": "artist"},
        {"feedback": "hidden"},
    ],
)
def test_feedback_rejects_invalid_contract_values(updates):
    response = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        json=payload(**updates),
    )
    assert response.status_code == 422


def test_feedback_rejects_missing_artist_and_promoter():
    missing_artist = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        json=payload(sourceEntityId=999_999_999),
    )
    missing_promoter = client.post(
        "/api/recommendation-feedback",
        headers=headers(USER_ONE),
        json=payload(candidateEntityId=999_999_999),
    )

    assert missing_artist.status_code == 404
    assert missing_promoter.status_code == 404


def test_feedback_requires_current_user():
    response = client.post("/api/recommendation-feedback", json=payload())
    assert response.status_code == 401
