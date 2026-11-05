-- Reviews are an audit record and must not be rewritten after enabling the gate.
CREATE FUNCTION reject_promoter_role_review_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'promoter role quality reviews are immutable' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER promoter_role_review_immutable BEFORE UPDATE OR DELETE ON promoter_role_quality_review
  FOR EACH ROW EXECUTE FUNCTION reject_promoter_role_review_mutation();

CREATE TABLE promoter_role_quality_revocation (
    review_id BIGINT PRIMARY KEY REFERENCES promoter_role_quality_review(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER promoter_role_revocation_immutable BEFORE UPDATE OR DELETE ON promoter_role_quality_revocation
  FOR EACH ROW EXECUTE FUNCTION reject_promoter_role_review_mutation();

CREATE FUNCTION guard_promoter_role_revocation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE active_review BIGINT; mode_enabled BOOLEAN;
BEGIN
  EXECUTE format('SELECT enabled, quality_review_id FROM %I.promoter_role_runtime_state WHERE id = 1 FOR UPDATE', TG_TABLE_SCHEMA)
    INTO mode_enabled, active_review;
  IF mode_enabled AND active_review = NEW.review_id THEN
    RAISE EXCEPTION 'disable promoter roles before revoking the active review' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER promoter_role_revocation_guard BEFORE INSERT ON promoter_role_quality_revocation
  FOR EACH ROW EXECUTE FUNCTION guard_promoter_role_revocation();

CREATE OR REPLACE FUNCTION version_promoter_role_mode_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE valid_review BOOLEAN;
BEGIN
  IF NEW.enabled THEN
    EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.promoter_role_quality_review r WHERE r.id = $1 AND r.config_hash = $2 AND r.classifier_version = $3 AND NOT EXISTS (SELECT 1 FROM %I.promoter_role_quality_revocation x WHERE x.review_id = r.id))', TG_TABLE_SCHEMA, TG_TABLE_SCHEMA)
      INTO valid_review USING NEW.quality_review_id, NEW.config_hash, NEW.classifier_version;
    IF NOT valid_review THEN
      RAISE EXCEPTION 'a matching, non-revoked quality review is required to enable promoter roles' USING ERRCODE = '23514';
    END IF;
  END IF;
  IF NEW.enabled IS DISTINCT FROM OLD.enabled
     OR NEW.quality_review_id IS DISTINCT FROM OLD.quality_review_id
     OR NEW.config_hash IS DISTINCT FROM OLD.config_hash
     OR NEW.classifier_version IS DISTINCT FROM OLD.classifier_version THEN
    NEW.revision := OLD.revision + 1;
    NEW.updated_at := now();
  END IF;
  RETURN NEW;
END;
$$;

-- Preserve the guarded singleton; toggling it is the supported control operation.
CREATE FUNCTION reject_promoter_role_state_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'promoter role runtime state cannot be deleted' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER promoter_role_state_no_delete BEFORE DELETE ON promoter_role_runtime_state
  FOR EACH ROW EXECUTE FUNCTION reject_promoter_role_state_delete();
