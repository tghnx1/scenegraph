CREATE TABLE IF NOT EXISTS "entity_embeddings" (
    "id" BIGSERIAL PRIMARY KEY,
    "entity_type" TEXT NOT NULL CHECK ("entity_type" IN ('event', 'artist')),
    "entity_id" BIGINT NOT NULL,
    "model" TEXT NOT NULL,
    "dimensions" INTEGER NOT NULL CHECK ("dimensions" > 0),
    "text_hash" TEXT NOT NULL,
    "text_profile" TEXT NOT NULL,
    "embedding" DOUBLE PRECISION[] NOT NULL,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE ("entity_type", "entity_id", "model", "dimensions")
);

CREATE INDEX IF NOT EXISTS "entity_embeddings_lookup_idx"
ON "entity_embeddings" ("entity_type", "model", "dimensions");
