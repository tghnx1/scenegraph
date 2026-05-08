# Berlin Scene Graph — DB Schema And JSON Import Spec

This file is the concrete instruction set for the teammate who will import the
JSON data into Postgres.

It is intentionally strict:
- only model fields that already exist in our JSON files
- keep normalized relational tables for app data
- keep raw source JSON separately for fallback / future recovery
- do not invent tables or columns for data we do not currently have

---

## 1. Source Files We Have

Primary source:
- `/Volumes/Untitled/42/scenegraph-data/json/ra_berlin_past_events.json`

Enrichment sources:
- `/Volumes/Untitled/42/scenegraph-data/json/artists.json`
- `/Volumes/Untitled/42/scenegraph-data/json/artist_biographies.json`

Observed shape:
- events: array of event objects
- artists.json: array with `id`, `url`
- artist_biographies.json: array with fields including:
  - `id`
  - `artist_name`
  - `biography`
  - `biography_url`
  - `status`
  - `http_status`
  - `final_url`

Important notes from the real JSON:
- event JSON already contains nested:
  - `venue`
  - `artists`
  - `promoters`
  - `genres`
  - `images`
- event JSON also contains:
  - `content` -> event description
  - `lineup` -> raw lineup text / markup, useful when `artists[]` is incomplete

---

## 2. Final Tables We Need Now

### Core relational tables

1. `events`
2. `venues`
3. `artists`
4. `promoters`
5. `genres`

### Join tables

6. `event_artists`
7. `event_promoters`
8. `event_genres`

### Optional but recommended now because the data already exists

9. `event_images`

### Raw source archive table

10. `event_source_payloads`

This is preferred over putting raw JSON directly into `events`, because it
keeps the main app table clean while preserving the full original source.

---

## 3. Tables We Do NOT Need Now

Do not create these yet:
- `admins`
- `tickets`
- `player_links`
- `set_times`
- `child_events`
- `areas`
- `countries`
- downloaded image/blob storage
- venue descriptions
- promoter descriptions

Reason:
- either not needed for current app logic
- or not clearly present as useful first-class data in our current JSON
- or better preserved in raw source payload only

---

## 4. Final Column Spec

## `events`

- `id` bigserial primary key
- `ra_event_id` text unique not null
- `title` text not null
- `description_text` text
- `lineup_raw` text
- `content_url` text
- `event_date` timestamptz
- `start_time` timestamptz
- `end_time` timestamptz
- `minimum_age` integer
- `cost_text` text
- `interested_count` integer
- `is_ticketed` boolean
- `is_festival` boolean
- `live` boolean
- `has_secret_venue` boolean
- `date_posted` timestamptz
- `date_updated` timestamptz
- `venue_id` bigint references `venues(id)`

### Source mapping

- `ra_event_id` <- `event.id`
- `title` <- `event.title`
- `description_text` <- `event.content`
- `lineup_raw` <- `event.lineup`
- `content_url` <- `event.contentUrl`
- `event_date` <- `event.date`
- `start_time` <- `event.startTime`
- `end_time` <- `event.endTime`
- `minimum_age` <- `event.minimumAge`
- `cost_text` <- `event.cost`
- `interested_count` <- `event.interestedCount`
- `is_ticketed` <- `event.isTicketed`
- `is_festival` <- `event.isFestival`
- `live` <- `event.live`
- `has_secret_venue` <- `event.hasSecretVenue`
- `date_posted` <- `event.datePosted`
- `date_updated` <- `event.dateUpdated`
- `venue_id` <- resolved from nested `event.venue.id`

---

## `venues`

- `id` bigserial primary key
- `ra_venue_id` text unique not null
- `name` text not null
- `content_url` text
- `address` text
- `latitude` numeric
- `longitude` numeric
- `live` boolean
- `area_name` text
- `country_code` text

### Source mapping

- `ra_venue_id` <- `event.venue.id`
- `name` <- `event.venue.name`
- `content_url` <- `event.venue.contentUrl`
- `address` <- `event.venue.address`
- `latitude` <- `event.venue.location.latitude`
- `longitude` <- `event.venue.location.longitude`
- `live` <- `event.venue.live`
- `area_name` <- `event.venue.area.name`
- `country_code` <- `event.venue.area.country.urlCode`

---

## `artists`

- `id` bigserial primary key
- `ra_artist_id` text unique not null
- `name` text not null
- `content_url` text
- `url_safe_name` text
- `biography` text
- `biography_url` text
- `biography_status` text

### Source mapping

Basic artist identity comes from event JSON:
- `ra_artist_id` <- `event.artists[].id`
- `name` <- `event.artists[].name`
- `content_url` <- `event.artists[].contentUrl`
- `url_safe_name` <- `event.artists[].urlSafeName`

Biography enrichment comes from `artist_biographies.json`:
- `biography` <- `biography.biography`
- `biography_url` <- `biography.biography_url` only when `biography.status = 'ok'`
- `biography_status` <- `biography.status`

Important:
- store `biography_url` only when biography status is `ok`
- store `biography_status` so we know whether biography fetch was `ok`,
  `not_found`, or another state

Do not require biography to exist in order to create the artist row.

---

## `promoters`

- `id` bigserial primary key
- `ra_promoter_id` text unique not null
- `name` text not null
- `content_url` text
- `live` boolean
- `has_ticket_access` boolean

### Source mapping

- `ra_promoter_id` <- `event.promoters[].id`
- `name` <- `event.promoters[].name`
- `content_url` <- `event.promoters[].contentUrl`
- `live` <- `event.promoters[].live`
- `has_ticket_access` <- `event.promoters[].hasTicketAccess`

---

## `genres`

- `id` bigserial primary key
- `ra_genre_id` text unique not null
- `name` text not null
- `slug` text

### Source mapping

- `ra_genre_id` <- `event.genres[].id`
- `name` <- `event.genres[].name`
- `slug` <- `event.genres[].slug`

Important:
- keep these as coarse RA tags only
- do not treat them as the final fine-grained style system
- richer style understanding should come later from artist biographies and text analysis

---

## `event_artists`

- `event_id` bigint references `events(id)` not null
- `artist_id` bigint references `artists(id)` not null
- primary key (`event_id`, `artist_id`)

Source:
- from `event.artists[]`

Important:
- this table is only for matched structured artists already present in the JSON
- raw lineup text is still stored separately in `events.lineup_raw`
- later we may parse additional plain-text artists from lineup text if needed

---

## `event_promoters`

- `event_id` bigint references `events(id)` not null
- `promoter_id` bigint references `promoters(id)` not null
- primary key (`event_id`, `promoter_id`)

Source:
- from `event.promoters[]`

---

## `event_genres`

- `event_id` bigint references `events(id)` not null
- `genre_id` bigint references `genres(id)` not null
- primary key (`event_id`, `genre_id`)

Source:
- from `event.genres[]`

---

## `event_images`

- `id` bigserial primary key
- `ra_image_id` text unique
- `event_id` bigint references `events(id)` not null
- `image_url` text not null
- `image_type` text
- `alt_text` text

### Source mapping

- `ra_image_id` <- `event.images[].id`
- `image_url` <- `event.images[].filename`
- `image_type` <- `event.images[].type`
- `alt_text` <- `event.images[].alt`

Important:
- store image URLs / metadata only
- do not download/store actual binary image data in Postgres

---

## `event_source_payloads`

- `id` bigserial primary key
- `event_id` bigint references `events(id)` unique not null
- `source_name` text not null
- `source_event_id` text not null
- `payload` jsonb not null
- `fetched_at` timestamptz default now()

### Source mapping

- `source_name` <- constant `'ra'`
- `source_event_id` <- raw `event.id`
- `payload` <- full original event JSON object

Purpose:
- preserve all source fields we are not modeling yet
- make it easy to recover later fields without rescanning files
- keep `events` table clean while still retaining source provenance

---

## 5. Import Rules

These rules matter more than the exact implementation language.

### Rule 1 — import events first as the master source

The whole model is events-first:
- events are the source of truth
- venues, artists, promoters, genres are derived from events

### Rule 2 — upsert all normalized entities

Use RA IDs as natural unique keys:
- events by `ra_event_id`
- venues by `ra_venue_id`
- artists by `ra_artist_id`
- promoters by `ra_promoter_id`
- genres by `ra_genre_id`

Do not create duplicate rows when an entity appears in multiple events.

### Rule 3 — preserve lineup raw text

Always store `events.lineup_raw`, even if `event.artists[]` is already present.

Reason:
- some artists may be missing from structured `artists[]`
- the docs and scraper notes explicitly say lineup text is needed for recovery

### Rule 4 — preserve full raw payload

For every imported event:
- insert/update normalized `events` row
- then insert/update one `event_source_payloads` row with the full original JSON

### Rule 5 — biographies are enrichment, not a blocker

Do not block artist import on biography availability.

Process:
- create/update artists from event JSON first
- then enrich artists from `artist_biographies.json`

If biography is missing:
- leave `biography` null
- store `biography_url` only when status is `ok`
- still store `biography_status`

### Rule 6 — genres are coarse tags only

Import event genres because they exist and cost little to keep.

But do not build the final style system around them.

### Rule 7 — do not invent missing fields

If the field is not in current JSON:
- do not create it now just because it sounds useful

Examples to avoid for now:
- promoter descriptions
- venue descriptions
- admin tables

---

## 6. Recommended Import Order

For one import pass over `ra_berlin_past_events.json`:

1. read one event object
2. upsert venue
3. upsert artists from `event.artists[]`
4. upsert promoters from `event.promoters[]`
5. upsert genres from `event.genres[]`
6. upsert event with resolved `venue_id`
7. upsert join rows:
   - `event_artists`
   - `event_promoters`
   - `event_genres`
8. upsert `event_images`
9. upsert `event_source_payloads`

After the event import is complete:

10. load `artist_biographies.json`
11. update matching `artists` rows by `ra_artist_id`

---

## 7. Exact Guidance For The Teammate Implementing Import

Use this as the implementation brief.

### Instruction

Build a Python import script that reads:
- `/Volumes/Untitled/42/scenegraph-data/json/ra_berlin_past_events.json`
- `/Volumes/Untitled/42/scenegraph-data/json/artist_biographies.json`

and imports the data into Postgres using the schema defined in this file.

### Hard requirements

- Use the real JSON shape only.
- Do not invent columns for fields not present in the current JSON.
- Use RA IDs as unique import keys.
- Use upsert behavior so repeated imports are safe.
- Preserve `events.lineup_raw`.
- Preserve `events.description_text`.
- Preserve the full original event JSON in `event_source_payloads.payload`.
- Preserve `artists.biography`, `artists.biography_url`, and `artists.biography_status`.
- Import genres as coarse metadata only.
- Do not create admin-related tables.
- Do not store image binaries, only image URLs and metadata.

### Safety requirements

- Re-running the import must not create duplicates.
- Missing nested arrays must not crash the import.
- Missing biography data must not block artist creation.
- If a referenced nested object is absent, set the relational field to null when appropriate.
- Log counts for:
  - imported events
  - imported venues
  - imported artists
  - imported promoters
  - imported genres
  - imported event_images
  - imported biography updates

### Output requirements

Deliver:
- schema SQL or migration files
- one reproducible Python import script
- clear environment instructions
- a short verification checklist with sample SQL queries

---

## 8. AI-Style Prompt Version

If delegating this work to an AI or another teammate, use the prompt below.

### Prompt

Implement the Postgres schema and Python import pipeline for Berlin Scene Graph using the specification in `documentation/db_schema_and_json_import_spec.md`.

Requirements:
- Read event data from `/Volumes/Untitled/42/scenegraph-data/json/ra_berlin_past_events.json`.
- Read biography enrichment from `/Volumes/Untitled/42/scenegraph-data/json/artist_biographies.json`.
- Create only the tables defined in the spec:
  - `events`
  - `venues`
  - `artists`
  - `promoters`
  - `genres`
  - `event_artists`
  - `event_promoters`
  - `event_genres`
  - `event_images`
  - `event_source_payloads`
- Use RA IDs as unique keys.
- Make imports idempotent with upserts.
- Preserve:
  - event description in `events.description_text`
  - raw lineup in `events.lineup_raw`
  - raw full event JSON in `event_source_payloads.payload`
  - artist biography fields in `artists`
- Do not create fields or tables for data not currently present in the JSON.
- Do not create admin tables.
- Do not store binary image data.
- Keep genres as coarse metadata only.

Implementation expectations:
- Python import script only.
- Safe repeated imports.
- Clear logging and counts.
- Provide sample verification SQL queries after implementation.

Success criteria:
- Import runs end-to-end without duplicates.
- Structured entities and join tables are filled correctly.
- Raw payload archive is preserved.
- Artists are enriched with biography fields when available.

---

## 9. Short Final Decision Summary

We are choosing:
- normalized relational tables for core scene entities
- a separate raw payload archive table
- event-first ingestion
- artist biography enrichment
- raw lineup preservation

We are explicitly not choosing:
- Prisma runtime integration
- admin modeling
- over-modeling every nested RA field
- binary asset storage in Postgres
