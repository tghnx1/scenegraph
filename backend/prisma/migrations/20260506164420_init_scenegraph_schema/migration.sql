-- CreateTable
CREATE TABLE "events" (
    "id" BIGSERIAL NOT NULL,
    "ra_event_id" TEXT NOT NULL,
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

    CONSTRAINT "events_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "venues" (
    "id" BIGSERIAL NOT NULL,
    "ra_venue_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "address" TEXT,
    "latitude" DECIMAL(65,30),
    "longitude" DECIMAL(65,30),
    "live" BOOLEAN,
    "area_name" TEXT,
    "country_code" TEXT,

    CONSTRAINT "venues_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "artists" (
    "id" BIGSERIAL NOT NULL,
    "ra_artist_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "url_safe_name" TEXT,
    "biography" TEXT,
    "biography_url" TEXT,
    "biography_status" TEXT,

    CONSTRAINT "artists_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "promoters" (
    "id" BIGSERIAL NOT NULL,
    "ra_promoter_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "content_url" TEXT,
    "live" BOOLEAN,
    "has_ticket_access" BOOLEAN,

    CONSTRAINT "promoters_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "genres" (
    "id" BIGSERIAL NOT NULL,
    "ra_genre_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT,

    CONSTRAINT "genres_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "event_artists" (
    "event_id" BIGINT NOT NULL,
    "artist_id" BIGINT NOT NULL,

    CONSTRAINT "event_artists_pkey" PRIMARY KEY ("event_id","artist_id")
);

-- CreateTable
CREATE TABLE "event_promoters" (
    "event_id" BIGINT NOT NULL,
    "promoter_id" BIGINT NOT NULL,

    CONSTRAINT "event_promoters_pkey" PRIMARY KEY ("event_id","promoter_id")
);

-- CreateTable
CREATE TABLE "event_genres" (
    "event_id" BIGINT NOT NULL,
    "genre_id" BIGINT NOT NULL,

    CONSTRAINT "event_genres_pkey" PRIMARY KEY ("event_id","genre_id")
);

-- CreateTable
CREATE TABLE "event_images" (
    "id" BIGSERIAL NOT NULL,
    "ra_image_id" TEXT,
    "event_id" BIGINT NOT NULL,
    "image_url" TEXT NOT NULL,
    "image_type" TEXT,
    "alt_text" TEXT,

    CONSTRAINT "event_images_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "event_source_payloads" (
    "id" BIGSERIAL NOT NULL,
    "event_id" BIGINT NOT NULL,
    "source_name" TEXT NOT NULL DEFAULT 'ra',
    "source_event_id" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "fetched_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "event_source_payloads_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "events_ra_event_id_key" ON "events"("ra_event_id");

-- CreateIndex
CREATE UNIQUE INDEX "venues_ra_venue_id_key" ON "venues"("ra_venue_id");

-- CreateIndex
CREATE UNIQUE INDEX "artists_ra_artist_id_key" ON "artists"("ra_artist_id");

-- CreateIndex
CREATE UNIQUE INDEX "promoters_ra_promoter_id_key" ON "promoters"("ra_promoter_id");

-- CreateIndex
CREATE UNIQUE INDEX "genres_ra_genre_id_key" ON "genres"("ra_genre_id");

-- CreateIndex
CREATE UNIQUE INDEX "event_images_ra_image_id_key" ON "event_images"("ra_image_id");

-- CreateIndex
CREATE UNIQUE INDEX "event_source_payloads_event_id_key" ON "event_source_payloads"("event_id");

-- AddForeignKey
ALTER TABLE "events" ADD CONSTRAINT "events_venue_id_fkey" FOREIGN KEY ("venue_id") REFERENCES "venues"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_artists" ADD CONSTRAINT "event_artists_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "events"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_artists" ADD CONSTRAINT "event_artists_artist_id_fkey" FOREIGN KEY ("artist_id") REFERENCES "artists"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_promoters" ADD CONSTRAINT "event_promoters_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "events"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_promoters" ADD CONSTRAINT "event_promoters_promoter_id_fkey" FOREIGN KEY ("promoter_id") REFERENCES "promoters"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_genres" ADD CONSTRAINT "event_genres_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "events"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_genres" ADD CONSTRAINT "event_genres_genre_id_fkey" FOREIGN KEY ("genre_id") REFERENCES "genres"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_images" ADD CONSTRAINT "event_images_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "events"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "event_source_payloads" ADD CONSTRAINT "event_source_payloads_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "events"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
