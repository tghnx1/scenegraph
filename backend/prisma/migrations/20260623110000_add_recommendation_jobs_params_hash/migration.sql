ALTER TABLE "recommendation_jobs"
    ADD COLUMN IF NOT EXISTS "params_hash" TEXT;

UPDATE "recommendation_jobs"
SET "params_hash" = md5("params_json"::text)
WHERE "params_hash" IS NULL;

WITH ranked_jobs AS (
    SELECT
        ctid,
        row_number() OVER (
            PARTITION BY "user_id", "artist_id", "job_type", "params_hash"
            ORDER BY "created_at" DESC, "finished_at" DESC NULLS LAST, "updated_at" DESC, "id" DESC
        ) AS row_number
    FROM "recommendation_jobs"
)
DELETE FROM "recommendation_jobs"
WHERE ctid IN (
    SELECT ctid
    FROM ranked_jobs
    WHERE row_number > 1
);

ALTER TABLE "recommendation_jobs"
    ALTER COLUMN "params_hash" SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "recommendation_jobs_user_artist_type_params_hash_key"
    ON "recommendation_jobs" ("user_id", "artist_id", "job_type", "params_hash");
