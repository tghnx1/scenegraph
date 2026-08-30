CREATE TABLE IF NOT EXISTS "coverage_reconciliations" (
    "id" BIGSERIAL PRIMARY KEY,
    "requested_min_date" DATE NOT NULL,
    "requested_max_date" TEXT NOT NULL,
    "resolved_max_date" DATE,
    "future_horizon_days" INTEGER NOT NULL DEFAULT 365,
    "audit_chunk_days" INTEGER NOT NULL DEFAULT 31,
    "pipeline_chunk_days" INTEGER NOT NULL DEFAULT 7,
    "max_attempts" INTEGER NOT NULL DEFAULT 3,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "phase" TEXT NOT NULL DEFAULT 'pending',
    "current_min_date" DATE,
    "current_max_date" DATE,
    "initial_missing" INTEGER,
    "final_missing" INTEGER,
    "worker_id" TEXT,
    "error" TEXT,
    "started_at" TIMESTAMP(6) WITH TIME ZONE,
    "completed_at" TIMESTAMP(6) WITH TIME ZONE,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "coverage_reconciliations_requested_max_check" CHECK (
        "requested_max_date" = 'auto'
        OR "requested_max_date" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
    ),
    CONSTRAINT "coverage_reconciliations_status_check" CHECK (
        "status" IN ('queued', 'running', 'succeeded', 'failed', 'future_horizon_exhausted')
    ),
    CONSTRAINT "coverage_reconciliations_bounds_check" CHECK (
        "future_horizon_days" BETWEEN 1 AND 3660
        AND "audit_chunk_days" BETWEEN 1 AND 31
        AND "pipeline_chunk_days" BETWEEN 1 AND 7
        AND "max_attempts" BETWEEN 1 AND 5
    )
);

CREATE TABLE IF NOT EXISTS "coverage_reconciliation_dates" (
    "id" BIGSERIAL PRIMARY KEY,
    "reconciliation_id" BIGINT NOT NULL REFERENCES "coverage_reconciliations"("id") ON DELETE CASCADE,
    "coverage_date" DATE NOT NULL,
    "period" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "initial_audit_status" TEXT,
    "initial_missing_count" INTEGER,
    "pipeline_status" TEXT NOT NULL DEFAULT 'pending',
    "pipeline_attempt_count" INTEGER NOT NULL DEFAULT 0,
    "final_audit_status" TEXT,
    "final_missing_count" INTEGER,
    "initial_audit" JSONB,
    "final_audit" JSONB,
    "error" TEXT,
    "started_at" TIMESTAMP(6) WITH TIME ZONE,
    "completed_at" TIMESTAMP(6) WITH TIME ZONE,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "coverage_reconciliation_dates_period_check" CHECK ("period" IN ('historical', 'future')),
    CONSTRAINT "coverage_reconciliation_dates_status_check" CHECK (
        "status" IN ('pending', 'audited', 'processing', 'complete', 'failed')
    ),
    CONSTRAINT "coverage_reconciliation_dates_pipeline_status_check" CHECK (
        "pipeline_status" IN ('pending', 'running', 'succeeded', 'failed', 'skipped')
    ),
    CONSTRAINT "coverage_reconciliation_dates_attempts_check" CHECK ("pipeline_attempt_count" >= 0),
    CONSTRAINT "coverage_reconciliation_dates_run_date_unique" UNIQUE ("reconciliation_id", "coverage_date")
);

CREATE INDEX IF NOT EXISTS "coverage_reconciliations_status_created_idx"
ON "coverage_reconciliations" ("status", "created_at");

CREATE UNIQUE INDEX IF NOT EXISTS "coverage_reconciliations_active_request_idx"
ON "coverage_reconciliations" ("requested_min_date", "requested_max_date")
WHERE "status" IN ('queued', 'running');

CREATE INDEX IF NOT EXISTS "coverage_reconciliation_dates_run_status_idx"
ON "coverage_reconciliation_dates" ("reconciliation_id", "status", "coverage_date");
