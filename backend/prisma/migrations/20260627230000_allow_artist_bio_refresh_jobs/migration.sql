ALTER TABLE "recommendation_jobs"
    DROP CONSTRAINT IF EXISTS "recommendation_jobs_type_check";

ALTER TABLE "recommendation_jobs"
    ADD CONSTRAINT "recommendation_jobs_type_check"
    CHECK ("job_type" IN ('artist_promoters', 'artist_bio_refresh'));
