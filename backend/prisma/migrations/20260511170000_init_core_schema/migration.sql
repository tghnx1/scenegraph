CREATE TABLE IF NOT EXISTS "artists" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_artist_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "url_safe_name" TEXT,
    "biography" TEXT,
    "biography_url" TEXT,
    "biography_status" TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS "artists_ra_artist_id_key"
ON "artists" ("ra_artist_id");

CREATE TABLE IF NOT EXISTS "venues" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_venue_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "address" TEXT,
    "latitude" DECIMAL(65, 30),
    "longitude" DECIMAL(65, 30),
    "live" BOOLEAN,
    "area_name" TEXT,
    "country_code" TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS "venues_ra_venue_id_key"
ON "venues" ("ra_venue_id");

CREATE TABLE IF NOT EXISTS "genres" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_genre_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS "genres_ra_genre_id_key"
ON "genres" ("ra_genre_id");

CREATE TABLE IF NOT EXISTS "promoters" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_promoter_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "live" BOOLEAN,
    "has_ticket_access" BOOLEAN
);

CREATE UNIQUE INDEX IF NOT EXISTS "promoters_ra_promoter_id_key"
ON "promoters" ("ra_promoter_id");

CREATE TABLE IF NOT EXISTS "events" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_event_id" TEXT NOT NULL,
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
    "venue_id" BIGINT,
    CONSTRAINT "events_venue_id_fkey"
        FOREIGN KEY ("venue_id") REFERENCES "venues"("id")
        ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS "events_ra_event_id_key"
ON "events" ("ra_event_id");

CREATE TABLE IF NOT EXISTS "event_artists" (
    "event_id" BIGINT NOT NULL,
    "artist_id" BIGINT NOT NULL,
    CONSTRAINT "event_artists_pkey" PRIMARY KEY ("event_id", "artist_id"),
    CONSTRAINT "event_artists_event_id_fkey"
        FOREIGN KEY ("event_id") REFERENCES "events"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "event_artists_artist_id_fkey"
        FOREIGN KEY ("artist_id") REFERENCES "artists"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_genres" (
    "event_id" BIGINT NOT NULL,
    "genre_id" BIGINT NOT NULL,
    CONSTRAINT "event_genres_pkey" PRIMARY KEY ("event_id", "genre_id"),
    CONSTRAINT "event_genres_event_id_fkey"
        FOREIGN KEY ("event_id") REFERENCES "events"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "event_genres_genre_id_fkey"
        FOREIGN KEY ("genre_id") REFERENCES "genres"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_images" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_image_id" TEXT,
    "event_id" BIGINT NOT NULL,
    "image_url" TEXT NOT NULL,
    "image_type" TEXT,
    "alt_text" TEXT,
    CONSTRAINT "event_images_event_id_fkey"
        FOREIGN KEY ("event_id") REFERENCES "events"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS "event_images_ra_image_id_key"
ON "event_images" ("ra_image_id");

CREATE TABLE IF NOT EXISTS "event_promoters" (
    "event_id" BIGINT NOT NULL,
    "promoter_id" BIGINT NOT NULL,
    CONSTRAINT "event_promoters_pkey" PRIMARY KEY ("event_id", "promoter_id"),
    CONSTRAINT "event_promoters_event_id_fkey"
        FOREIGN KEY ("event_id") REFERENCES "events"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "event_promoters_promoter_id_fkey"
        FOREIGN KEY ("promoter_id") REFERENCES "promoters"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_source_payloads" (
    "id" BIGSERIAL PRIMARY KEY,
    "event_id" BIGINT NOT NULL,
    "source_name" TEXT NOT NULL DEFAULT 'ra',
    "source_event_id" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "fetched_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "event_source_payloads_event_id_fkey"
        FOREIGN KEY ("event_id") REFERENCES "events"("id")
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS "event_source_payloads_event_id_key"
ON "event_source_payloads" ("event_id");
