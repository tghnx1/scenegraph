CREATE TABLE IF NOT EXISTS "artist_extracted_tags" (
    "id" BIGSERIAL PRIMARY KEY,
    "artist_id" BIGINT NOT NULL,
    "tag_type" TEXT NOT NULL,
    "tag_value" TEXT NOT NULL,
    "source" TEXT NOT NULL DEFAULT 'biography',
    "confidence" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "extractor" TEXT NOT NULL,
    "evidence" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "artist_extracted_tags_artist_id_fkey"
        FOREIGN KEY ("artist_id") REFERENCES "artists"("id")
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "artist_extracted_tags_confidence_check"
        CHECK ("confidence" >= 0 AND "confidence" <= 1),
    CONSTRAINT "artist_extracted_tags_type_check"
        CHECK ("tag_type" IN ('style', 'label', 'collective', 'role', 'residency', 'alias'))
);

CREATE UNIQUE INDEX IF NOT EXISTS "artist_extracted_tags_unique_idx"
ON "artist_extracted_tags" (
    "artist_id",
    "tag_type",
    lower("tag_value"),
    "source",
    "extractor"
);

CREATE INDEX IF NOT EXISTS "artist_extracted_tags_artist_idx"
ON "artist_extracted_tags" ("artist_id", "tag_type");

CREATE INDEX IF NOT EXISTS "artist_extracted_tags_value_idx"
ON "artist_extracted_tags" ("tag_type", lower("tag_value"));

CREATE TABLE IF NOT EXISTS "artist_tag_extraction_runs" (
    "id" BIGSERIAL PRIMARY KEY,
    "artist_id" BIGINT NOT NULL,
    "source" TEXT NOT NULL DEFAULT 'biography',
    "extractor" TEXT NOT NULL,
    "text_hash" TEXT NOT NULL,
    "tag_count" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "artist_tag_extraction_runs_artist_id_fkey"
        FOREIGN KEY ("artist_id") REFERENCES "artists"("id")
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS "artist_tag_extraction_runs_unique_idx"
ON "artist_tag_extraction_runs" ("artist_id", "source", "extractor");
