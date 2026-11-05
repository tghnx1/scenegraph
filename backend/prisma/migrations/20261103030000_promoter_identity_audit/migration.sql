CREATE TABLE promoter_identity_audit (
    id BIGSERIAL PRIMARY KEY,
    promoter_id BIGINT NOT NULL REFERENCES promoters(id) ON DELETE RESTRICT,
    identity_id BIGINT NOT NULL REFERENCES promoter_identity(id) ON DELETE RESTRICT,
    previous_status TEXT CHECK (previous_status IN ('proposed', 'confirmed')),
    new_status TEXT NOT NULL CHECK (new_status IN ('proposed', 'confirmed')),
    reason TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
    version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX promoter_identity_audit_promoter_idx ON promoter_identity_audit(promoter_id, created_at);
