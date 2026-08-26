from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.auth import pwd_context
from app.db import get_connection
from app.main import app


BASE_USER_ID = 96_001
USERS = [
    {"email": "maksim-multiuser@example.com", "password": "12345", "user_id": BASE_USER_ID + 0},
    {"email": "howard-multiuser@example.com", "password": "12345", "user_id": BASE_USER_ID + 1},
    {"email": "tarcisio-multiuser@example.com", "password": "12345", "user_id": BASE_USER_ID + 2},
    {"email": "herold-multiuser@example.com", "password": "12345", "user_id": BASE_USER_ID + 3},
    {"email": "aaron-multiuser@example.com", "password": "12345", "user_id": BASE_USER_ID + 4},
]


def seed_users() -> None:
    password_hash = pwd_context.hash("12345")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for user in USERS:
                cursor.execute("DELETE FROM users WHERE id = %s OR email = %s", (user["user_id"], user["email"]))
                cursor.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, role, status)
                    VALUES (%s, %s, %s, %s, 'artist', 'approved')
                    """,
                    (user["user_id"], user["email"], user["email"], password_hash),
                )
            connection.commit()


def cleanup_users() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for user in USERS:
                cursor.execute("DELETE FROM users WHERE id = %s OR email = %s", (user["user_id"], user["email"]))
            connection.commit()


def login(payload: dict) -> dict:
    with TestClient(app) as client:
        response = client.post(
            "/api/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
    assert response.status_code == 200
    return response.json()


@pytest.fixture(autouse=True)
def _multiuser_fixture():
    seed_users()
    try:
        yield
    finally:
        cleanup_users()


def test_multiple_users_can_log_in_concurrently_with_isolated_sessions():
    with ThreadPoolExecutor(max_workers=len(USERS)) as executor:
        responses = list(executor.map(login, USERS))

    assert all(response["success"] for response in responses)
    assert {response["username"] for response in responses} == {
        user["email"] for user in USERS
    }
    assert {response["user_id"] for response in responses} == {
        user["user_id"] for user in USERS
    }

    tokens = [response["access_token"] for response in responses]
    assert all(tokens)
    assert len(set(tokens)) == len(tokens)
