import urllib.request
import json
import sys
import re
from datetime import datetime
import time

URL = "https://ra.co/graphql"
GRAPHQL_QUERY = """
query GET_EVENT($id: ID!) {
  event(id: $id) {
    id
    title
    date
    startTime
    endTime
    interestedCount
    contentUrl
    lineup
    cost
    isTicketed
    isSaved
    isInterested
    queueItEnabled
    newEventForm
    pick {
      id
      blurb
    }
    __typename
    images {
      id
      filename
      alt
    }
    flyerFront
    venue {
      id
      name
      address
      contentUrl
      live
      __typename
    }
    promoters {
      id
      name
      __typename
    }
    artists {
      id
      name
    }
  }
}
"""

def fetch_single_event(event_id):
    payload = {
        "operationName": "GET_EVENT",
        "variables": {"id": str(event_id)},
        "query": GRAPHQL_QUERY
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": f"https://ra.co/events/de/berlin",
        "Origin": "https://ra.co"
    }

    req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Error fetching event {event_id}: {e}", file=sys.stderr)
        return None

def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"Fetching events for today ({today_str})...")

    # 1. Fetch event IDs for today via simple GraphQL list query instead of HTML (bypasses 403 block)
    list_query = """
    query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput) {
      eventListings(filters: $filters, filterOptions: $filterOptions, pageSize: 100, page: 1) {
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
    """

    list_payload = {
        "operationName": "GET_EVENT_LISTINGS",
        "variables": {
            "filters": {
                "areas": {"eq": 34}, # Use int rather than string for consistency
                "listingDate": {"gte": today_str, "lte": today_str}
            },
            "filterOptions": {}
        },
        "query": list_query
    }

    # Instead of Python's urllib (which is getting blocked or returning empty results),
    # we'll execute a bash curl command to bypass the block.
    import subprocess
    event_ids = []

    cmd = [
        "curl", "-s", "https://ra.co/graphql",
        "-H", "Content-Type: application/json",
        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Referer: https://ra.co/events/de/berlin",
        "--data-raw", json.dumps(list_payload)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        list_data = json.loads(result.stdout)

        if "errors" in list_data:
            print(f"GraphQL Errors: {list_data['errors']}")

        listings = list_data.get("data", {}).get("eventListings", {}).get("data", [])
        event_ids = [item["event"]["id"] for item in listings if item.get("event") and item["event"].get("id")]

    except Exception as e:
        print(f"Error fetching event list via GraphQL using curl: {e}")
        sys.exit(1)

    print(f"Found {len(event_ids)} potential event IDs via GraphQL list.")

    if not event_ids:
        print("No events found. Exiting.")
        sys.exit(0)

    todays_events = []

    # 2. Fetch details for each event ID
    for i, eid in enumerate(event_ids):
        print(f"Fetching {i+1}/{len(event_ids)}: ID {eid}")
        data = fetch_single_event(eid)

        if data and data.get("data") and data["data"].get("event"):
            event = data["data"]["event"]
            # The date in single event payload might have a timestamp attached. So we use .startswith()
            if event.get("date", "").startswith(today_str):
                todays_events.append(event)
            else:
                # If date format is somehow different or missing, log it to debug
                print(f"  -> Skipped: Date {event.get('date')} does not match {today_str}")
        else:
            print(f"  -> Error or invalid data for event {eid}")

        # Sleep slightly to avoid being flagged
        time.sleep(0.5)

    # Save result
    out_file = "/Users/tghnx1/Desktop/42/Transcendence/Parsers/GraphQLparser/ra_berlin_today_events.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(todays_events, f, ensure_ascii=False, indent=2)

    print(f"\nSuccessfully filtered and saved {len(todays_events)} events for today to {out_file}")

if __name__ == "__main__":
    main()
