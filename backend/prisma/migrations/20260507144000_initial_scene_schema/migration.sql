CREATE TABLE IF NOT EXISTS "artists" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_artist_id" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "url_safe_name" TEXT,
    "biography" TEXT,
    "biography_url" TEXT,
    "biography_status" TEXT
);

CREATE TABLE IF NOT EXISTS "venues" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_venue_id" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "address" TEXT,
    "latitude" NUMERIC(65, 30),
    "longitude" NUMERIC(65, 30),
    "live" BOOLEAN,
    "area_name" TEXT,
    "country_code" TEXT
);

CREATE TABLE IF NOT EXISTS "genres" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_genre_id" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "slug" TEXT
);

CREATE TABLE IF NOT EXISTS "promoters" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_promoter_id" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "live" BOOLEAN,
    "has_ticket_access" BOOLEAN
);

CREATE TABLE IF NOT EXISTS "events" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_event_id" TEXT NOT NULL UNIQUE,
    "title" TEXT NOT NULL,
    "description_text" TEXT,
    "lineup_raw" TEXT,
    "content_url" TEXT,
    "event_date" TIMESTAMP(6) WITH TIME ZONE,
    "start_time" TIMESTAMP(6) WITH TIME ZONE,
    "end_time" TIMESTAMP(6) WITH TIME ZONE,
    "minimum_age" INTEGER,
    "cost_text" TEXT,
    "interested_count" INTEGER,
    "is_ticketed" BOOLEAN,
    "is_festival" BOOLEAN,
    "live" BOOLEAN,
    "has_secret_venue" BOOLEAN,
    "date_posted" TIMESTAMP(6) WITH TIME ZONE,
    "date_updated" TIMESTAMP(6) WITH TIME ZONE,
    "venue_id" BIGINT REFERENCES "venues"("id") ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS "event_artists" (
    "event_id" BIGINT NOT NULL REFERENCES "events"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    "artist_id" BIGINT NOT NULL REFERENCES "artists"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    PRIMARY KEY ("event_id", "artist_id")
);

CREATE TABLE IF NOT EXISTS "event_genres" (
    "event_id" BIGINT NOT NULL REFERENCES "events"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    "genre_id" BIGINT NOT NULL REFERENCES "genres"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    PRIMARY KEY ("event_id", "genre_id")
);

CREATE TABLE IF NOT EXISTS "event_images" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_image_id" TEXT UNIQUE,
    "event_id" BIGINT NOT NULL REFERENCES "events"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    "image_url" TEXT NOT NULL,
    "image_type" TEXT,
    "alt_text" TEXT
);

CREATE TABLE IF NOT EXISTS "event_promoters" (
    "event_id" BIGINT NOT NULL REFERENCES "events"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    "promoter_id" BIGINT NOT NULL REFERENCES "promoters"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    PRIMARY KEY ("event_id", "promoter_id")
);

CREATE TABLE IF NOT EXISTS "event_source_payloads" (
    "id" BIGSERIAL PRIMARY KEY,
    "event_id" BIGINT NOT NULL UNIQUE REFERENCES "events"("id") ON UPDATE CASCADE ON DELETE RESTRICT,
    "source_name" TEXT NOT NULL DEFAULT 'ra',
    "source_event_id" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "fetched_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
