DROP TRIGGER IF EXISTS "scenegraph_dashboard_refresh_notify"
ON artist_claims;

CREATE TRIGGER "scenegraph_dashboard_refresh_notify"
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE
ON artist_claims
FOR EACH STATEMENT
EXECUTE FUNCTION "scenegraph_notify_dashboard_refresh"();

DROP TRIGGER IF EXISTS "scenegraph_dashboard_refresh_notify"
ON activity_log;

CREATE TRIGGER "scenegraph_dashboard_refresh_notify"
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE
ON activity_log
FOR EACH STATEMENT
EXECUTE FUNCTION "scenegraph_notify_dashboard_refresh"();
