import os
import json
import asyncio
from prisma import Prisma, Json
from dotenv import load_dotenv
from datetime import datetime, timezone
import time

load_dotenv()
EVENTS_FILE = os.getenv("EVENTS_JSON_PATH", "data/ra_berlin_past_events_2026.json")

db = Prisma()

# -------------------------
# Progress Bar
# -------------------------
def print_progress(current, total, start_time):
    percent = (current / total) * 100
    bar_length = 40
    done = int(bar_length * current / total)
    bar = "█" * done + "-" * (bar_length - done)

    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0

    print(
        f"\rImport Progress: |{bar}| {percent:.1f}% "
        f"({current}/{total}) | {speed:.1f} ev/s | ETA: {eta:.1f}s",
        end=""
    )


# -------------------------
# Datetime parser
# -------------------------
ERROR_COUNT = 0
MAX_ERRORS = 20
def parse_datetime(value: str | None, field_name: str = ""):
    global ERROR_COUNT

    if not value:
        return None

    value = value.strip()

    try:
        # ISO ( Z )
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        # ISO no timezone →  UTC
        if "T" in value:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)

        # just date (YYYY-MM-DD)
        if len(value) == 10:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)

        # fallback
        return datetime.fromisoformat(value)

    except Exception as e:
        if ERROR_COUNT < MAX_ERRORS:
            print(f"[WARN] Failed to parse datetime ({field_name}): '{value}' → {e}")
        ERROR_COUNT += 1
        return None


# -------------------------
# Safe getter
# -------------------------
def safe_get(d, *keys):
    for k in keys:
        if not d:
            return None
        d = d.get(k)
    return d


# -------------------------
# Clean payload
# -------------------------
def clean_payload(obj):
    if isinstance(obj, dict):
        return {k: clean_payload(v) for k, v in obj.items() if k != "__typename"}
    elif isinstance(obj, list):
        return [clean_payload(i) for i in obj]
    return obj


# -------------------------
# MAIN
# -------------------------
async def main():
    await db.connect()

    with open(EVENTS_FILE, "r") as f:
        events = json.load(f)

    total = len(events)
    start_time = time.time()

    # -------------------------
    # LOOP
    # -------------------------
    for i, e in enumerate(events, start=1):

        # -------------------------
        # 1. VENUE
        # -------------------------
        venue_id = None
        venue_data = e.get("venue")

        if venue_data:
            venue = await db.venue.upsert(
                where={"ra_venue_id": str(venue_data["id"])},
                data={
                    "create": {
                        "ra_venue_id": str(venue_data["id"]),
                        "name": venue_data.get("name"),
                        "content_url": venue_data.get("contentUrl"),
                        "address": venue_data.get("address"),
                        "latitude": safe_get(venue_data, "location", "latitude"),
                        "longitude": safe_get(venue_data, "location", "longitude"),
                        "live": venue_data.get("live"),
                        "area_name": safe_get(venue_data, "area", "name"),
                        "country_code": safe_get(venue_data, "area", "country", "urlCode"),
                    },
                    "update": {}
                }
            )
            venue_id = venue.id

        # -------------------------
        # 2. ARTISTS
        # -------------------------
        artist_ids = []
        for a in e.get("artists", []):
            artist = await db.artist.upsert(
                where={"ra_artist_id": str(a["id"])},
                data={
                    "create": {
                        "ra_artist_id": str(a["id"]),
                        "name": a.get("name"),
                        "content_url": a.get("contentUrl"),
                        "url_safe_name": a.get("urlSafeName"),
                    },
                    "update": {}
                }
            )
            artist_ids.append(artist.id)

        # -------------------------
        # 3. PROMOTERS
        # -------------------------
        promoter_ids = []
        for p in e.get("promoters", []):
            promoter = await db.promoter.upsert(
                where={"ra_promoter_id": str(p["id"])},
                data={
                    "create": {
                        "ra_promoter_id": str(p["id"]),
                        "name": p.get("name"),
                        "content_url": p.get("contentUrl"),
                        "live": p.get("live"),
                        "has_ticket_access": p.get("hasTicketAccess"),
                    },
                    "update": {}
                }
            )
            promoter_ids.append(promoter.id)

        # -------------------------
        # 4. GENRES
        # -------------------------
        genre_ids = []
        for g in e.get("genres", []):
            genre = await db.genre.upsert(
                where={"ra_genre_id": str(g["id"])},
                data={
                    "create": {
                        "ra_genre_id": str(g["id"]),
                        "name": g.get("name"),
                        "slug": g.get("slug"),
                    },
                    "update": {}
                }
            )
            genre_ids.append(genre.id)

        # -------------------------
        # 5. EVENT
        # -------------------------
        event = await db.event.upsert(
            where={"ra_event_id": str(e["id"])},
            data={
                "create": {
                    "ra_event_id": str(e["id"]),
                    "title": e.get("title"),
                    "description_text": e.get("content"),
                    "lineup_raw": e.get("lineup"),
                    "content_url": e.get("contentUrl"),
                    "event_date": parse_datetime(e.get("date"), "event_date"),
                    "start_time": parse_datetime(e.get("startTime"), "start_time"),
                    "end_time": parse_datetime(e.get("endTime"), "end_time"),
                    "minimum_age": e.get("minimumAge"),
                    "cost_text": e.get("cost"),
                    "interested_count": e.get("interestedCount"),
                    "is_ticketed": e.get("isTicketed"),
                    "is_festival": e.get("isFestival"),
                    "live": e.get("live"),
                    "has_secret_venue": e.get("hasSecretVenue"),
                    "date_posted": parse_datetime(e.get("datePosted"), "date_posted"),
                    "date_updated": parse_datetime(e.get("dateUpdated"), "date_updated"),
                    "venue_id": venue_id,
                },
                "update": {}
            }
        )

        # -------------------------
        # 6. JOIN TABLES
        # -------------------------
        for aid in artist_ids:
            await db.eventartist.upsert(
                where={
                    "event_id_artist_id": {
                        "event_id": event.id,
                        "artist_id": aid
                    }
                },
                data={
                    "create": {
                        "event_id": event.id,
                        "artist_id": aid
                    },
                    "update": {}
                }
            )

        for pid in promoter_ids:
            await db.eventpromoter.upsert(
                where={
                    "event_id_promoter_id": {
                        "event_id": event.id,
                        "promoter_id": pid
                    }
                },
                data={
                    "create": {
                        "event_id": event.id,
                        "promoter_id": pid
                    },
                    "update": {}
                }
            )

        for gid in genre_ids:
            await db.eventgenre.upsert(
                where={
                    "event_id_genre_id": {
                        "event_id": event.id,
                        "genre_id": gid
                    }
                },
                data={
                    "create": {
                        "event_id": event.id,
                        "genre_id": gid
                    },
                    "update": {}
                }
            )

        # -------------------------
        # 7. IMAGES
        # -------------------------
        for img in e.get("images", []):
            if img.get("id"):
                await db.eventimage.upsert(
                    where={"ra_image_id": str(img["id"])},
                    data={
                        "create": {
                            "ra_image_id": str(img["id"]),
                            "event_id": event.id,
                            "image_url": img.get("filename"),
                            "image_type": img.get("type"),
                            "alt_text": img.get("alt"),
                        },
                        "update": {}
                    }
                )
            else:
                # Fallback in case no ID is provided
                await db.eventimage.create(
                    data={
                        "event_id": event.id,
                        "image_url": img.get("filename"),
                        "image_type": img.get("type"),
                        "alt_text": img.get("alt"),
                    }
                )

        # -------------------------
        # 8. RAW PAYLOAD
        # -------------------------
        event_id_int = int(event.id)

        def clean_payload(obj):
            if isinstance(obj, dict):
                return {
                    k: clean_payload(v)
                    for k, v in obj.items()
                    if k != "__typename"
                }
            elif isinstance(obj, list):
                return [clean_payload(i) for i in obj]
            return obj

        safe_payload = clean_payload(e)

        await db.eventsourcepayload.upsert(
            where={"event_id": event_id_int},
            data={
                "create": {
                    "event_id": event_id_int,
                    "source_name": "ra",
                    "source_event_id": str(e["id"]),
                    "payload": Json(safe_payload),
                },
                "update": {
                    "payload": Json(safe_payload),
                }
            }
        )
        print_progress(i, total, start_time)

    await db.disconnect()

    total_time = time.time() - start_time
    total_minutes = total_time / 60
    if total_time < 60:
        print(f"\n\n✅ Import finished in {total_time:.2f} seconds")
    else:
        minutes = int(total_time // 60)
        seconds = int(total_time % 60)
        print(f"\n\n✅ Import finished in {minutes}m {seconds}s")


if __name__ == "__main__":
    asyncio.run(main())