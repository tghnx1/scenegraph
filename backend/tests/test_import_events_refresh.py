from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.import_events import import_event


class FakeImportCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple | list | None]] = []
        self._next_row: dict[str, int] = {"id": 100}
        self._next_lookup_id = 200

    def execute(self, query: str, params=None):
        normalized = " ".join(query.split())
        self.executed.append((normalized, params))
        if normalized.startswith("INSERT INTO events"):
            self._next_row = {"id": 100}
        elif "RETURNING id" in normalized:
            self._next_lookup_id += 1
            self._next_row = {"id": self._next_lookup_id}
        else:
            self._next_row = {"id": 100}

    def fetchone(self):
        return self._next_row


def test_import_event_rebuilds_refreshable_event_relations_before_linking():
    cursor = FakeImportCursor()

    import_event(
        cursor,
        {
            "id": "2472941",
            "title": "Fresh title",
            "date": "2026-06-26T00:00:00+00:00",
            "lineup": "Artist A\nArtist C",
            "content": "Fresh description",
            "artists": [
                {"id": "1", "name": "Artist A"},
                {"id": "3", "name": "Artist C"},
            ],
            "genres": [{"id": "10", "name": "Techno", "slug": "techno"}],
            "promoters": [{"id": "20", "name": "Promoter", "contentUrl": "/promoters/20"}],
            "images": [{"id": "30", "filename": "https://example.com/flyer.jpg"}],
        },
    )

    queries = [query for query, _params in cursor.executed]
    delete_artist_index = queries.index("DELETE FROM event_artists WHERE event_id = %s")
    delete_genre_index = queries.index("DELETE FROM event_genres WHERE event_id = %s")
    delete_promoter_index = queries.index("DELETE FROM event_promoters WHERE event_id = %s")
    delete_image_index = queries.index("DELETE FROM event_images WHERE event_id = %s")
    first_artist_link_index = next(index for index, query in enumerate(queries) if query.startswith("INSERT INTO event_artists"))
    first_genre_link_index = next(index for index, query in enumerate(queries) if query.startswith("INSERT INTO event_genres"))
    first_promoter_link_index = next(index for index, query in enumerate(queries) if query.startswith("INSERT INTO event_promoters"))
    first_image_link_index = next(index for index, query in enumerate(queries) if query.startswith("INSERT INTO event_images"))

    assert delete_artist_index < first_artist_link_index
    assert delete_genre_index < first_genre_link_index
    assert delete_promoter_index < first_promoter_link_index
    assert delete_image_index < first_image_link_index
    assert any(query.startswith("INSERT INTO event_source_payloads") for query in queries)
