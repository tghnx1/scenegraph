ALTER TABLE "recommendation_jobs"
    ADD COLUMN IF NOT EXISTS "params_hash" TEXT;

UPDATE "recommendation_jobs"
SET "params_hash" = md5("params_json"::text)
WHERE "params_hash" IS NULL;

ALTER TABLE "recommendation_jobs"
    ALTER COLUMN "params_hash" SET NOT NULL;
