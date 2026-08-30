from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any


RA_GRAPHQL_URL = "https://ra.co/graphql"
BERLIN_AREA_ID = 34
EVENT_LISTINGS_QUERY = """
query GET_EVENT_LISTINGS(
  $filters: FilterInputDtoInput,
  $filterOptions: FilterOptionsInputDtoInput,
  $page: Int!
) {
  eventListings(filters: $filters, filterOptions: $filterOptions, pageSize: 100, page: $page) {
    data {
      id
      event {
        id
        title
        date
      }
    }
  }
}
""".strip()


class RAListingError(RuntimeError):
    pass


def build_event_listing_payload(
    min_date: str,
    max_date: str,
    page: int,
    *,
    area_id: int = BERLIN_AREA_ID,
) -> dict[str, Any]:
    return {
        "operationName": "GET_EVENT_LISTINGS",
        "variables": {
            "filters": {
                "areas": {"eq": area_id},
                "listingDate": {"gte": min_date, "lte": max_date},
            },
            "filterOptions": {},
            "page": page,
        },
        "query": EVENT_LISTINGS_QUERY,
    }


def extract_event_listing_ids(body: Any, *, page: int) -> list[str]:
    if not isinstance(body, dict):
        raise RAListingError(f"RA event listing response was not an object on page {page}")
    if body.get("errors"):
        raise RAListingError(f"RA event listing GraphQL error on page {page}")
    listings = body.get("data", {}).get("eventListings", {}).get("data", [])
    if not isinstance(listings, list):
        raise RAListingError(f"RA event listing data was not a list on page {page}")
    return [
        str(item["event"]["id"])
        for item in listings
        if isinstance(item, dict)
        and isinstance(item.get("event"), dict)
        and item["event"].get("id") is not None
    ]


def fetch_event_listing_page_ids(
    min_date: str,
    max_date: str,
    page: int,
    *,
    area_id: int = BERLIN_AREA_ID,
    timeout: float = 15.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
    user_agent: str = "ScenegraphCoverage/1.0",
) -> list[str]:
    payload = build_event_listing_payload(min_date, max_date, page, area_id=area_id)
    request = urllib.request.Request(
        RA_GRAPHQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": user_agent,
            "Referer": "https://ra.co/events/de/berlin",
            "Origin": "https://ra.co",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RAListingError(f"RA event listing request failed on page {page}: {type(exc).__name__}") from exc

    return extract_event_listing_ids(body, page=page)


def fetch_event_listing_ids(
    min_date: str,
    max_date: str,
    *,
    area_id: int = BERLIN_AREA_ID,
    max_pages: int = 100,
    page_fetcher: Callable[[str, str, int], list[str]] | None = None,
) -> set[str]:
    fetch_page = page_fetcher or (
        lambda start, end, page: fetch_event_listing_page_ids(
            start,
            end,
            page,
            area_id=area_id,
        )
    )
    event_ids: set[str] = set()
    for page in range(1, max_pages + 1):
        page_ids = fetch_page(min_date, max_date, page)
        if not page_ids:
            return event_ids
        event_ids.update(str(event_id) for event_id in page_ids)
    raise RAListingError(f"RA event listing exceeded the {max_pages}-page safety limit")
