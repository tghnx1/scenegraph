from fastapi.testclient import TestClient
from app.db import get_connection
from app.main import app, extracted_tag_score
from app.recommendation_scoring import DEFAULT_SEMANTIC_ARTIST_TAG_SCORING

# docker compose exec backend sh -lc 'cd /app && pytest tests/test_graph_api.py -q'
client = TestClient(app)


def delete_feedback_fixture() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM recommendation_feedback
                WHERE source_entity_type = 'artist'
                  AND source_entity_id = 2178
                  AND candidate_entity_type = 'artist'
                  AND candidate_entity_id = 2829
                """
            )


def test_graph_smoke():
    response = client.get("/api/graph")
    assert response.status_code == 200

    data = response.json()
    assert "nodes" in data
    assert "links" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["links"], list)


def test_graph_filters_by_genre():
    response = client.get("/api/graph", params={"genre": "techno"})
    assert response.status_code == 200

    data = response.json()
    event_nodes = [n for n in data["nodes"] if n["type"] == "event"]
    assert len(event_nodes) > 0
    assert all("techno" in n["genres"] for n in event_nodes)


def test_graph_rejects_invalid_date_range():
    response = client.get(
        "/api/graph",
        params={"dateFrom": "2025-12-31", "dateTo": "2025-01-01"},
    )
    assert response.status_code == 400
    assert "dateFrom must be earlier" in response.json()["detail"]


def test_graph_limit_validation():
    response = client.get("/api/graph", params={"limit": 0})
    assert response.status_code == 422


def test_graph_empty_result():
    response = client.get("/api/graph", params={"genre": "no-such-genre"})
    assert response.status_code == 200
    assert response.json() == {"nodes": [], "links": []}


def test_graph_links_reference_existing_nodes():
    response = client.get("/api/graph", params={"genre": "techno"})
    assert response.status_code == 200

    data = response.json()
    node_ids = {node["id"] for node in data["nodes"]}

    for link in data["links"]:
        assert link["source"] in node_ids
        assert link["target"] in node_ids


def test_graph_event_shape():
    response = client.get("/api/graph", params={"genre": "techno"})
    assert response.status_code == 200

    data = response.json()
    event_nodes = [n for n in data["nodes"] if n["type"] == "event"]
    assert event_nodes

    for event in event_nodes:
        assert "name" in event
        assert "date" in event
        assert "startDate" in event
        assert "endDate" in event
        assert "label" not in event
        assert "sceneFocus" not in event


def test_graph_includes_promoter_relationships():
    response = client.get("/api/graph", params={"limit": 1000})
    assert response.status_code == 200

    data = response.json()
    promoter_nodes = [n for n in data["nodes"] if n["type"] == "promoter"]
    promoter_links = [l for l in data["links"] if l["relationship"] == "organized"]
    node_ids = {node["id"] for node in data["nodes"]}

    assert promoter_nodes
    assert promoter_links

    for link in promoter_links:
        assert link["source"].startswith("promoter-")
        assert link["source"] in node_ids
        assert link["target"].startswith("event-")
        assert link["target"] in node_ids


def test_semantic_artists_endpoint_shape():
    response = client.get("/api/semantic/artists/2178", params={"limit": 3})
    assert response.status_code == 200

    data = response.json()
    assert data["entityId"] == 2178
    assert data["entityType"] == "artist"
    assert data["similar"]

    first = data["similar"][0]
    assert first["type"] == "artist"
    assert "score" in first
    assert "embeddingScore" in first
    assert "styleScore" in first
    assert "tagScore" in first
    assert "scoreBreakdown" in first
    assert set(first["scoreBreakdown"]) == {"embedding", "style", "tag"}
    assert isinstance(first["sharedStyles"], list)
    assert isinstance(first["sharedTags"], dict)


def test_semantic_artists_endpoint_debug_includes_source_and_candidate_tags():
    response = client.get("/api/semantic/artists/2178", params={"limit": 1, "debug": True})
    assert response.status_code == 200

    first = response.json()["similar"][0]
    assert set(first["debug"]) == {
        "sourceStyles",
        "candidateStyles",
        "sourceTags",
        "candidateTags",
    }
    assert isinstance(first["debug"]["sourceStyles"], list)
    assert isinstance(first["debug"]["candidateTags"], dict)


def test_extracted_tag_score_uses_weighted_type_overlap():
    source_tags = {
        "collective": ["Tres Bienski"],
        "residency": ["Tres Bienski"],
        "role": ["dj"],
    }
    candidate_tags = {
        "collective": ["Tres Bienski"],
        "residency": ["Tres Bienski"],
        "role": ["dj"],
    }

    score = extracted_tag_score(source_tags, candidate_tags, DEFAULT_SEMANTIC_ARTIST_TAG_SCORING)

    assert score == 0.30 + 0.25 + 0.10 * 0.5


def test_recommendations_endpoint_alias_still_works():
    response = client.get("/api/recommendations/events/1", params={"limit": 1})
    assert response.status_code == 200
    assert response.json()["similar"]


def test_artist_recommendations_endpoint_uses_recommendation_contract():
    response = client.get("/api/recommendations/artists/2178", params={"limit": 3})
    assert response.status_code == 200

    data = response.json()
    assert data["entityId"] == 2178
    assert data["entityType"] == "artist"
    assert data["recommendations"]
    assert "similar" not in data

    first = data["recommendations"][0]
    assert first["type"] == "artist"
    assert "score" in first
    assert "semanticScore" in first
    assert "graphScore" in first
    assert set(first["scoreBreakdown"]) == {"semantic", "graph"}
    assert set(first["semanticBreakdown"]) == {"embedding", "style", "tag"}
    assert isinstance(first["reasons"], list)
    assert isinstance(first["sharedStyles"], list)
    assert isinstance(first["sharedTags"], dict)


def test_recommendation_feedback_can_be_upserted_and_listed():
    delete_feedback_fixture()
    payload = {
        "sourceEntityType": "artist",
        "sourceEntityId": 2178,
        "candidateEntityType": "artist",
        "candidateEntityId": 2829,
        "feedback": "positive",
        "reason": "strong style overlap",
    }

    response = client.post("/api/recommendation-feedback", json=payload)
    assert response.status_code == 200
    created = response.json()
    assert created["sourceEntityType"] == "artist"
    assert created["candidateEntityId"] == 2829
    assert created["feedback"] == "positive"
    assert created["reason"] == "strong style overlap"

    update_response = client.post(
        "/api/recommendation-feedback",
        json={**payload, "feedback": "hidden", "reason": "testing upsert"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["id"] == created["id"]
    assert updated["feedback"] == "hidden"
    assert updated["reason"] == "testing upsert"

    list_response = client.get(
        "/api/recommendation-feedback",
        params={
            "sourceEntityType": "artist",
            "sourceEntityId": 2178,
            "candidateEntityType": "artist",
            "candidateEntityId": 2829,
        },
    )
    assert list_response.status_code == 200
    items = list_response.json()["feedback"]
    assert items
    assert items[0]["id"] == created["id"]
    delete_feedback_fixture()


def test_recommendation_feedback_rejects_missing_entities():
    response = client.post(
        "/api/recommendation-feedback",
        json={
            "sourceEntityType": "artist",
            "sourceEntityId": 999999999,
            "candidateEntityType": "artist",
            "candidateEntityId": 2829,
            "feedback": "negative",
        },
    )

    assert response.status_code == 404
