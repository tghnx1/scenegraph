CREATE OR REPLACE VIEW "event_extracted_genres" AS
SELECT
    id,
    event_id,
    tag_value AS extracted_genre,
    source,
    confidence,
    extractor,
    evidence,
    created_at,
    updated_at
FROM "event_extracted_tags"
WHERE tag_type = 'style'
  AND extractor LIKE 'llm_event_tags_v3:%';
