import urllib.request
import json
import sys

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
    blurb
    minAge
    cost
    ticketUrl
    isTicketsSoldOut
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
    }
    promoters {
      id
      name
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
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://ra.co/events/{event_id}",
        "Origin": "https://ra.co"
    }

    req = urllib.request.Request(URL, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body)
    except Exception as e:
        print(f"Error fetching event: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    # You can change this ID to test other events
    test_event_id = "2356707"
    print(f"Fetching event {test_event_id} via GraphQL...\n")

    result = fetch_single_event(test_event_id)
    if result:
        out_file = f"single_event_{test_event_id}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved event data to {out_file}")
    else:
        print("Failed to fetch event data.")
