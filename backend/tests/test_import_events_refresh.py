from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.import_events import (
    import_event,
    load_events,
    normalized_venue_coordinates,
    normalized_venue_name,
)


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
    assert not any("recommendation_jobs" in query for query in queries)


def venue(**updates):
    value = {
        "id": "143430",
        "name": "Existing Venue",
        "address": "Uferstrasse 8-11 - 13357 Berlin",
        "area": {"id": "34", "name": "Berlin"},
        "location": {"latitude": 52.5412, "longitude": 13.3891},
    }
    value.update(updates)
    return value


def venue_insert_params(cursor):
    return next(
        params
        for query, params in cursor.executed
        if query.startswith("INSERT INTO venues")
    )


def test_blank_venue_name_uses_leading_address_segment():
    assert normalized_venue_name(
        venue(name=" ", address="Studio dB - Uferstrasse 8-11, Studio A14 - 13357 Berlin")
    ) == "Studio dB"


def test_blank_venue_name_without_usable_address_uses_ra_id():
    assert normalized_venue_name(venue(name=None, address="  ")) == "RA venue 143430"


def test_normal_venue_name_is_trimmed_and_unchanged():
    assert normalized_venue_name(venue(name="  Existing Venue  ")) == "Existing Venue"


def test_invalid_berlin_coordinates_become_null():
    assert normalized_venue_coordinates(
        venue(location={"latitude": 40.758449, "longitude": -73.990028})
    ) == (None, None)


def test_valid_berlin_coordinates_remain_unchanged():
    assert normalized_venue_coordinates(venue()) == (52.5412, 13.3891)


def test_malformed_venue_metadata_does_not_abort_valid_event_import(tmp_path):
    raw_venue = venue(
        name="",
        address="Studio dB - Uferstrasse 8-11, Studio A14 - 13357 Berlin",
        location={"latitude": 40.758449, "longitude": -73.990028},
    )
    event = {
        "id": "2433416",
        "title": "Inverted Sky:",
        "date": "2026-08-30T00:00:00+00:00",
        "venue": raw_venue,
        "artists": [],
        "genres": [],
        "promoters": [],
        "images": [],
    }
    import_path = tmp_path / "events.json"
    import_path.write_text(json.dumps([event]), encoding="utf-8")

    loaded_event = load_events(import_path)[0]
    cursor = FakeImportCursor()
    import_event(cursor, loaded_event)

    params = venue_insert_params(cursor)
    assert params[1] == "Studio dB"
    assert params[4:6] == (None, None)
    payload_params = next(
        params
        for query, params in cursor.executed
        if query.startswith("INSERT INTO event_source_payloads")
    )
    assert json.loads(payload_params[3])["venue"] == raw_venue
