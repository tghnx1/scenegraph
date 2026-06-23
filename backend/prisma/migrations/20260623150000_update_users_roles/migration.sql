ALTER TABLE "users"
    DROP CONSTRAINT IF EXISTS "users_role_check";

-- Normalize historical role values after removing the old constraint.
UPDATE "users"
SET "role" = 'user'
WHERE "role" = 'artist';

UPDATE "users"
SET "role" = 'agent'
WHERE "role" = 'contributor';

ALTER TABLE "users"
    ALTER COLUMN "role" SET DEFAULT 'user';

ALTER TABLE "users"
    ADD CONSTRAINT "users_role_check"
    CHECK ("role" IN ('user', 'agent', 'admin'));
