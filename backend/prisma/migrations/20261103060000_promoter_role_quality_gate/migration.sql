CREATE TABLE promoter_role_quality_review (
    id BIGSERIAL PRIMARY KEY,
    config_hash TEXT NOT NULL,
    classifier_version TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    true_positive INTEGER NOT NULL CHECK (true_positive >= 0),
    true_negative INTEGER NOT NULL CHECK (true_negative >= 0),
    false_positive INTEGER NOT NULL CHECK (false_positive >= 0),
    false_negative INTEGER NOT NULL CHECK (false_negative >= 0),
    unknown_count INTEGER NOT NULL CHECK (unknown_count >= 0),
    representative BOOLEAN NOT NULL CHECK (representative),
    reviewer TEXT NOT NULL CHECK (length(reviewer) BETWEEN 1 AND 200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (true_positive + false_positive > 0 AND true_positive + false_negative > 0),
    CHECK (true_negative + false_positive > 0),
    CHECK (true_positive::bigint * 5 >= (true_positive::bigint + false_positive) * 4),
    CHECK (true_positive::bigint * 5 >= (true_positive::bigint + false_negative) * 4)
);
CREATE INDEX promoter_role_quality_review_config_idx
  ON promoter_role_quality_review(config_hash, classifier_version, created_at);

ALTER TABLE promoter_role_runtime_state
  ADD COLUMN quality_review_id BIGINT REFERENCES promoter_role_quality_review(id) ON DELETE RESTRICT,
  ADD COLUMN config_hash TEXT,
  ADD COLUMN classifier_version TEXT;

CREATE OR REPLACE FUNCTION version_promoter_role_mode_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE valid_review BOOLEAN;
BEGIN
  IF NEW.enabled THEN
    EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.promoter_role_quality_review WHERE id = $1 AND config_hash = $2 AND classifier_version = $3)', TG_TABLE_SCHEMA)
      INTO valid_review USING NEW.quality_review_id, NEW.config_hash, NEW.classifier_version;
    IF NOT valid_review THEN
      RAISE EXCEPTION 'a matching quality review is required to enable promoter roles' USING ERRCODE = '23514';
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
DROP TRIGGER promoter_role_mode_revision ON promoter_role_runtime_state;
CREATE TRIGGER promoter_role_mode_revision
  BEFORE UPDATE OF enabled, quality_review_id, config_hash, classifier_version ON promoter_role_runtime_state
  FOR EACH ROW EXECUTE FUNCTION version_promoter_role_mode_change();
