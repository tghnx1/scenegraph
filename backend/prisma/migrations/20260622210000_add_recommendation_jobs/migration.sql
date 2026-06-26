CREATE TABLE IF NOT EXISTS "recommendation_jobs" (
    "id" UUID PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "artist_id" BIGINT NOT NULL,
    "job_type" TEXT NOT NULL DEFAULT 'artist_promoters',
    "params_json" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "result_json" JSONB,
    "error_message" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "started_at" TIMESTAMPTZ(6),
    "finished_at" TIMESTAMPTZ(6),
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "recommendation_jobs_user_id_fkey"
        FOREIGN KEY ("user_id") REFERENCES "users"("id")
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "recommendation_jobs_artist_id_fkey"
        FOREIGN KEY ("artist_id") REFERENCES "artists"("id")
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "recommendation_jobs_type_check"
        CHECK ("job_type" = 'artist_promoters'),
    CONSTRAINT "recommendation_jobs_status_check"
        CHECK ("status" IN ('queued', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS "recommendation_jobs_claim_idx"
    ON "recommendation_jobs" ("status", "created_at");

CREATE INDEX IF NOT EXISTS "recommendation_jobs_user_created_idx"
    ON "recommendation_jobs" ("user_id", "created_at" DESC);
