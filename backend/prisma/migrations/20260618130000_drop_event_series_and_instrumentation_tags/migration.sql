DELETE FROM "event_extracted_tags"
WHERE "tag_type" IN ('format', 'series', 'instrumentation');

UPDATE "event_tag_extraction_runs" r
SET "tag_count" = tc.tag_count,
    "updated_at" = CURRENT_TIMESTAMP
FROM (
    SELECT
        r2."event_id",
        r2."source",
        r2."extractor",
        COUNT(t."id") AS tag_count
    FROM "event_tag_extraction_runs" r2
    LEFT JOIN "event_extracted_tags" t
      ON t."event_id" = r2."event_id"
     AND t."source" = r2."source"
     AND t."extractor" = r2."extractor"
    GROUP BY r2."event_id", r2."source", r2."extractor"
) tc
WHERE r."event_id" = tc."event_id"
  AND r."source" = tc."source"
  AND r."extractor" = tc."extractor";

ALTER TABLE "event_extracted_tags"
    DROP CONSTRAINT IF EXISTS "event_extracted_tags_type_check";

ALTER TABLE "event_extracted_tags"
    ADD CONSTRAINT "event_extracted_tags_type_check"
    CHECK ("tag_type" IN ('style', 'theme', 'mood'));
