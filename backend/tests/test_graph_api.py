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
