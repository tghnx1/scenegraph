ALTER TABLE "users"
    DROP CONSTRAINT IF EXISTS "users_role_check";

-- Normalize historical role values after removing the old constraint.
UPDATE "users"
SET "role" = 'artist'
WHERE "role" = 'user';

UPDATE "users"
SET "role" = 'agent'
WHERE "role" = 'contributor';

ALTER TABLE "users"
    ALTER COLUMN "role" SET DEFAULT 'artist';

ALTER TABLE "users"
    ADD CONSTRAINT "users_role_check"
    CHECK ("role" IN ('artist', 'agent', 'admin'));
