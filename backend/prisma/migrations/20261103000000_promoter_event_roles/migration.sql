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
