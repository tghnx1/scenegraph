BEGIN;

-- Replace copied event text and profile names with hashes while retaining stale-input checks.
UPDATE promoter_event_classification c SET input_snapshot = jsonb_build_object(
  'event_id', c.input_snapshot->'event_id',
  'title_hash', encode(sha256(convert_to(c.input_snapshot->>'title', 'UTF8')), 'hex'),
  'description_hash', encode(sha256(convert_to(c.input_snapshot->>'description', 'UTF8')), 'hex'),
  'venue_id', c.input_snapshot->'venue_id',
  'venue_name_hash', CASE WHEN c.input_snapshot->>'venue_name' IS NULL THEN NULL
    ELSE encode(sha256(convert_to(c.input_snapshot->>'venue_name', 'UTF8')), 'hex') END,
  'promoters', COALESCE((
    SELECT jsonb_agg(jsonb_build_object(
      'id', p->'id', 'name_hash', encode(sha256(convert_to(p->>'name', 'UTF8')), 'hex'),
      'identity_id', p->'identity_id') ORDER BY (p->>'id')::bigint)
    FROM jsonb_array_elements(c.input_snapshot->'promoters') p
  ), '[]'::jsonb)
);

CREATE OR REPLACE VIEW promoter_role_eligible_links AS
SELECT ep.event_id,
       COALESCE(canonical.promoter_id, ep.promoter_id) AS promoter_id,
       array_agg(DISTINCT ep.promoter_id ORDER BY ep.promoter_id) AS source_promoter_ids,
       c.config_hash, c.classifier_version
FROM event_promoters ep
JOIN promoter_event_role r ON r.event_id = ep.event_id AND r.promoter_id = ep.promoter_id
JOIN promoter_event_classification c ON c.event_id = ep.event_id AND c.input_hash = r.input_hash
JOIN events e ON e.id = ep.event_id
LEFT JOIN venues v ON v.id = e.venue_id
LEFT JOIN promoter_identity_member im ON im.promoter_id = ep.promoter_id AND im.status = 'confirmed'
LEFT JOIN LATERAL (
    SELECT min(im2.promoter_id) AS promoter_id FROM promoter_identity_member im2
    WHERE im2.identity_id = im.identity_id AND im2.status = 'confirmed'
) canonical ON TRUE
WHERE r.role IN ('organizer', 'both') AND NOT r.needs_review
  AND (r.method = 'manual' OR r.classifier_version = c.classifier_version)
  AND c.input_snapshot = jsonb_build_object(
    'event_id', e.id,
    'title_hash', encode(sha256(convert_to(e.title, 'UTF8')), 'hex'),
    'description_hash', encode(sha256(convert_to(left(coalesce(e.description_text, ''), 12000), 'UTF8')), 'hex'),
    'venue_id', e.venue_id,
    'venue_name_hash', CASE WHEN v.name IS NULL THEN NULL ELSE encode(sha256(convert_to(v.name, 'UTF8')), 'hex') END,
    'promoters', COALESCE((
       SELECT jsonb_agg(jsonb_build_object('id', p.id,
                    'name_hash', encode(sha256(convert_to(p.name, 'UTF8')), 'hex'),
                    'identity_id', CASE WHEN member.status = 'confirmed' THEN member.identity_id ELSE NULL END)
                    ORDER BY p.id)
       FROM event_promoters source_ep JOIN promoters p ON p.id = source_ep.promoter_id
       LEFT JOIN promoter_identity_member member ON member.promoter_id = p.id
       WHERE source_ep.event_id = e.id
    ), '[]'::jsonb)
  )
GROUP BY ep.event_id, COALESCE(canonical.promoter_id, ep.promoter_id), c.config_hash, c.classifier_version;

COMMIT;
