from __future__ import annotations

import json
import socket
import urllib.error
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
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        reason: str = "invalid_response",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.reason = reason
        self.status_code = status_code


def classify_listing_request_error(exc: BaseException, *, page: int) -> RAListingError:
    status_code = exc.code if isinstance(exc, urllib.error.HTTPError) else None
    if status_code == 429:
        return RAListingError(
            f"RA event listing request was rate limited on page {page}",
            retryable=True,
            reason="http_429",
            status_code=status_code,
        )
    if status_code is not None and 500 <= status_code <= 599:
        return RAListingError(
            f"RA event listing server error on page {page}",
            retryable=True,
            reason="http_5xx",
            status_code=status_code,
        )
    if status_code is not None:
        return RAListingError(
            f"RA event listing HTTP error on page {page}",
            retryable=False,
            reason="http_4xx",
            status_code=status_code,
        )

    cause = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    retryable_types = (
        ConnectionError,
        TimeoutError,
        socket.timeout,
        ConnectionResetError,
    )
    retryable = isinstance(cause, retryable_types) or isinstance(exc, retryable_types)
    return RAListingError(
        f"RA event listing request failed on page {page}: {type(exc).__name__}",
        retryable=retryable,
        reason="transport" if retryable else "request_failed",
    )


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


def extract_event_listings(body: Any, *, page: int) -> list[dict[str, str]]:
    if not isinstance(body, dict):
        raise RAListingError(f"RA event listing response was not an object on page {page}")
    if body.get("errors"):
        raise RAListingError(f"RA event listing GraphQL error on page {page}")
    listings = body.get("data", {}).get("eventListings", {}).get("data", [])
    if not isinstance(listings, list):
        raise RAListingError(f"RA event listing data was not a list on page {page}")
    normalized: list[dict[str, str]] = []
    for item in listings:
        if not isinstance(item, dict) or not isinstance(item.get("event"), dict):
            continue
        event = item["event"]
        if event.get("id") is None:
            continue
        normalized.append(
            {
                "id": str(event["id"]),
                "date": str(event.get("date") or ""),
            }
        )
    return normalized


def extract_event_listing_ids(body: Any, *, page: int) -> list[str]:
    return [listing["id"] for listing in extract_event_listings(body, page=page)]


def fetch_event_listing_page(
    min_date: str,
    max_date: str,
    page: int,
    *,
    area_id: int = BERLIN_AREA_ID,
    timeout: float = 15.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
    user_agent: str = "ScenegraphCoverage/1.0",
) -> list[dict[str, str]]:
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
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RAListingError(
            f"RA event listing response could not be decoded on page {page}",
            retryable=False,
            reason="invalid_json",
        ) from exc
    except Exception as exc:
        raise classify_listing_request_error(exc, page=page) from exc

    return extract_event_listings(body, page=page)


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
    return [
        listing["id"]
        for listing in fetch_event_listing_page(
            min_date,
            max_date,
            page,
            area_id=area_id,
            timeout=timeout,
            opener=opener,
            user_agent=user_agent,
        )
    ]


def fetch_event_listings(
    min_date: str,
    max_date: str,
    *,
    area_id: int = BERLIN_AREA_ID,
    max_pages: int = 100,
    page_fetcher: Callable[[str, str, int], list[dict[str, str]]] | None = None,
) -> list[dict[str, str]]:
    fetch_page = page_fetcher or (
        lambda start, end, page: fetch_event_listing_page(
            start,
            end,
            page,
            area_id=area_id,
        )
    )
    listings_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for page in range(1, max_pages + 1):
        page_listings = fetch_page(min_date, max_date, page)
        if not page_listings:
            return list(listings_by_key.values())
        for listing in page_listings:
            key = (str(listing["id"]), str(listing.get("date") or ""))
            listings_by_key[key] = {"id": key[0], "date": key[1]}
    raise RAListingError(f"RA event listing exceeded the {max_pages}-page safety limit")


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
