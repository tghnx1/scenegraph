ALTER TABLE "coverage_reconciliations"
ADD COLUMN IF NOT EXISTS "refresh_all_future" BOOLEAN NOT NULL DEFAULT TRUE;
