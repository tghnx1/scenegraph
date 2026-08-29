CREATE TABLE IF NOT EXISTS "ingestion_quarantine" (
    "id" BIGSERIAL PRIMARY KEY,
    "entity_type" TEXT NOT NULL,
    "entity_id" BIGINT NOT NULL,
    "stage" TEXT NOT NULL,
    "error_type" TEXT NOT NULL,
    "error_message" TEXT,
    "attempt_count" INTEGER NOT NULL DEFAULT 1,
    "first_seen_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_seen_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolved_at" TIMESTAMP(6) WITH TIME ZONE,
    "metadata" JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS "ingestion_quarantine_entity_idx"
ON "ingestion_quarantine" ("entity_type", "entity_id", "stage");

CREATE UNIQUE INDEX IF NOT EXISTS "ingestion_quarantine_unresolved_unique_idx"
ON "ingestion_quarantine" ("entity_type", "entity_id", "stage")
WHERE "resolved_at" IS NULL;
