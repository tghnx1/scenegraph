from app.promoter_graph import project_path_subgraph, promoter_recommendation_reasons, promoter_recommendation_status
from app.recommendation_scoring import DEFAULT_PROMOTER_RECOMMENDATION_SCORING
from app.schemas import GraphLink, GraphNode


def test_promoter_recommendation_reasons_use_displayed_titles_count_for_event_reasons():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 0,
        "matched_artist_count": 0,
        "event_similarity_count": 1,
        "event_similarity_event_titles": ["A", "B"],
        "shared_extracted_genres": ["techno", "ebm"],
        "shared_themes": [],
        "shared_moods": [],
        "latest_event_date": None,
    }

    reasons = promoter_recommendation_reasons(row)

    assert reasons == [
        "1 similar promoter events",
        "2 shared extracted genres: techno, ebm",
    ]


def test_promoter_recommendation_reasons_show_manual_even_without_coplayed():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 0,
        "manual_warm_connection_count": 1,
        "matched_artist_count": 0,
        "event_similarity_count": 0,
        "event_count": 0,
        "latest_event_date": None,
    }

    reasons = promoter_recommendation_reasons(row)

    assert reasons == ["1 manually added trusted artist links"]


def test_promoter_recommendation_reasons_show_manual_artist_names():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 0,
        "manual_warm_connection_count": 1,
        "manual_warm_connection_artists": [{"id": 42, "name": "Zee Mon"}],
        "matched_artist_count": 0,
        "event_similarity_count": 0,
        "event_count": 0,
        "latest_event_date": None,
    }

    reasons = promoter_recommendation_reasons(row)

    assert reasons == ["1 manually added trusted artist links: Zee Mon"]


def test_promoter_recommendation_reasons_truncate_long_lists_and_dedupe():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 12,
        "warm_connection_artists": [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
            {"id": 3, "name": "C"},
            {"id": 4, "name": "D"},
            {"id": 5, "name": "E"},
            {"id": 6, "name": "F"},
            {"id": 7, "name": "G"},
            {"id": 8, "name": "H"},
            {"id": 9, "name": "I"},
            {"id": 10, "name": "A"},
        ],
        "manual_warm_connection_count": 0,
        "matched_artist_count": 0,
        "event_similarity_count": 0,
        "event_count": 0,
        "latest_event_date": None,
    }

    reasons = promoter_recommendation_reasons(row)

    assert reasons == [
        "12 co-played artists connected: A, B, C, D, E, +4 more",
    ]


def test_promoter_recommendation_status_marks_manual_as_warm_relevant():
    row = {
        "direct_connection_count": 0,
        "warm_connection_count": 0,
        "manual_warm_connection_count": 1,
    }

    status = promoter_recommendation_status(row, DEFAULT_PROMOTER_RECOMMENDATION_SCORING)

    assert status == "warm_relevant"


def test_project_path_subgraph_keeps_warm_manual_collapses_solid():
    nodes_by_id = {
        "artist-1": GraphNode(id="artist-1", entityId=1, type="artist", name="A"),
        "artist-2": GraphNode(id="artist-2", entityId=2, type="artist", name="B"),
        "event-1": GraphNode(id="event-1", entityId=3, type="event", name="Event"),
    }
    links = [
        GraphLink(
            source="artist-1",
            target="event-1",
            relationship="played",
            evidenceType="warm_network",
            style="solid",
            strength=0.7,
        ),
        GraphLink(
            source="artist-2",
            target="event-1",
            relationship="played",
            evidenceType="warm_network",
            style="solid",
            strength=0.7,
        ),
    ]

    _, projected_links, _, _ = project_path_subgraph(
        nodes_by_id=nodes_by_id,
        links=links,
        path_node_ids={"artist-1", "artist-2", "event-1"},
        path_link_keys={"artist-1|event-1", "artist-2|event-1"},
    )

    assert projected_links[0].style == "solid"


def test_project_path_subgraph_marks_mixed_collapses_dashed():
    nodes_by_id = {
        "artist-1": GraphNode(id="artist-1", entityId=1, type="artist", name="A"),
        "artist-2": GraphNode(id="artist-2", entityId=2, type="artist", name="B"),
        "event-1": GraphNode(id="event-1", entityId=3, type="event", name="Event"),
    }
    links = [
        GraphLink(
            source="artist-1",
            target="event-1",
            relationship="played",
            evidenceType="semantic_bridge",
            style="solid",
            strength=0.7,
        ),
        GraphLink(
            source="artist-2",
            target="event-1",
            relationship="played",
            evidenceType="semantic_bridge",
            style="dashed",
            strength=0.7,
        ),
    ]

    _, projected_links, _, _ = project_path_subgraph(
        nodes_by_id=nodes_by_id,
        links=links,
        path_node_ids={"artist-1", "artist-2", "event-1"},
        path_link_keys={"artist-1|event-1", "artist-2|event-1"},
    )

    assert projected_links[0].style == "dashed"


def test_project_path_subgraph_prefers_solid_style_when_merging_projected_links():
    nodes_by_id = {
        "artist-1": GraphNode(id="artist-1", entityId=1, type="artist", name="A"),
        "artist-2": GraphNode(id="artist-2", entityId=2, type="artist", name="B"),
        "event-1": GraphNode(id="event-1", entityId=3, type="event", name="Warm Event"),
        "event-2": GraphNode(id="event-2", entityId=4, type="event", name="Semantic Event"),
    }
    links = [
        GraphLink(
            source="artist-1",
            target="event-1",
            relationship="played",
            evidenceType="warm_network",
            style="solid",
            strength=0.6,
        ),
        GraphLink(
            source="artist-2",
            target="event-1",
            relationship="played",
            evidenceType="warm_network",
            style="solid",
            strength=0.6,
        ),
        GraphLink(
            source="artist-1",
            target="event-2",
            relationship="played",
            evidenceType="semantic_bridge",
            style="solid",
            strength=0.9,
        ),
        GraphLink(
            source="artist-2",
            target="event-2",
            relationship="played",
            evidenceType="semantic_bridge",
            style="solid",
            strength=0.9,
        ),
    ]

    _, projected_links, _, _ = project_path_subgraph(
        nodes_by_id=nodes_by_id,
        links=links,
        path_node_ids={"artist-1", "artist-2", "event-1", "event-2"},
        path_link_keys={
            "artist-1|event-1",
            "artist-2|event-1",
            "artist-1|event-2",
            "artist-2|event-2",
        },
    )

    assert projected_links[0].style == "solid"
