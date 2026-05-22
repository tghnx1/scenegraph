CREATE TABLE IF NOT EXISTS "recommendation_feedback" (
    "id" BIGSERIAL PRIMARY KEY,
    "source_entity_type" TEXT NOT NULL,
    "source_entity_id" BIGINT NOT NULL,
    "candidate_entity_type" TEXT NOT NULL,
    "candidate_entity_id" BIGINT NOT NULL,
    "feedback" TEXT NOT NULL,
    "reason" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "recommendation_feedback_source_type_check"
        CHECK ("source_entity_type" IN ('artist', 'event')),
    CONSTRAINT "recommendation_feedback_candidate_type_check"
        CHECK ("candidate_entity_type" IN ('artist', 'event')),
    CONSTRAINT "recommendation_feedback_value_check"
        CHECK ("feedback" IN ('positive', 'negative', 'hidden'))
);

CREATE UNIQUE INDEX IF NOT EXISTS "recommendation_feedback_unique_idx"
ON "recommendation_feedback" (
    "source_entity_type",
    "source_entity_id",
    "candidate_entity_type",
    "candidate_entity_id"
);

CREATE INDEX IF NOT EXISTS "recommendation_feedback_source_idx"
ON "recommendation_feedback" ("source_entity_type", "source_entity_id");

CREATE INDEX IF NOT EXISTS "recommendation_feedback_candidate_idx"
ON "recommendation_feedback" ("candidate_entity_type", "candidate_entity_id");
