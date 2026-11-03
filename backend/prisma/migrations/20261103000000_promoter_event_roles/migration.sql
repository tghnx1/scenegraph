-- Derived decisions are separate from RA's event_promoters, which is rebuilt on import.
CREATE TABLE promoter_event_role (
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    promoter_id BIGINT NOT NULL REFERENCES promoters(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('organizer', 'venue', 'both', 'unknown')),
    confidence DOUBLE PRECISION CHECK (confidence BETWEEN 0 AND 1),
    reason_code TEXT NOT NULL,
    evidence TEXT CHECK (length(evidence) <= 1000),
    method TEXT NOT NULL CHECK (method IN ('rule', 'llm', 'manual')),
    classifier_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, promoter_id)
);
CREATE INDEX promoter_event_role_promoter_id_idx ON promoter_event_role(promoter_id);

-- One marker per event, including events where the model found no candidate.
CREATE TABLE promoter_event_classification (
    event_id BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    input_hash TEXT NOT NULL,
    input_snapshot JSONB NOT NULL,
    config_hash TEXT NOT NULL,
    classifier_version TEXT NOT NULL,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE promoter_identity (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE promoter_identity_member (
    promoter_id BIGINT PRIMARY KEY REFERENCES promoters(id) ON DELETE CASCADE,
    identity_id BIGINT NOT NULL REFERENCES promoter_identity(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'confirmed')),
    reason TEXT NOT NULL,
    version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX promoter_identity_member_identity_id_idx ON promoter_identity_member(identity_id);

-- Compare structured source data at read time so stale results cannot leak into recommendations.
CREATE VIEW promoter_role_eligible_links AS
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
    'event_id', e.id, 'title', e.title, 'description', left(coalesce(e.description_text, ''), 12000),
    'venue_id', e.venue_id, 'venue_name', v.name,
    'promoters', COALESCE((
       SELECT jsonb_agg(jsonb_build_object('id', p.id, 'name', p.name,
                    'identity_id', CASE WHEN member.status = 'confirmed' THEN member.identity_id ELSE NULL END)
                    ORDER BY p.id)
       FROM event_promoters source_ep JOIN promoters p ON p.id = source_ep.promoter_id
       LEFT JOIN promoter_identity_member member ON member.promoter_id = p.id
       WHERE source_ep.event_id = e.id
    ), '[]'::jsonb)
  )
GROUP BY ep.event_id, COALESCE(canonical.promoter_id, ep.promoter_id), c.config_hash, c.classifier_version;

CREATE TABLE event_organizer_candidate (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    evidence TEXT NOT NULL CHECK (length(evidence) <= 1000),
    confidence DOUBLE PRECISION CHECK (confidence BETWEEN 0 AND 1),
    classifier_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'matched', 'rejected')),
    promoter_id BIGINT REFERENCES promoters(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, normalized_name, input_hash, classifier_version),
    CHECK (status <> 'matched' OR promoter_id IS NOT NULL)
);

CREATE TABLE promoter_role_backfill_run (
    id BIGSERIAL PRIMARY KEY,
    scope JSONB NOT NULL,
    classifier_version TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'paused', 'failed', 'succeeded')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE promoter_role_backfill_item (
    run_id BIGINT NOT NULL REFERENCES promoter_role_backfill_run(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    input_hash TEXT,
    error_code TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, event_id)
);
