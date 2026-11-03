CREATE TABLE promoter_role_runtime_state (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    revision BIGINT NOT NULL DEFAULT 0 CHECK (revision >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO promoter_role_runtime_state (id) VALUES (1);

CREATE FUNCTION version_promoter_role_mode_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.enabled IS DISTINCT FROM OLD.enabled THEN
    NEW.revision := OLD.revision + 1;
    NEW.updated_at := now();
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER promoter_role_mode_revision BEFORE UPDATE OF enabled ON promoter_role_runtime_state
  FOR EACH ROW EXECUTE FUNCTION version_promoter_role_mode_change();

-- The source table's schema is always used, even if a session creates temp tables.
CREATE FUNCTION bump_promoter_role_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE format('UPDATE %I.promoter_role_runtime_state SET revision = revision + 1, updated_at = now() WHERE id = 1 AND enabled', TG_TABLE_SCHEMA);
  RETURN NULL;
END;
$$;

CREATE TRIGGER promoter_roles_revision AFTER INSERT OR UPDATE OR DELETE ON promoter_event_role
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();
CREATE TRIGGER promoter_classification_revision AFTER INSERT OR UPDATE OR DELETE ON promoter_event_classification
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();
CREATE TRIGGER promoter_identity_revision AFTER INSERT OR UPDATE OR DELETE ON promoter_identity_member
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();
CREATE TRIGGER promoter_link_revision AFTER INSERT OR UPDATE OR DELETE ON event_promoters
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();
CREATE TRIGGER promoter_event_revision AFTER UPDATE OF title, description_text, venue_id ON events
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();
CREATE TRIGGER promoter_name_revision AFTER UPDATE OF name ON promoters
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();
CREATE TRIGGER promoter_venue_revision AFTER UPDATE OF name ON venues
  FOR EACH STATEMENT EXECUTE FUNCTION bump_promoter_role_revision();
