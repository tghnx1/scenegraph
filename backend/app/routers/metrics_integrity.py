
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from psycopg import Connection
from psycopg.rows import dict_row

class IntegrityItem(BaseModel):
    id: str
    label: str
    value: Any
    total: Optional[int] = None
    percentage: Optional[float] = None
    status: str
    meaning: str
    why_it_matters: str = Field(alias="whyItMatters")
    fix: Optional[str] = None

    class Config:
        populate_by_name = True


class IntegritiesResponse(BaseModel):
    latest_source_payload: Optional[str]
    integrity_lists: List[IntegrityItem]

INTEGRITY_SQL = """
WITH
artist_event_counts AS (
    SELECT artist_id, COUNT(*) AS n
    FROM event_artists
    GROUP BY artist_id
),
event_artist_counts AS (
    SELECT event_id, COUNT(*) AS n
    FROM event_artists
    GROUP BY event_id
),
promoter_event_counts AS (
    SELECT promoter_id, COUNT(*) AS n
    FROM event_promoters
    GROUP BY promoter_id
),
event_promoter_counts AS (
    SELECT event_id, COUNT(*) AS n
    FROM event_promoters
    GROUP BY event_id
),
event_genre_counts AS (
    SELECT event_id, COUNT(*) AS n
    FROM event_genres
    GROUP BY event_id
),
artist_embedding_ids AS (
    SELECT DISTINCT entity_id
    FROM entity_embeddings
    WHERE entity_type = 'artist'
),
event_embedding_ids AS (
    SELECT DISTINCT entity_id
    FROM entity_embeddings
    WHERE entity_type = 'event'
),
artist_tag_ids AS (
    SELECT DISTINCT artist_id
    FROM artist_extracted_tags
),
event_tag_ids AS (
    SELECT DISTINCT event_id
    FROM event_extracted_tags
),
base_counts AS (
    SELECT
        (SELECT COUNT(*) FROM artists) AS total_artists,
        (SELECT COUNT(*) FROM promoters) AS total_promoters,
        (SELECT COUNT(*) FROM venues) AS total_venues,
        (SELECT COUNT(*) FROM events) AS total_events,
        (SELECT COUNT(*) FROM events WHERE venue_id IS NOT NULL) AS event_venue_links,
        (SELECT MAX(fetched_at) FROM event_source_payloads) AS latest_fetched_at
)
SELECT
    to_char(base_counts.latest_fetched_at, 'YYYY-MM-DD HH24:MI:SS') AS latest_source_payload,
    COALESCE((SELECT SUM(n) FROM artist_event_counts), 0)::bigint AS event_artist_links,
    COALESCE((SELECT SUM(n) FROM event_promoter_counts), 0)::bigint AS event_promoter_links,
    base_counts.event_venue_links AS event_venue_links,
    base_counts.total_events AS total_events,

    base_counts.total_artists - (SELECT COUNT(*) FROM artist_event_counts) AS artists_without_event,
    base_counts.total_artists AS total_artists,
    base_counts.total_promoters - (SELECT COUNT(*) FROM promoter_event_counts) AS promoters_without_event,
    base_counts.total_promoters AS total_promoters,
    base_counts.total_venues - (SELECT COUNT(DISTINCT venue_id) FROM events WHERE venue_id IS NOT NULL) AS venues_without_event,
    base_counts.total_venues AS total_venues,

    base_counts.total_events - (SELECT COUNT(*) FROM event_artist_counts) AS events_without_artists,
    base_counts.total_events - (SELECT COUNT(*) FROM event_promoter_counts) AS events_without_promoter,

    (SELECT ROUND(AVG(n)::numeric, 2) FROM artist_event_counts) AS avg_events_per_artist,
    (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n) FROM artist_event_counts) AS med_events_per_artist,
    (SELECT ROUND(AVG(n)::numeric, 2) FROM promoter_event_counts) AS avg_events_per_promoter,
    (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n) FROM promoter_event_counts) AS med_events_per_promoter,
    (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n) FROM event_promoter_counts) AS med_promoters_per_event,
    (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n) FROM event_genre_counts) AS med_genres_per_event,

    (SELECT COUNT(*) FROM artist_embedding_ids) AS artists_with_embeddings,
    base_counts.total_artists - (SELECT COUNT(*) FROM artist_embedding_ids) AS artists_without_embeddings,
    base_counts.total_artists - (SELECT COUNT(*) FROM artist_tag_ids) AS artists_without_tags,
    (SELECT COUNT(*) FROM event_embedding_ids) AS events_with_embeddings,
    base_counts.total_events - (SELECT COUNT(*) FROM event_embedding_ids) AS events_without_embeddings,
    base_counts.total_events - (SELECT COUNT(*) FROM event_tag_ids) AS events_without_tags,

    (SELECT COUNT(*) FROM artist_event_counts) AS artists_with_graph_input,
    (
        SELECT COUNT(*)
        FROM artist_embedding_ids ae
        JOIN artist_event_counts aec ON aec.artist_id = ae.entity_id
    ) AS artists_with_both_inputs,
    (
        SELECT COUNT(*)
        FROM events e
        LEFT JOIN event_artist_counts eac ON eac.event_id = e.id
        LEFT JOIN event_promoter_counts epc ON epc.event_id = e.id
        LEFT JOIN event_genre_counts egc ON egc.event_id = e.id
        WHERE e.venue_id IS NOT NULL
            OR eac.event_id IS NOT NULL
            OR epc.event_id IS NOT NULL
            OR egc.event_id IS NOT NULL
    ) AS events_with_graph_input,
    (
        SELECT COUNT(*)
        FROM event_embedding_ids ee
        JOIN events e ON e.id = ee.entity_id
        LEFT JOIN event_artist_counts eac ON eac.event_id = ee.entity_id
        LEFT JOIN event_promoter_counts epc ON epc.event_id = ee.entity_id
        LEFT JOIN event_genre_counts egc ON egc.event_id = ee.entity_id
        WHERE e.venue_id IS NOT NULL
            OR eac.event_id IS NOT NULL
            OR epc.event_id IS NOT NULL
            OR egc.event_id IS NOT NULL
    ) AS events_with_both_inputs
FROM base_counts;
"""

def compute_status(value: int, total: int) -> str:
    if total == 0:
        return "unknown"
    pct = value / total * 100
    if pct <= 20:
        return "good"
    if pct >= 21 and pct <= 60:
        return "warning"
    return "critical"

def get_integrity(db: Connection) -> dict:
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(INTEGRITY_SQL)
        row = cur.fetchone()

    total_events = row["total_events"]
    event_venue_links = row["event_venue_links"]
    events_without_venue = total_events - event_venue_links

    integrity_lists = [
        IntegrityItem(**{
            "id":           "event_artist_links",
            "label":        "Event-artist links",
            "value":        row["event_artist_links"],
            "total":        None,
            "percentage":   None,
            "status":       "good" if row["event_artist_links"] > 0 else "critical",
            "meaning":      "How many event ↔ artist edges exist in the graph.",
            "whyItMatters": "Without these links artists cannot be connected to promoters or venues through events.",
            "fix":          None,
        }),
        IntegrityItem(**{
            "id":           "event_promoter_links",
            "label":        "Event-promoter links",
            "value":        row["event_promoter_links"],
            "total":        None,
            "percentage":   None,
            "status":       "good" if row["event_promoter_links"] > 0 else "critical",
            "meaning":      "How many event ↔ promoter edges exist in the graph.",
            "whyItMatters": "Without these links promoters are disconnected from the scene graph.",
            "fix":          None,
        }),
        IntegrityItem(**{
            "id":           "events_venue_links",
            "label":        "Events-venue link",
            "value":        event_venue_links,
            "total":        total_events,
            "percentage":   round(event_venue_links / total_events * 100, 2) if total_events > 0 else 0.0,
            "status":       compute_status(events_without_venue, total_events),
            "meaning":      "Events that have a venue_id assigned.",
            "whyItMatters": "Events without a venue cannot form held_at graph edges.",
            "fix":          "Check import pipeline for missing venue data in source payloads.",
        }),
        IntegrityItem(**{
            "id":           "artists_without_event",
            "label":        "Artists without event",
            "value":        row["artists_without_event"],
            "total":        row["total_artists"],
            "percentage":   round(row["artists_without_event"] / row["total_artists"] * 100, 2) if row["total_artists"] > 0 else 0.0,
            "status":       compute_status(row["artists_without_event"], row["total_artists"]),
            "meaning":      "Artists that have no linked events in the database.",
            "whyItMatters": "Isolated artists cannot appear in any graph traversal or recommendation.",
            "fix":          "Check import pipeline for missing event_artists rows.",
        }),
        IntegrityItem(**{
            "id":           "promoters_without_event",
            "label":        "Promoters without event",
            "value":        row["promoters_without_event"],
            "total":        row["total_promoters"],
            "percentage":   round(row["promoters_without_event"] / row["total_promoters"] * 100, 2) if row["total_promoters"] > 0 else 0.0,
            "status":       compute_status(row["promoters_without_event"], row["total_promoters"]),
            "meaning":      "Promoters that have no linked events in the database.",
            "whyItMatters": "Isolated promoters cannot appear in any graph traversal or recommendation.",
            "fix":          "Check import pipeline for missing event_promoters rows.",
        }),
        IntegrityItem(**{
            "id":           "venues_without_event",
            "label":        "Venues without event",
            "value":        row["venues_without_event"],
            "total":        row["total_venues"],
            "percentage":   round(row["venues_without_event"] / row["total_venues"] * 100, 2) if row["total_venues"] > 0 else 0.0,
            "status":       compute_status(row["venues_without_event"], row["total_venues"]),
            "meaning":      "Venues that have no linked events in the database.",
            "whyItMatters": "Isolated venues cannot appear in any graph traversal or recommendation.",
            "fix":          "Check import pipeline for missing venue_id assignments on events.",
        }),
        IntegrityItem(**{
            "id":           "events_without_artists",
            "label":        "Events without artists",
            "value":        row["events_without_artists"],
            "total":        total_events,
            "percentage":   round(row["events_without_artists"] / total_events * 100, 2) if total_events > 0 else 0.0,
            "status":       compute_status(row["events_without_artists"], total_events),
            "meaning":      "Events with no artist linked in event_artists.",
            "whyItMatters": "Events without artists are invisible in artist-based graph traversals.",
            "fix":          "Check import pipeline for missing event_artists rows.",
        }),
        IntegrityItem(**{
            "id":           "events_without_promoter",
            "label":        "Events without promoter",
            "value":        row["events_without_promoter"],
            "total":        total_events,
            "percentage":   round(row["events_without_promoter"] / total_events * 100, 2) if total_events > 0 else 0.0,
            "status":       compute_status(row["events_without_promoter"], total_events),
            "meaning":      "Events with no promoter linked in event_promoters.",
            "whyItMatters": "Events without a promoter are missing a key scene graph connection.",
            "fix":          "Check import pipeline for missing event_promoters rows.",
        }),
        IntegrityItem(**{
            "id":           "events_without_venue",
            "label":        "Events without venue",
            "value":        events_without_venue,
            "total":        total_events,
            "percentage":   round(events_without_venue / total_events * 100, 2) if total_events > 0 else 0.0,
            "status":       compute_status(events_without_venue, total_events),
            "meaning":      "Events with no venue_id assigned.",
            "whyItMatters": "Events without a venue cannot form held_at graph edges.",
            "fix":          "Check import pipeline for missing venue data in source payloads.",
        }),
        IntegrityItem(**{
            "id":           "avg_events_per_artist",
            "label":        "Avg. events per artist",
            "value":        row["avg_events_per_artist"] or 0,
            "total":        None,
            "percentage":   None,
            "status":       "good" if (row["avg_events_per_artist"] or 0) > 1 else "warning",
            "meaning":      f"On average each artist is linked to {row['avg_events_per_artist'] or 0:.2f} events.",
            "whyItMatters": "Low averages indicate sparse artist coverage in the graph.",
            "fix":          None,
        }),
        IntegrityItem(**{
            "id":           "med_events_per_artist",
            "label":        "Median events per artist",
            "value":        round(row["med_events_per_artist"] or 0, 2),
            "total":        None,
            "percentage":   None,
            "status":       "good" if (row["med_events_per_artist"] or 0) >= 1 else "warning",
            "meaning":      f"The median artist is linked to {row['med_events_per_artist'] or 0:.1f} events.",
            "whyItMatters": "Median is more robust than average for skewed distributions.",
            "fix":          None,
        }),
        IntegrityItem(**{
            "id":           "avg_events_per_promoter",
            "label":        "Avg. events per promoter",
            "value":        row["avg_events_per_promoter"] or 0,
            "total":        None,
            "percentage":   None,
            "status":       "good" if (row["avg_events_per_promoter"] or 0) > 1 else "warning",
            "meaning":      f"On average each promoter is linked to {row['avg_events_per_promoter'] or 0:.2f} events.",
            "whyItMatters": "Low averages may indicate missing event_promoters rows.",
            "fix":          "Check import pipeline for missing event_promoters rows.",
        }),
        IntegrityItem(**{
            "id":           "med_events_per_promoter",
            "label":        "Median events per promoter",
            "value":        round(row["med_events_per_promoter"] or 0, 2),
            "total":        None,
            "percentage":   None,
            "status":       "good" if (row["med_events_per_promoter"] or 0) >= 1 else "warning",
            "meaning":      f"The median promoter is linked to {row['med_events_per_promoter'] or 0:.1f} events.",
            "whyItMatters": "Median is more robust than average for skewed distributions.",
            "fix":          None,
        }),
        IntegrityItem(**{
            "id":           "med_promoters_per_event",
            "label":        "Median promoters per event",
            "value":        round(row["med_promoters_per_event"] or 0, 2),
            "total":        None,
            "percentage":   None,
            "status":       "good" if (row["med_promoters_per_event"] or 0) >= 1 else "warning",
            "meaning":      f"The median event has {row['med_promoters_per_event'] or 0:.1f} promoters linked.",
            "whyItMatters": "Events without promoters are missing key graph connections.",
            "fix":          "Check import pipeline for missing event_promoters rows.",
        }),
        IntegrityItem(**{
            "id":           "med_genres_per_event",
            "label":        "Median genres per event",
            "value":        round(row["med_genres_per_event"] or 0, 2),
            "total":        None,
            "percentage":   None,
            "status":       "good" if (row["med_genres_per_event"] or 0) >= 1 else "warning",
            "meaning":      f"The median event has {row['med_genres_per_event'] or 0:.1f} genres linked.",
            "whyItMatters": "Events without genres cannot be filtered by style in the graph.",
            "fix":          "Check import pipeline for missing event_genres rows.",
        }),
        IntegrityItem(**{
            "id":           "artists_with_embeddings",
            "label":        "Artists with embeddings",
            "value":        row["artists_with_embeddings"],
            "total":        row["total_artists"],
            "percentage":   round(row["artists_with_embeddings"] / row["total_artists"] * 100, 2) if row["total_artists"] > 0 else 0.0,
            "status":       "good" if row["artists_with_embeddings"] == row["total_artists"] else "warning",
            "meaning":      "Artists that have a semantic embedding vector stored.",
            "whyItMatters": "Embeddings enable semantic search and similarity recommendations.",
            "fix":          None,
        }),
        IntegrityItem(**{
            "id":           "artists_without_embeddings",
            "label":        "Artists without embeddings",
            "value":        row["artists_without_embeddings"],
            "total":        row["total_artists"],
            "percentage":   round(row["artists_without_embeddings"] / row["total_artists"] * 100, 2) if row["total_artists"] > 0 else 0.0,
            "status":       compute_status(row["artists_without_embeddings"], row["total_artists"]),
            "meaning":      "Artists missing a semantic embedding vector.",
            "whyItMatters": "These artists will not appear in semantic search or similarity results.",
            "fix":          "Run the embedding pipeline for artists missing vectors.",
        }),
        IntegrityItem(**{
            "id":           "artists_without_tags",
            "label":        "Artists without extracted tags",
            "value":        row["artists_without_tags"],
            "total":        row["total_artists"],
            "percentage":   round(row["artists_without_tags"] / row["total_artists"] * 100, 2) if row["total_artists"] > 0 else 0.0,
            "status":       compute_status(row["artists_without_tags"], row["total_artists"]),
            "meaning":      "Artists with no extracted style, label or role tags.",
            "whyItMatters": "Without tags artists cannot be filtered or grouped by style in the graph.",
            "fix":          "Run the tag extraction pipeline for artists missing tags.",
        }),
        IntegrityItem(**{
            "id":           "events_with_embeddings",
            "label":        "Events with embeddings",
            "value":        row["events_with_embeddings"],
            "total":        row["total_events"],
            "percentage":   round(row["events_with_embeddings"] / row["total_events"] * 100, 2) if row["total_events"] > 0 else 0.0,
            "status":       "good" if row["events_with_embeddings"] == row["total_events"] else "warning",
            "meaning":      "Events that have a semantic embedding vector stored.",
            "whyItMatters": "Embeddings enable semantic search and similarity recommendations.",
            "fix":          None,
        }),
        IntegrityItem(**{
            "id":           "events_without_embeddings",
            "label":        "Events without embeddings",
            "value":        row["events_without_embeddings"],
            "total":        row["total_events"],
            "percentage":   round(row["events_without_embeddings"] / row["total_events"] * 100, 2) if row["total_events"] > 0 else 0.0,
            "status":       compute_status(row["events_without_embeddings"], row["total_events"]),
            "meaning":      "Events missing a semantic embedding vector.",
            "whyItMatters": "These events will not appear in semantic search or similarity results.",
            "fix":          "Run the embedding pipeline for events missing vectors.",
        }),
        IntegrityItem(**{
            "id":           "events_without_tags",
            "label":        "Events without extracted tags",
            "value":        row["events_without_tags"],
            "total":        row["total_events"],
            "percentage":   round(row["events_without_tags"] / row["total_events"] * 100, 2) if row["total_events"] > 0 else 0.0,
            "status":       compute_status(row["events_without_tags"], row["total_events"]),
            "meaning":      "Events with no extracted style, mood or theme tags.",
            "whyItMatters": "Without tags events cannot be filtered or grouped by style in the graph.",
            "fix":          "Run the tag extraction pipeline for events missing tags.",
        }),
        IntegrityItem(**{
            "id":           "artists_with_embedding_input",
            "label":        "Artists with embedding input",
            "value":        row["artists_with_embeddings"],
            "total":        row["total_artists"],
            "percentage":   round(row["artists_with_embeddings"] / row["total_artists"] * 100, 2) if row["total_artists"] > 0 else 0.0,
            "status":       "good" if row["artists_with_embeddings"] == row["total_artists"] else "warning",
            "meaning":      "Artists that have a semantic vector stored.",
            "whyItMatters": "Embedding input is required for semantic similarity recommendations.",
            "fix":          "Run the embedding pipeline for artists missing vectors.",
        }),
        IntegrityItem(**{
            "id":           "artists_with_graph_input",
            "label":        "Artists with graph input",
            "value":        row["artists_with_graph_input"],
            "total":        row["total_artists"],
            "percentage":   round(row["artists_with_graph_input"] / row["total_artists"] * 100, 2) if row["total_artists"] > 0 else 0.0,
            "status":       "good" if row["artists_with_graph_input"] == row["total_artists"] else "warning",
            "meaning":      "Artists linked to at least one event.",
            "whyItMatters": "Graph input is required for graph-based recommendations.",
            "fix":          "Check import pipeline for missing event_artists rows.",
        }),
        IntegrityItem(**{
            "id":           "artists_with_both_inputs",
            "label":        "Artists with both inputs",
            "value":        row["artists_with_both_inputs"],
            "total":        row["total_artists"],
            "percentage":   round(row["artists_with_both_inputs"] / row["total_artists"] * 100, 2) if row["total_artists"] > 0 else 0.0,
            "status":       "good" if row["artists_with_both_inputs"] == row["total_artists"] else "warning",
            "meaning":      "Artists that have both a semantic embedding and at least one event link.",
            "whyItMatters": "Only artists with both inputs are fully eligible for recommendations.",
            "fix":          "Run embedding and import pipelines for artists missing either input.",
        }),
        IntegrityItem(**{
            "id":           "events_with_embedding_input",
            "label":        "Events with embedding input",
            "value":        row["events_with_embeddings"],
            "total":        row["total_events"],
            "percentage":   round(row["events_with_embeddings"] / row["total_events"] * 100, 2) if row["total_events"] > 0 else 0.0,
            "status":       "good" if row["events_with_embeddings"] == row["total_events"] else "warning",
            "meaning":      "Events that have a semantic vector stored.",
            "whyItMatters": "Embedding input is required for semantic similarity recommendations.",
            "fix":          "Run the embedding pipeline for events missing vectors.",
        }),
        IntegrityItem(**{
            "id":           "events_with_graph_input",
            "label":        "Events with graph input",
            "value":        row["events_with_graph_input"],
            "total":        row["total_events"],
            "percentage":   round(row["events_with_graph_input"] / row["total_events"] * 100, 2) if row["total_events"] > 0 else 0.0,
            "status":       "good" if row["events_with_graph_input"] == row["total_events"] else "warning",
            "meaning":      "Events with at least one artist, promoter, venue or genre link.",
            "whyItMatters": "Graph input is required for graph-based recommendations.",
            "fix":          "Check import pipeline for missing event relationship rows.",
        }),
        IntegrityItem(**{
            "id":           "events_with_both_inputs",
            "label":        "Events with both inputs",
            "value":        row["events_with_both_inputs"],
            "total":        row["total_events"],
            "percentage":   round(row["events_with_both_inputs"] / row["total_events"] * 100, 2) if row["total_events"] > 0 else 0.0,
            "status":       "good" if row["events_with_both_inputs"] == row["total_events"] else "warning",
            "meaning":      "Events that have both a semantic embedding and at least one graph link.",
            "whyItMatters": "Only events with both inputs are fully eligible for recommendations.",
            "fix":          "Run embedding and import pipelines for events missing either input.",
        }),
    ]

    return IntegritiesResponse( 
        latest_source_payload=row["latest_source_payload"],
        integrity_lists=integrity_lists,
    )
