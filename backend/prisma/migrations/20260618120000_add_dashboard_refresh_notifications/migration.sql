CREATE OR REPLACE FUNCTION "scenegraph_notify_dashboard_refresh"()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM pg_notify(
        'scenegraph_dashboard_refresh',
        json_build_object(
            'type', 'dashboard_refresh_required',
            'reason', 'database_changed',
            'table', TG_TABLE_NAME,
            'operation', TG_OP,
            'changedAt', transaction_timestamp()
        )::text
    );

    RETURN NULL;
END;
$$;

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'artists',
        'venues',
        'genres',
        'promoters',
        'events',
        'event_artists',
        'event_genres',
        'event_promoters',
        'event_images',
        'event_source_payloads',
        'entity_embeddings',
        'artist_extracted_tags',
        'artist_tag_extraction_runs',
        'event_extracted_tags',
        'event_tag_extraction_runs',
        'users'
        'activity_log'
        'artist_claims'
    ]
    LOOP
        IF to_regclass(format('public.%I', table_name)) IS NOT NULL THEN
            EXECUTE format(
                'DROP TRIGGER IF EXISTS "scenegraph_dashboard_refresh_notify" ON %I',
                table_name
            );
            EXECUTE format(
                'CREATE TRIGGER "scenegraph_dashboard_refresh_notify" ' ||
                'AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON %I ' ||
                'FOR EACH STATEMENT EXECUTE FUNCTION "scenegraph_notify_dashboard_refresh"()',
                table_name
            );
        END IF;
    END LOOP;
END;
$$;
