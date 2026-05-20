CREATE TABLE IF NOT EXISTS "event_extracted_tags" (
    "id" BIGSERIAL PRIMARY KEY,
    "event_id" BIGINT NOT NULL,
    "tag_type" TEXT NOT NULL,
    "tag_value" TEXT NOT NULL,
    "source" TEXT NOT NULL DEFAULT 'description',
    "confidence" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "extractor" TEXT NOT NULL,
    "evidence" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "event_extracted_tags_event_id_fkey"
        FOREIGN KEY ("event_id") REFERENCES "events"("id")
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "event_extracted_tags_confidence_check"
        CHECK ("confidence" >= 0 AND "confidence" <= 1),
    CONSTRAINT "event_extracted_tags_type_check"
        CHECK ("tag_type" IN ('style', 'format', 'mood', 'theme', 'instrumentation', 'series'))
);

CREATE UNIQUE INDEX IF NOT EXISTS "event_extracted_tags_unique_idx"
ON "event_extracted_tags" (
    "event_id",
    "tag_type",
    lower("tag_value"),
    "source",
    "extractor"
);

CREATE INDEX IF NOT EXISTS "event_extracted_tags_event_idx"
ON "event_extracted_tags" ("event_id", "tag_type");

CREATE INDEX IF NOT EXISTS "event_extracted_tags_value_idx"
ON "event_extracted_tags" ("tag_type", lower("tag_value"));

CREATE TABLE IF NOT EXISTS "event_tag_extraction_runs" (
    "id" BIGSERIAL PRIMARY KEY,
    "event_id" BIGINT NOT NULL,
    "source" TEXT NOT NULL DEFAULT 'description',
    "extractor" TEXT NOT NULL,
    "text_hash" TEXT NOT NULL,
    "tag_count" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "event_tag_extraction_runs_event_id_fkey"
        FOREIGN KEY ("event_id") REFERENCES "events"("id")
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS "event_tag_extraction_runs_unique_idx"
ON "event_tag_extraction_runs" ("event_id", "source", "extractor");
