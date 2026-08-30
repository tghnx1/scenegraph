CREATE TABLE IF NOT EXISTS "coverage_runs" (
    "id" BIGSERIAL PRIMARY KEY,
    "min_date" DATE NOT NULL,
    "max_date" DATE NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'queued',
    "max_attempts" INTEGER NOT NULL DEFAULT 3,
    "total_missing" INTEGER,
    "worker_id" TEXT,
    "error" TEXT,
    "started_at" TIMESTAMP(6) WITH TIME ZONE,
    "completed_at" TIMESTAMP(6) WITH TIME ZONE,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "coverage_runs_date_order_check" CHECK ("min_date" <= "max_date"),
    CONSTRAINT "coverage_runs_status_check" CHECK (
        "status" IN ('queued', 'running', 'succeeded', 'failed')
    ),
    CONSTRAINT "coverage_runs_max_attempts_check" CHECK (
        "max_attempts" BETWEEN 1 AND 5
    )
);

CREATE TABLE IF NOT EXISTS "coverage_run_dates" (
    "id" BIGSERIAL PRIMARY KEY,
    "coverage_run_id" BIGINT NOT NULL REFERENCES "coverage_runs"("id") ON DELETE CASCADE,
    "coverage_date" DATE NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "initial_missing_count" INTEGER,
    "final_missing_count" INTEGER,
    "audit_status" TEXT,
    "backfill_status" TEXT NOT NULL DEFAULT 'pending',
    "backfill_attempt_count" INTEGER NOT NULL DEFAULT 0,
    "verify_status" TEXT NOT NULL DEFAULT 'pending',
    "verify_attempt_count" INTEGER NOT NULL DEFAULT 0,
    "initial_audit" JSONB,
    "final_audit" JSONB,
    "error" TEXT,
    "started_at" TIMESTAMP(6) WITH TIME ZONE,
    "completed_at" TIMESTAMP(6) WITH TIME ZONE,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "coverage_run_dates_status_check" CHECK (
        "status" IN ('pending', 'audited', 'repairing', 'complete', 'failed')
    ),
    CONSTRAINT "coverage_run_dates_backfill_status_check" CHECK (
        "backfill_status" IN ('pending', 'running', 'succeeded', 'failed', 'skipped')
    ),
    CONSTRAINT "coverage_run_dates_verify_status_check" CHECK (
        "verify_status" IN ('pending', 'running', 'succeeded', 'failed', 'skipped')
    ),
    CONSTRAINT "coverage_run_dates_attempts_check" CHECK (
        "backfill_attempt_count" >= 0 AND "verify_attempt_count" >= 0
    ),
    CONSTRAINT "coverage_run_dates_run_date_unique" UNIQUE ("coverage_run_id", "coverage_date")
);

CREATE INDEX IF NOT EXISTS "coverage_runs_status_created_at_idx"
ON "coverage_runs" ("status", "created_at");

CREATE INDEX IF NOT EXISTS "coverage_runs_range_created_at_idx"
ON "coverage_runs" ("min_date", "max_date", "created_at" DESC);

CREATE UNIQUE INDEX IF NOT EXISTS "coverage_runs_active_range_unique_idx"
ON "coverage_runs" ("min_date", "max_date")
WHERE "status" IN ('queued', 'running');

CREATE INDEX IF NOT EXISTS "coverage_run_dates_run_status_idx"
ON "coverage_run_dates" ("coverage_run_id", "status");
