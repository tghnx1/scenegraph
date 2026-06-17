from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app


client = TestClient(app)


def delete_connection(source_artist_id: int, connected_artist_id: int) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM artist_manual_connections
                WHERE source_artist_id = %s
                  AND connected_artist_id = %s
                """,
                (source_artist_id, connected_artist_id),
            )


@pytest.fixture
def artist_pair() -> Generator[tuple[dict, dict], None, None]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    source_artist.id AS source_id,
                    source_artist.name AS source_name,
                    connected_artist.id AS connected_id,
                    connected_artist.name AS connected_name
                FROM artists source_artist
                CROSS JOIN artists connected_artist
                WHERE source_artist.id <> connected_artist.id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM artist_manual_connections amc
                      WHERE amc.source_artist_id = source_artist.id
                        AND amc.connected_artist_id = connected_artist.id
                  )
                ORDER BY source_artist.id ASC, connected_artist.id ASC
                LIMIT 1
                """
            )
            rows = cursor.fetchall()

    assert rows
    row = rows[0]
    source_artist = {"id": row["source_id"], "name": row["source_name"]}
    connected_artist = {"id": row["connected_id"], "name": row["connected_name"]}
    delete_connection(source_artist["id"], connected_artist["id"])

    yield source_artist, connected_artist

    delete_connection(source_artist["id"], connected_artist["id"])


def test_manual_artist_connection_can_be_added_listed_and_upserted(artist_pair):
    source_artist, connected_artist = artist_pair
    path = f"/api/artists/{source_artist['id']}/known-artists"
    payload = {"connectedArtistId": connected_artist["id"]}

    initial_list_response = client.get(path)
    assert initial_list_response.status_code == 200
    assert all(
        item["connectedArtistId"] != connected_artist["id"]
        for item in initial_list_response.json()["items"]
    )

    create_response = client.post(path, json=payload)
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["sourceArtistId"] == source_artist["id"]
    assert created["connectedArtistId"] == connected_artist["id"]
    assert created["connectedArtistName"] == connected_artist["name"]
    assert created["createdAt"]
    assert created["updatedAt"]

    upsert_response = client.post(path, json=payload)
    assert upsert_response.status_code == 200
    upserted = upsert_response.json()
    assert upserted["sourceArtistId"] == source_artist["id"]
    assert upserted["connectedArtistId"] == connected_artist["id"]
    assert upserted["createdAt"] == created["createdAt"]

    list_response = client.get(path)
    assert list_response.status_code == 200
    matching_items = [
        item
        for item in list_response.json()["items"]
        if item["connectedArtistId"] == connected_artist["id"]
    ]
    assert len(matching_items) == 1


def test_manual_artist_connection_can_be_deleted(artist_pair):
    source_artist, connected_artist = artist_pair
    collection_path = f"/api/artists/{source_artist['id']}/known-artists"
    item_path = f"{collection_path}/{connected_artist['id']}"

    create_response = client.post(
        collection_path,
        json={"connectedArtistId": connected_artist["id"]},
    )
    assert create_response.status_code == 200

    delete_response = client.delete(item_path)
    assert delete_response.status_code == 200
    assert delete_response.json()["connectedArtistId"] == connected_artist["id"]

    second_delete_response = client.delete(item_path)
    assert second_delete_response.status_code == 404
    assert second_delete_response.json()["detail"] == "manual artist connection not found"


def test_manual_artist_connection_rejects_self_link(artist_pair):
    source_artist, _ = artist_pair

    response = client.post(
        f"/api/artists/{source_artist['id']}/known-artists",
        json={"connectedArtistId": source_artist["id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source artist and connected artist must be different"


def test_manual_artist_connection_rejects_missing_source_artist(artist_pair):
    _, connected_artist = artist_pair
    missing_artist_id = 9_999_999_999

    response = client.post(
        f"/api/artists/{missing_artist_id}/known-artists",
        json={"connectedArtistId": connected_artist["id"]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == f"artist {missing_artist_id} not found"


def test_manual_artist_connection_rejects_missing_connected_artist(artist_pair):
    source_artist, _ = artist_pair
    missing_artist_id = 9_999_999_999

    response = client.post(
        f"/api/artists/{source_artist['id']}/known-artists",
        json={"connectedArtistId": missing_artist_id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == f"artist {missing_artist_id} not found"


def test_manual_artist_connection_rejects_invalid_request_body(artist_pair):
    source_artist, _ = artist_pair

    response = client.post(
        f"/api/artists/{source_artist['id']}/known-artists",
        json={},
    )

    assert response.status_code == 422
