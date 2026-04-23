import requests
import random
import time
from datetime import datetime, timedelta

AREA_ID = 34  # Berlin
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

def get_furthest_event(days_forward):
    today = datetime.now()
    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=days_forward)).strftime("%Y-%m-%d")
    url = "https://ra.co/graphql"
    session = requests.Session()
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Content-Type": "application/json",
        "Referer": "https://ra.co/events/de/berlin",
        "Origin": "https://ra.co"
    }
    query = """
    query GET_ALL_EVENTS($filters: FilterInputDtoInput, $pageSize: Int, $page: Int) {
      eventListings(filters: $filters, pageSize: $pageSize, page: $page) {
        data {
          event {
            id
            date
          }
        }
        totalResults
      }
    }
    """
    page = 1
    page_size = 50
    furthest_date = None
    event_count = 0
    while True:
        variables = {
            "filters": {
                "areas": {"eq": AREA_ID},
                "listingDate": {"gte": start_date, "lte": end_date}
            },
            "pageSize": page_size,
            "page": page
        }
        response = session.post(url, json={'query': query, 'variables': variables}, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        listings = data.get('data', {}).get('eventListings', {}).get('data', [])
        if not listings:
            break
        for item in listings:
            event = item.get('event', {})
            date_str = event.get('date', '')
            event_count += 1
            try:
                event_date = datetime.fromisoformat(date_str[:10])
                if furthest_date is None or event_date > furthest_date:
                    furthest_date = event_date
            except Exception:
                continue
        if len(listings) < page_size:
            break
        page += 1
        time.sleep(random.uniform(0.2, 0.5))
    return furthest_date, event_count

# Main logic: increase DAYS_FORWARD until furthest date stops increasing
max_days = 30
step = 30
last_furthest = None
unchanged_count = 0
while True:
    print(f"Checking {max_days} days ahead...")
    result = get_furthest_event(max_days)
    if result is None or result[0] is None:
        print("No events found.")
        break
    furthest, event_count = result
    days_diff = (furthest.date() - datetime.now().date()).days
    print(f"Furthest event date found: {furthest.date()} ({days_diff} days from today) | Events: {event_count}")
    if last_furthest is not None and furthest <= last_furthest:
        unchanged_count += 1
        if unchanged_count >= 2:
            print(f"No further events found after {max_days} days.")
            break
    else:
        unchanged_count = 0
        last_furthest = furthest
    max_days += step
    time.sleep(1)