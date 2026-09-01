ALTER TABLE "coverage_reconciliations"
ADD COLUMN IF NOT EXISTS "source_quarantine_ttl_days" INTEGER NOT NULL DEFAULT 7;

ALTER TABLE "coverage_reconciliations"
ADD CONSTRAINT "coverage_reconciliations_source_quarantine_ttl_check"
CHECK ("source_quarantine_ttl_days" BETWEEN 1 AND 365);
