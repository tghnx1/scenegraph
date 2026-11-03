ALTER TABLE promoter_role_runtime_state ADD COLUMN audience TEXT NOT NULL DEFAULT 'allowlist'
  CHECK (audience IN ('allowlist', 'all'));

CREATE TABLE promoter_role_allowlist (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER promoter_allowlist_revision AFTER INSERT OR UPDATE OR DELETE ON promoter_role_allowlist
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();

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
     OR NEW.classifier_version IS DISTINCT FROM OLD.classifier_version
     OR NEW.audience IS DISTINCT FROM OLD.audience THEN
    NEW.revision := OLD.revision + 1;
    NEW.updated_at := now();
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER promoter_role_mode_revision ON promoter_role_runtime_state;
CREATE TRIGGER promoter_role_mode_revision
  BEFORE UPDATE OF enabled, quality_review_id, config_hash, classifier_version, audience ON promoter_role_runtime_state
  FOR EACH ROW EXECUTE FUNCTION version_promoter_role_mode_change();
