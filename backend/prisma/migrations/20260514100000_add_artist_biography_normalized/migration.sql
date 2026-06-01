ALTER TABLE "artists"
ADD COLUMN IF NOT EXISTS "biography_normalized" TEXT;
