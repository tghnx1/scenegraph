CREATE TABLE IF NOT EXISTS "import_runs" (
    "id" BIGSERIAL PRIMARY KEY,
    "pipeline_name" TEXT NOT NULL DEFAULT 'full-pipeline',
    "status" TEXT NOT NULL DEFAULT 'running',
    "min_date" DATE,
    "max_date" DATE,
    "events_json" TEXT,
    "import_json" TEXT,
    "event_ids_file" TEXT,
    "artist_ids_file" TEXT,
    "event_count" INTEGER NOT NULL DEFAULT 0,
    "artist_count" INTEGER NOT NULL DEFAULT 0,
    "events_imported" INTEGER NOT NULL DEFAULT 0,
    "artists_imported" INTEGER NOT NULL DEFAULT 0,
    "event_payloads" INTEGER NOT NULL DEFAULT 0,
    "event_tags" INTEGER NOT NULL DEFAULT 0,
    "artist_tags" INTEGER NOT NULL DEFAULT 0,
    "event_embeddings" INTEGER NOT NULL DEFAULT 0,
    "artist_embeddings" INTEGER NOT NULL DEFAULT 0,
    "metadata" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "error" TEXT,
    "started_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMP(6) WITH TIME ZONE,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "import_runs_status_check" CHECK ("status" IN ('running', 'succeeded', 'failed'))
);

CREATE TABLE IF NOT EXISTS "import_run_stages" (
    "id" BIGSERIAL PRIMARY KEY,
    "import_run_id" BIGINT NOT NULL REFERENCES "import_runs"("id") ON DELETE CASCADE,
    "stage_name" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'running',
    "command" TEXT,
    "duration_ms" INTEGER,
    "metadata" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "error" TEXT,
    "started_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMP(6) WITH TIME ZONE,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "import_run_stages_status_check" CHECK ("status" IN ('running', 'succeeded', 'failed'))
);

CREATE INDEX IF NOT EXISTS "import_runs_started_at_idx"
ON "import_runs" ("started_at" DESC);

CREATE INDEX IF NOT EXISTS "import_runs_status_started_at_idx"
ON "import_runs" ("status", "started_at" DESC);

CREATE INDEX IF NOT EXISTS "import_run_stages_run_stage_idx"
ON "import_run_stages" ("import_run_id", "stage_name");

CREATE OR REPLACE VIEW "import_run_latest_summary" AS
SELECT
    r.*,
    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'stage', s.stage_name,
                    'status', s.status,
                    'durationMs', s.duration_ms,
                    'startedAt', s.started_at,
                    'finishedAt', s.finished_at,
                    'error', s.error
                )
                ORDER BY s.id
            )
            FROM import_run_stages s
            WHERE s.import_run_id = r.id
        ),
        '[]'::jsonb
    ) AS stages
FROM import_runs r
ORDER BY r.started_at DESC;
