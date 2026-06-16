
from pydantic import BaseModel, Field
from typing import List
from psycopg import Connection
from psycopg.rows import dict_row

class TopListEntry(BaseModel):
    name: str
    count: int
    rank: int

class TopList(BaseModel):
    id: str
    label: str
    items: List[TopListEntry]
    meaning: str
    why_it_matters: str = Field(alias="whyItMatters")

    class Config:
        populate_by_name = True

class TopListsResponse(BaseModel):
    top_lists: List[TopList]

TOP_LISTS_SQL = """
SELECT
    'source_genres' AS list,
    g.id, g.name, COUNT(*) AS event_count
FROM event_genres eg
JOIN genres g ON g.id = eg.genre_id
GROUP BY g.id, g.name
ORDER BY event_count DESC, g.name ASC
LIMIT 5;
"""

TOP_EXTRACTED_GENRES_SQL = """
SELECT
    0 AS id,
    tag_value AS name,
    COUNT(*) AS event_count
FROM artist_extracted_tags
WHERE tag_type = 'style'
GROUP BY tag_value
ORDER BY event_count DESC, tag_value ASC
LIMIT 5;
"""

TOP_VENUES_SQL = """
SELECT v.id, v.name, COUNT(*) AS event_count
FROM events e
JOIN venues v ON v.id = e.venue_id
GROUP BY v.id, v.name
ORDER BY event_count DESC, v.name ASC
LIMIT 5;
"""

TOP_PROMOTERS_SQL = """
SELECT p.id, p.name, COUNT(*) AS event_count
FROM event_promoters ep
JOIN promoters p ON p.id = ep.promoter_id
GROUP BY p.id, p.name
ORDER BY event_count DESC, p.name ASC
LIMIT 5;
"""

TOP_ARTISTS_SQL = """
SELECT a.id, a.name, COUNT(*) AS event_count
FROM event_artists ea
JOIN artists a ON a.id = ea.artist_id
GROUP BY a.id, a.name
ORDER BY event_count DESC, a.name ASC
LIMIT 5;
"""

def get_rankings(db: Connection) -> dict:
    def fetch(sql: str, has_id: bool = True) -> List[TopListEntry]:
        with db.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return [
                TopListEntry(
                    name=row["name"],
                    count=row["event_count"],
                    rank=i + 1,
                )
                for i, row in enumerate(cur.fetchall())
            ]

    return TopListsResponse(top_lists=[
        TopList(**{
            "id":           "top_source_genres",
            "label":        "Top 5 source genres",
            "items":        fetch(TOP_LISTS_SQL),
            "meaning":      "Most common RA source genres linked to events.",
            "whyItMatters": "Shows which genres dominate the imported dataset.",
        }),
        TopList(**{
            "id":           "top_extracted_genres",
            "label":        "Top 5 extracted genres",
            "items":        fetch(TOP_EXTRACTED_GENRES_SQL, has_id=False),
            "meaning":      "Most common LLM-extracted style tags across artists.",
            "whyItMatters": "Shows which styles are most represented in the scene graph.",
        }),
        TopList(**{
            "id":           "top_venues",
            "label":        "Top 5 venues",
            "items":        fetch(TOP_VENUES_SQL),
            "meaning":      "Venues with the most linked events.",
            "whyItMatters": "Highlights the most active locations in the scene.",
        }),
        TopList(**{
            "id":           "top_promoters",
            "label":        "Top 5 promoters",
            "items":        fetch(TOP_PROMOTERS_SQL),
            "meaning":      "Promoters with the most linked events.",
            "whyItMatters": "Identifies the most active promoters in the dataset.",
        }),
        TopList(**{
            "id":           "top_artists",
            "label":        "Top 5 artists",
            "items":        fetch(TOP_ARTISTS_SQL),
            "meaning":      "Artists with the most linked events.",
            "whyItMatters": "Identifies the most active artists in the scene graph.",
        }),
    ])