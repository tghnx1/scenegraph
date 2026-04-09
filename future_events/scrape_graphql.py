#starting source: https://stackoverflow.com/a/76282850
import requests
import json
import csv
import time
import random
import sys
from datetime import datetime, timedelta

# --- CONFIGURATION ---
AREA_ID = 34  # Berlin
DAYS_FORWARD = 375 # How far into the future to look
OUTPUT_JSON = "ra_future_events.json"
OUTPUT_CSV = "ra_future_events.csv"

# A list of modern User-Agents to rotate through
USER_AGENTS = [
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

def get_future_dates(days):
	"""Calculates the date range for the GraphQL filter."""
	today = datetime.now()
	start_date = today.strftime("%Y-%m-%d")
	end_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")
	return start_date, end_date

# GraphQL query to fetch detailed event information
GET_EVENT_QUERY = """
query GET_EVENT($id: ID!) {
    event(id: $id) {
        id
        title
        content
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

def get_event_details(session, headers, event_id):
	"""Fetch detailed information for a single event."""
	url = "https://ra.co/graphql"
	variables = {"id": event_id}

	try:
		time.sleep(random.uniform(0.5, 1.5))  # Rate limiting
		response = session.post(url, json={'query': GET_EVENT_QUERY, 'variables': variables}, headers=headers, timeout=15)
		response.raise_for_status()
		return response.json().get('data', {}).get('event', {})
	except Exception as e:
		print(f"Error fetching event {event_id}: {e}")
		return {}

def scrape_ra():
	start_date, end_date = get_future_dates(DAYS_FORWARD)
	url = "https://ra.co/graphql"

	# Use a Session to persist cookies (looks more like a real user)
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
		  id
		  event {
			id
		  }
		}
		totalResults
	  }
	}
	"""

	print(f"Starting scrape for Berlin future events ({start_date} to {end_date})...")

	# Random initial delay to not look like a scheduled task
	time.sleep(random.uniform(1.0, 3.0))

	try:
		# Fetch all event IDs with pagination
		all_event_ids = []
		page = 1
		page_size = 50  # Fetch 50 events per page

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

			# Check for Rate Limiting (429)
			if response.status_code == 429:
				print("429 Error: RA has rate-limited this IP. Stopping to avoid a ban.")
				sys.exit()

			response.raise_for_status()
			data = response.json()

			# Debug: Print response on first page
			if page == 1:
				print(f"API Response (first page): {json.dumps(data, indent=2)[:500]}...")

			# Check for GraphQL errors
			if 'errors' in data:
				print(f"GraphQL Error: {data['errors']}")
				return

			listings = data.get('data', {}).get('eventListings', {}).get('data', [])
			total_count = data.get('data', {}).get('eventListings', {}).get('totalResults', 0)

			if not listings:
				break

			for item in listings:
				event_id = item.get('event', {}).get('id')
				if event_id:
					all_event_ids.append(event_id)

			print(f"Fetched page {page}: {len(listings)} events (Total so far: {len(all_event_ids)}/{total_count})")

			# Stop if we've fetched all pages
			if len(listings) < page_size:
				break

			page += 1
			time.sleep(random.uniform(0.5, 1.0))  # Rate limiting between pages

		if not all_event_ids:
			print("No events found. You might be blocked or the range is empty.")
			return

		# Fetch detailed info for each event
		all_events_data = []
		print(f"\nFetching detailed info for {len(all_event_ids)} events...")
		for idx, event_id in enumerate(all_event_ids, 1):
			detailed_event = get_event_details(session, headers, event_id)
			if detailed_event:
				all_events_data.append(detailed_event)
			if idx % 10 == 0:
				print(f"Progress: {idx}/{len(all_event_ids)}")

		# --- SAVE TO JSON ---
		with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
			json.dump(all_events_data, f, indent=4, ensure_ascii=False)

		# --- SAVE TO CSV ---
		with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
			writer = csv.writer(f)
			writer.writerow(["Date", "Event", "Venue", "Interested Count", "Link", "Start Time", "End Time", "Cost", "Artists", "Promoters"])
			for detailed_event in all_events_data:
				artists_list = ', '.join([a.get('name', '') for a in detailed_event.get('artists', [])])
				promoters_list = ', '.join([p.get('name', '') for p in detailed_event.get('promoters', [])])

				writer.writerow([
					detailed_event.get('date', '')[:10],
					detailed_event.get('title', 'N/A'),
					detailed_event.get('venue', {}).get('name', 'N/A'),
					detailed_event.get('interestedCount', 0),
					f"https://ra.co{detailed_event.get('contentUrl', '')}",
					detailed_event.get('startTime', ''),
					detailed_event.get('endTime', ''),
					detailed_event.get('cost', 'N/A'),
					artists_list,
					promoters_list
				])

		print(f"\nScraped {len(all_events_data)} events total")
		print(f"JSON saved to: {OUTPUT_JSON}")
		print(f"CSV saved to: {OUTPUT_CSV}")

	except requests.exceptions.RequestException as e:
		print(f"Network error: {e}")
	except Exception as e:
		print(f"Error: {e}")

if __name__ == "__main__":
	scrape_ra()