import urllib.request
import json
import sys
import os
import random
import time
from datetime import datetime, timedelta
import subprocess
import calendar
import logging

log_file = "/Users/tghnx1/Desktop/42/scenegraph/Parsers/parse_past_events.log"
logging.basicConfig(
    filename=log_file,
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
]

def get_random_ua():
    return random.choice(USER_AGENTS)

def fetch_single_event(event_id):
    payload = {
        "operationName": "GET_EVENT",
        "variables": {"id": str(event_id)},
        "query": GRAPHQL_QUERY
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": get_random_ua(),
        "Referer": f"https://ra.co/events/de/berlin",
        "Origin": "https://ra.co"
    }

    req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        error_msg = f"Error fetching event {event_id}: {e}"
        print(error_msg, file=sys.stderr)
        logging.error(error_msg)
        return None

def get_month_chunks(start_date_str, end_date_str):
    chunks = []
    start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    current = start
    while current <= end:
        # End of the current month
        # Find number of days in the current month
        days_in_month = calendar.monthrange(current.year, current.month)[1]
        month_end = current.replace(day=days_in_month)

        # If month_end is beyond the ultimate end date, cap it
        if month_end > end:
            month_end = end

        chunks.append((current.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")))

        # Move to the first day of the next month
        current = month_end + timedelta(days=1)

    chunks.reverse()
    return chunks

def main():
    out_file = "/Users/tghnx1/Desktop/42/scenegraph/Parsers/ra_berlin_past_events.json"

    # 4. Incremental Deduplication: Load existing data
    past_events = []
    scraped_ids = set()
    if os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    past_events = json.loads(content)
                    scraped_ids = {str(e.get("id")) for e in past_events if "id" in e}
            print(f"Loaded {len(scraped_ids)} existing events from {out_file}.")
        except Exception as e:
            error_msg = f"Error loading existing events file: {e}"
            print(error_msg)
            logging.error(error_msg)

    # 1. Chunk the Date Ranges
    today_str = datetime.now().strftime("%Y-%m-%d")
    date_chunks = get_month_chunks("2010-01-01", today_str)

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

    # To replace 'page: 1' with variable in query
    list_query_paginated = """
    query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, $page: Int!) {
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
    """

    new_events_count = 0

    for chunk_start, chunk_end in date_chunks:
        print(f"\n--- Fetching event IDs for date range {chunk_start} to {chunk_end} ---")
        month_start_time = time.time()

        # 2. Implement Pagination
        page = 1
        while True:
            list_payload = {
                "operationName": "GET_EVENT_LISTINGS",
                "variables": {
                    "filters": {
                        "areas": {"eq": 34},
                        "listingDate": {"gte": chunk_start, "lte": chunk_end}
                    },
                    "filterOptions": {},
                    "page": page
                },
                "query": list_query_paginated
            }

            cmd = [
                "curl", "-s", URL,
                "-H", "Content-Type: application/json",
                "-H", f"User-Agent: {get_random_ua()}",
                "-H", "Referer: https://ra.co/events/de/berlin",
                "--data-raw", json.dumps(list_payload)
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                list_data = json.loads(result.stdout)

                if "errors" in list_data:
                    error_msg = f"GraphQL Errors on page {page}: {list_data['errors']}"
                    print(error_msg)
                    logging.error(error_msg)
                    break

                listings = list_data.get("data", {}).get("eventListings", {}).get("data", [])
                if not listings:
                    print(f"  Page {page} empty. Moving to next chunk.")
                    break

                page_event_ids = [item["event"]["id"] for item in listings if item.get("event") and item["event"].get("id")]
                print(f"  Found {len(page_event_ids)} events on page {page}.")

                for eid in page_event_ids:
                    # Deduplication check
                    if str(eid) in scraped_ids:
                        # print(f"    Skipping {eid} (Already scraped)")
                        continue

                    print(f"    Fetching details for ID {eid}")
                    data = fetch_single_event(eid)

                    if data and data.get("data") and data["data"].get("event"):
                        event = data["data"]["event"]
                        # 3. Remove Exact Date Validation
                        past_events.append(event)
                        scraped_ids.add(str(eid))
                        new_events_count += 1

                        # 5. Add Checkpointing
                        if new_events_count % 50 == 0:
                            print(f"  [Checkpointing] Saving {len(past_events)} events to disk...")
                            with open(out_file, "w", encoding="utf-8") as f:
                                json.dump(past_events, f, ensure_ascii=False, indent=2)

                    else:
                        warning_msg = f"    -> Error or invalid data for event {eid}"
                        print(warning_msg)
                        logging.warning(warning_msg)

                    # 6. Use Randomized Delays
                    time.sleep(random.uniform(1.5, 3.5))

            except Exception as e:
                error_msg = f"Error fetching event list on page {page} via GraphQL using curl: {e}"
                print(error_msg)
                logging.error(error_msg)
                # Optional: break or sleep and retry
                break

            page += 1

        month_end_time = time.time()
        elapsed_minutes = (month_end_time - month_start_time) / 60.0
        print(f"--- Finished parsing month ({chunk_start} to {chunk_end}) in {elapsed_minutes:.2f} minutes. ---")

    # Final save
    # 7. Rename Output (done)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(past_events, f, ensure_ascii=False, indent=2)

    print(f"\\nFinished! Successfully compiled {len(past_events)} total past events to {out_file}")

if __name__ == "__main__":
    main()
