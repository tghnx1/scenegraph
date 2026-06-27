import pytest
from fastapi.testclient import TestClient
from app.db import get_connection
from app.event_similarity import artist_relevant_source_event_ids
from app.main import app, extracted_tag_score
from app.recommendation_scoring import (
    DEFAULT_SEMANTIC_ARTIST_TAG_SCORING,
)

# docker compose exec backend sh -lc 'cd /app && pytest tests/test_graph_api.py -q'
client = TestClient(app)
client.headers.update({"X-User-Id": "1"})


def graph_has_genre_data() -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    EXISTS (SELECT 1 FROM event_genres)
                    OR EXISTS (
                        SELECT 1
                        FROM event_extracted_tags
                        WHERE tag_type IN ('style', 'genre')
                    ) AS has_genre_data
                """
            )
            row = cursor.fetchone()
    return bool(row["has_genre_data"]) if row is not None else False


def graph_has_promoter_data() -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    EXISTS (SELECT 1 FROM promoters)
                    AND EXISTS (SELECT 1 FROM event_promoters) AS has_promoter_data
                """
            )
            row = cursor.fetchone()
    return bool(row["has_promoter_data"]) if row is not None else False


def test_graph_smoke():
    response = client.get("/api/graph")
    assert response.status_code == 200

    data = response.json()
    assert "nodes" in data
    assert "links" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["links"], list)


def test_graph_filters_by_genre():
    if not graph_has_genre_data():
        pytest.skip("No genre data loaded in the test database")
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
    assert response.json() == {
        "nodes": [],
        "links": [],
        "preferredPathNodeIds": {},
        "preferredPathLinkKeys": {},
        "preferredPathPromoterIdsByNodeId": {},
        "preferredPathPromoterIdsByLinkKey": {},
        "fallbackPathNodeIds": {},
        "fallbackPathLinkKeys": {},
        "fallbackPathPromoterIdsByNodeId": {},
        "fallbackPathPromoterIdsByLinkKey": {},
    }


def test_graph_links_reference_existing_nodes():
    response = client.get("/api/graph", params={"genre": "techno"})
    assert response.status_code == 200

    data = response.json()
    node_ids = {node["id"] for node in data["nodes"]}

    for link in data["links"]:
        assert link["source"] in node_ids
        assert link["target"] in node_ids


def test_graph_event_shape():
    if not graph_has_genre_data():
        pytest.skip("No genre data loaded in the test database")
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
    if not graph_has_promoter_data():
        pytest.skip("No promoter graph data loaded in the test database")
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


 




def test_artist_promoter_recommendations_include_graph_payload():
    response = client.get("/api/recommendations/artists/2178/promoters", params={"limit": 3})
    assert response.status_code == 200

    data = response.json()
    assert data["entityId"] == 2178
    assert data["entityType"] == "artist"
    assert data["recommendations"]
    assert "graph" in data
    assert "analyticsGraph" in data

    first = data["recommendations"][0]
    assert first["type"] == "promoter"
    assert "score" in first
    assert set(first["scoreBreakdown"]) == {
        "semantic",
        "strength",
        "directConnection",
        "coPlayedConnection",
        "manualConnection",
        "eventSimilarity",
        "scaleFit",
        "activity",
        "recency",
    }
    assert first["matchedArtistCount"] >= 0
    assert first["eventCount"] >= 0
    assert (
        first["matchedArtistCount"] > 0
        or first["eventCount"] > 0
        or first["warmConnectionCount"] > 0
        or first["coPlayedConnectionCount"] > 0
        or first["manualConnectionCount"] > 0
        or first["scoreBreakdown"]["semantic"] > 0
        or first["scoreBreakdown"]["eventSimilarity"] > 0
    )
    assert isinstance(first["reasons"], list)
    assert first["status"] in {"new_relevant", "existing_partner", "warm_relevant"}
    assert first["warmConnectionCount"] >= 0
    assert first["coPlayedConnectionCount"] >= 0
    assert first["manualConnectionCount"] >= 0
    assert first["promoterInterestedSum"] >= 0
    assert first["promoterSizeSegment"] in {"small", "medium", "large"}
    assert first["directConnectionCount"] >= 0
    assert isinstance(first["evidence"], list)
    assert first["evidence"]
    assert "reasonDetails" in first
    assert set(first["reasonDetails"]) == {
        "similarPromoterEventTitles",
        "sharedExtractedGenres",
        "sharedExtractedGenreSources",
        "sharedThemes",
        "sharedMoods",
        "similarArtistNames",
        "coPlayedArtistNames",
        "manualArtistNames",
    }
    assert all(
        item["type"]
        in {"semantic_bridge", "direct_connection", "warm_network", "manual_connection", "event_similarity"}
        for item in first["evidence"]
    )

    graph = data["graph"]
    analytics_graph = data["analyticsGraph"]
    assert graph["nodes"]
    assert graph["links"]
    assert graph["graphMode"] == "compact"
    assert analytics_graph["graphMode"] == "full"
    assert any(node["type"] == "event" for node in analytics_graph["nodes"])
    assert "preferredPathNodeIds" in graph
    assert "preferredPathLinkKeys" in graph
    assert "preferredPathPromoterIdsByNodeId" in graph
    assert "preferredPathPromoterIdsByLinkKey" in graph
    assert "fallbackPathNodeIds" in graph
    assert "fallbackPathLinkKeys" in graph
    assert "fallbackPathPromoterIdsByNodeId" in graph
    assert "fallbackPathPromoterIdsByLinkKey" in graph
    assert all(node["type"] in {"artist", "promoter"} for node in graph["nodes"])
    semantic_link = next(
        (link for link in graph["links"] if link.get("evidenceType") == "semantic_bridge"),
        None,
    )
    assert semantic_link is not None
    assert semantic_link["style"] in {"solid", "dashed"}
    assert isinstance(semantic_link["strength"], (int, float))
    assert 0.0 <= semantic_link["strength"] <= 1.0
    assert set(data) >= {"largeRecommendations", "mediumRecommendations", "smallRecommendations"}


def test_artist_promoter_recommendations_include_debug_when_requested():
    response = client.get(
        "/api/recommendations/artists/2178/promoters",
        params={"limit": 1, "exclude_existing": "false", "debug": "true"},
    )
    assert response.status_code == 200

    data = response.json()
    assert "debug" in data
    assert set(data["debug"]) == {"candidateCounts", "filteredOut", "segments"}
    assert set(data["debug"]["filteredOut"]) >= {
        "excludeExisting",
        "eventSimilaritySamePromoter",
        "eventSimilarityLimitCutoff",
        "recommendationLimitCutoff",
    }
    assert set(data["debug"]["segments"]) >= {
        "promoterInterestedSumThresholds",
        "sourceArtistAverageInterested",
        "sourceArtistSizeSegment",
        "appliedPromoterSegmentQuotaRatios",
        "appliedPromoterSegmentQuotaCounts",
        "artistAverageInterestedThresholds",
    }
    assert set(data["debug"]["segments"]["appliedPromoterSegmentQuotaCounts"]) == {
        "small",
        "medium",
        "large",
    }
    assert data["recommendations"]
    first = data["recommendations"][0]
    assert "debug" in first
    assert set(first["debug"]) == {"rawSignals", "normalizedScores", "weightedScores"}
    assert "eventSimilarityEmbeddingScore" in first["debug"]["rawSignals"]
    assert "warmConnectionArtists" in first["debug"]["rawSignals"]
    assert "eventSimilarity" in first["debug"]["normalizedScores"]
    assert "total" in first["debug"]["weightedScores"]


def test_artist_promoter_recommendations_include_direct_connections():
    response = client.get(
        "/api/recommendations/artists/2178/promoters",
        params={"limit": 50, "exclude_existing": "false"},
    )
    assert response.status_code == 200
    data = response.json()

    direct_recommendations = [
        item for item in data["recommendations"] if item["directConnectionCount"] > 0
    ]
    for item in direct_recommendations:
        assert item["status"] == "existing_partner"
        assert item["scoreBreakdown"]["directConnection"] > 0
        assert any(evidence["type"] == "direct_connection" for evidence in item["evidence"])

    direct_links = [
        link
        for link in data["analyticsGraph"]["links"]
        if link.get("evidenceType") == "direct_connection"
    ]
    if direct_recommendations:
        assert direct_links
        assert all(link.get("style") == "solid" for link in direct_links)
    else:
        assert not direct_links


def test_artist_promoter_recommendations_exclude_existing_by_default():
    response = client.get("/api/recommendations/artists/2178/promoters", params={"limit": 50})
    assert response.status_code == 200
    data = response.json()

    assert all(item["directConnectionCount"] == 0 for item in data["recommendations"])
    assert all(item["scoreBreakdown"]["directConnection"] == 0 for item in data["recommendations"])
    assert all(item["status"] != "existing_partner" for item in data["recommendations"])
    assert not any(
        link.get("evidenceType") == "direct_connection" for link in data["analyticsGraph"]["links"]
    )


def test_artist_promoter_recommendations_include_warm_network_connections():
    response = client.get("/api/recommendations/artists/2178/promoters", params={"limit": 50})
    assert response.status_code == 200
    data = response.json()

    warm_recommendations = [
        item for item in data["recommendations"] if item["warmConnectionCount"] > 0
    ]
    for item in warm_recommendations:
        assert (
            item["scoreBreakdown"]["coPlayedConnection"] > 0
            or item["scoreBreakdown"]["manualConnection"] > 0
        )
        assert item["warmConnectionArtists"]
        assert all("id" in artist and "name" in artist for artist in item["warmConnectionArtists"])
        assert any(evidence["type"] == "warm_network" for evidence in item["evidence"])

    warm_links = [
        link
        for link in data["analyticsGraph"]["links"]
        if link.get("evidenceType") == "warm_network"
    ]
    if warm_recommendations:
        assert warm_links
        assert all(link.get("style") == "solid" for link in warm_links)
    else:
        assert not warm_links


def test_artist_promoter_recommendations_manual_connections_boost_warm_score():
    response = client.get("/api/recommendations/artists/2178/promoters", params={"limit": 50})
    assert response.status_code == 200
    data = response.json()

    manual_recommendations = [
        item for item in data["recommendations"] if item.get("manualConnectionCount", 0) > 0
    ]
    if manual_recommendations:
        assert all(item["scoreBreakdown"]["manualConnection"] > 0 for item in manual_recommendations)


def test_artist_promoter_recommendations_include_event_similarity_connections():
    response = client.get(
        "/api/recommendations/artists/2178/promoters",
        params={"limit": 50},
    )
    assert response.status_code == 200
    data = response.json()

    event_similarity_recommendations = [
        item for item in data["recommendations"] if item["scoreBreakdown"]["eventSimilarity"] > 0
    ]
    has_event_similarity_evidence = any(
        any(evidence["type"] == "event_similarity" for evidence in item["evidence"])
        for item in event_similarity_recommendations
    )

    event_similarity_links = [
        link
        for link in data["analyticsGraph"]["links"]
        if link.get("evidenceType") == "event_similarity"
    ]
    if event_similarity_recommendations and has_event_similarity_evidence:
        assert event_similarity_links
        assert all(link.get("style") in {"solid", "dashed"} for link in event_similarity_links)
    elif event_similarity_recommendations:
        # eventSimilarity can come from embedding-only signal even when no symbolic path exists
        assert not event_similarity_links
    else:
        assert not event_similarity_links


def test_artist_promoter_recommendations_preserve_existing_contract_fields():
    response = client.get("/api/recommendations/artists/2178/promoters", params={"limit": 1})
    assert response.status_code == 200

    data = response.json()
    first = data["recommendations"][0]
    assert "score" in first
    assert "semanticScore" in first
    assert "strengthScore" in first
    assert "activityScore" in first
    assert "recencyScore" in first
    assert "scoreBreakdown" in first
    assert "matchedArtistCount" in first
    assert "eventCount" in first
    assert "reasons" in first
    assert "graph" in data
    assert "analyticsGraph" in data
    assert "nodes" in data["graph"]
    assert "links" in data["graph"]
