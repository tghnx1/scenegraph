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
    "latitude" DECIMAL(65, 30),
    "longitude" DECIMAL(65, 30),
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
    "event_date" TIMESTAMPTZ(6),
    "start_time" TIMESTAMPTZ(6),
    "end_time" TIMESTAMPTZ(6),
    "minimum_age" INTEGER,
    "cost_text" TEXT,
    "interested_count" INTEGER,
    "is_ticketed" BOOLEAN,
    "is_festival" BOOLEAN,
    "live" BOOLEAN,
    "has_secret_venue" BOOLEAN,
    "date_posted" TIMESTAMPTZ(6),
    "date_updated" TIMESTAMPTZ(6),
    "venue_id" BIGINT,
    CONSTRAINT "events_venue_id_fkey"
        FOREIGN KEY ("venue_id")
        REFERENCES "venues"("id")
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_artists" (
    "event_id" BIGINT NOT NULL,
    "artist_id" BIGINT NOT NULL,
    CONSTRAINT "event_artists_pkey" PRIMARY KEY ("event_id", "artist_id"),
    CONSTRAINT "event_artists_event_id_fkey"
        FOREIGN KEY ("event_id")
        REFERENCES "events"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT "event_artists_artist_id_fkey"
        FOREIGN KEY ("artist_id")
        REFERENCES "artists"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_genres" (
    "event_id" BIGINT NOT NULL,
    "genre_id" BIGINT NOT NULL,
    CONSTRAINT "event_genres_pkey" PRIMARY KEY ("event_id", "genre_id"),
    CONSTRAINT "event_genres_event_id_fkey"
        FOREIGN KEY ("event_id")
        REFERENCES "events"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT "event_genres_genre_id_fkey"
        FOREIGN KEY ("genre_id")
        REFERENCES "genres"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_images" (
    "id" BIGSERIAL PRIMARY KEY,
    "ra_image_id" TEXT UNIQUE,
    "event_id" BIGINT NOT NULL,
    "image_url" TEXT NOT NULL,
    "image_type" TEXT,
    "alt_text" TEXT,
    CONSTRAINT "event_images_event_id_fkey"
        FOREIGN KEY ("event_id")
        REFERENCES "events"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_promoters" (
    "event_id" BIGINT NOT NULL,
    "promoter_id" BIGINT NOT NULL,
    CONSTRAINT "event_promoters_pkey" PRIMARY KEY ("event_id", "promoter_id"),
    CONSTRAINT "event_promoters_event_id_fkey"
        FOREIGN KEY ("event_id")
        REFERENCES "events"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT "event_promoters_promoter_id_fkey"
        FOREIGN KEY ("promoter_id")
        REFERENCES "promoters"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS "event_source_payloads" (
    "id" BIGSERIAL PRIMARY KEY,
    "event_id" BIGINT NOT NULL UNIQUE,
    "source_name" TEXT NOT NULL DEFAULT 'ra',
    "source_event_id" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "fetched_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "event_source_payloads_event_id_fkey"
        FOREIGN KEY ("event_id")
        REFERENCES "events"("id")
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS "events_venue_id_idx" ON "events" ("venue_id");
CREATE INDEX IF NOT EXISTS "event_artists_artist_id_idx" ON "event_artists" ("artist_id");
CREATE INDEX IF NOT EXISTS "event_genres_genre_id_idx" ON "event_genres" ("genre_id");
CREATE INDEX IF NOT EXISTS "event_images_event_id_idx" ON "event_images" ("event_id");
CREATE INDEX IF NOT EXISTS "event_promoters_promoter_id_idx" ON "event_promoters" ("promoter_id");
