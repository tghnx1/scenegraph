from __future__ import annotations

import json
import subprocess

from parsers.graphql_parser.event_listings import (
    EVENT_LISTINGS_QUERY,
    fetch_event_listing_ids,
    fetch_event_listing_page,
    fetch_event_listing_page_ids,
    fetch_event_listings,
)
from parsers.graphql_parser.parse_past_events import fetch_event_listing_page_ids_with_curl


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_listing_page_queries_exact_dates_and_returns_only_canonical_ids():
    captured = {}

    def opener(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "data": {
                    "eventListings": {
                        "data": [
                            {
                                "event": {
                                    "id": 12,
                                    "date": "2026-08-14T23:00:00.000Z",
                                    "title": "Ignored title",
                                }
                            },
                            {"event": {"id": "13", "date": "2026-08-15T21:00:00.000Z"}},
                        ]
                    }
                }
            }
        )

    result = fetch_event_listing_page_ids(DATE := "2026-08-15", DATE, 1, opener=opener)
    body = json.loads(captured["request"].data)

    assert result == ["12", "13"]
    assert body["variables"]["filters"]["listingDate"] == {"gte": DATE, "lte": DATE}
    assert body["variables"]["filters"]["areas"] == {"eq": 34}
    assert body["variables"]["page"] == 1
    assert body["query"] == EVENT_LISTINGS_QUERY


def test_listing_page_preserves_only_event_id_and_canonical_date():
    def opener(_request, *, timeout):
        assert timeout == 15.0
        return FakeResponse(
            {
                "data": {
                    "eventListings": {
                        "data": [
                            {
                                "event": {
                                    "id": "A",
                                    "date": "2026-08-27T22:00:00.000Z",
                                    "title": "Must not escape",
                                }
                            },
                            {"event": {"id": "B", "date": "2026-08-28T19:00:00.000Z"}},
                        ]
                    }
                }
            }
        )

    result = fetch_event_listing_page(
        "2026-08-28",
        "2026-08-28",
        1,
        opener=opener,
    )

    assert result == [
        {"id": "A", "date": "2026-08-27T22:00:00.000Z"},
        {"id": "B", "date": "2026-08-28T19:00:00.000Z"},
    ]


def test_listing_fetch_paginates_and_deduplicates_without_network():
    pages = {1: ["1", "2"], 2: ["2", "3"], 3: []}

    result = fetch_event_listing_ids(
        "2026-08-15",
        "2026-08-15",
        page_fetcher=lambda _start, _end, page: pages[page],
    )

    assert result == {"1", "2", "3"}


def test_listing_fetch_preserves_adjacent_date_duplicates_for_canonical_filtering():
    pages = {
        1: [
            {"id": "A", "date": "2026-08-27T22:00:00.000Z"},
            {"id": "B", "date": "2026-08-28T19:00:00.000Z"},
        ],
        2: [],
    }

    result = fetch_event_listings(
        "2026-08-28",
        "2026-08-28",
        page_fetcher=lambda _start, _end, page: pages[page],
    )

    assert result == pages[1]


def test_daily_parser_preserves_fixed_curl_listing_transport():
    captured = {}
    response = {
        "data": {
            "eventListings": {
                "data": [{"event": {"id": "12"}}, {"event": {"id": 13}}]
            }
        }
    }

    def runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(response))

    result = fetch_event_listing_page_ids_with_curl(
        "2026-08-15",
        "2026-08-15",
        2,
        user_agent="ScenegraphTest/1.0",
        runner=runner,
    )
    payload = json.loads(captured["command"][-1])

    assert result == ["12", "13"]
    assert captured["command"][:3] == ["curl", "-s", "https://ra.co/graphql"]
    assert "User-Agent: ScenegraphTest/1.0" in captured["command"]
    assert captured["kwargs"] == {"capture_output": True, "text": True, "timeout": 15}
    assert payload["variables"]["filters"]["listingDate"] == {
        "gte": "2026-08-15",
        "lte": "2026-08-15",
    }
    assert payload["variables"]["page"] == 2
