DROP TABLE IF EXISTS "recommendation_feedback";

CREATE TABLE "recommendation_feedback" (
    "id" BIGSERIAL PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "source_entity_type" TEXT NOT NULL,
    "source_entity_id" BIGINT NOT NULL,
    "candidate_entity_type" TEXT NOT NULL,
    "candidate_entity_id" BIGINT NOT NULL,
    "feedback" TEXT NOT NULL,
    "reason" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "recommendation_feedback_source_type_check"
        CHECK ("source_entity_type" = 'artist'),
    CONSTRAINT "recommendation_feedback_candidate_type_check"
        CHECK ("candidate_entity_type" = 'promoter'),
    CONSTRAINT "recommendation_feedback_value_check"
        CHECK ("feedback" IN ('positive', 'negative')),
    CONSTRAINT "recommendation_feedback_source_artist_fkey"
        FOREIGN KEY ("source_entity_id") REFERENCES "artists"("id") ON DELETE CASCADE,
    CONSTRAINT "recommendation_feedback_candidate_promoter_fkey"
        FOREIGN KEY ("candidate_entity_id") REFERENCES "promoters"("id") ON DELETE CASCADE,
    CONSTRAINT "recommendation_feedback_unique"
        UNIQUE (
            "user_id",
            "source_entity_type",
            "source_entity_id",
            "candidate_entity_type",
            "candidate_entity_id"
        )
);

CREATE INDEX "recommendation_feedback_user_idx"
    ON "recommendation_feedback" ("user_id");

CREATE INDEX "recommendation_feedback_user_source_idx"
    ON "recommendation_feedback" ("user_id", "source_entity_type", "source_entity_id");

CREATE INDEX "recommendation_feedback_user_candidate_idx"
    ON "recommendation_feedback" ("user_id", "candidate_entity_type", "candidate_entity_id");
