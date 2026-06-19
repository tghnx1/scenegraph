from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app


USERS = [
    {"username": "maksim", "password": "12345", "user_id": 1},
    {"username": "howard", "password": "12345", "user_id": 2},
    {"username": "tarcisio", "password": "12345", "user_id": 3},
    {"username": "herold", "password": "12345", "user_id": 4},
    {"username": "aaron", "password": "12345", "user_id": 5},
]


def login(payload: dict) -> dict:
    with TestClient(app) as client:
        response = client.post(
            "/api/login",
            json={"username": payload["username"], "password": payload["password"]},
        )
    assert response.status_code == 200
    return response.json()


def test_multiple_users_can_log_in_concurrently_with_isolated_sessions():
    with ThreadPoolExecutor(max_workers=len(USERS)) as executor:
        responses = list(executor.map(login, USERS))

    assert all(response["success"] for response in responses)
    assert {response["username"] for response in responses} == {
        user["username"] for user in USERS
    }
    assert {response["user_id"] for response in responses} == {
        user["user_id"] for user in USERS
    }

    tokens = [response["access_token"] for response in responses]
    assert all(tokens)
    assert len(set(tokens)) == len(tokens)
