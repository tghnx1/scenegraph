from fastapi.testclient import TestClient
from app.main import app

# docker compose exec backend sh -lc 'cd /app && pytest tests/test_graph_api.py -q'
client = TestClient(app)


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


def test_similar_events_endpoint_shape():
    response = client.get("/api/similar/events/1", params={"limit": 3})
    assert response.status_code == 200

    data = response.json()
    assert data["entityId"] == 1
    assert data["entityType"] == "event"
    assert data["similar"]
    assert "recommendations" not in data

    first = data["similar"][0]
    assert first["type"] == "event"
    assert "score" in first
    assert "semanticScore" in first
    assert "graphScore" in first
    assert isinstance(first["reasons"], list)


def test_similar_artists_endpoint_allows_empty_results_after_filtering():
    response = client.get("/api/similar/artists/1", params={"limit": 3})
    assert response.status_code == 200

    data = response.json()
    assert data["entityId"] == 1
    assert data["entityType"] == "artist"
    assert isinstance(data["similar"], list)


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
    assert isinstance(first["sharedStyles"], list)
    assert isinstance(first["sharedTags"], dict)


def test_recommendations_endpoint_alias_still_works():
    response = client.get("/api/recommendations/events/1", params={"limit": 1})
    assert response.status_code == 200
    assert response.json()["similar"]
