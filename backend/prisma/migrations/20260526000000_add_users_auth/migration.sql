CREATE TABLE IF NOT EXISTS "users" (
    "id" BIGSERIAL PRIMARY KEY,
    "username" TEXT NOT NULL UNIQUE,
    "email" TEXT NOT NULL UNIQUE,
    "password_hash" TEXT NOT NULL,
    "created_at" TIMESTAMP(6) WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "role" TEXT NOT NULL
        CHECK ("role" IN ('user', 'contributor', 'admin'))
        DEFAULT 'user',
    "status" TEXT NOT NULL
        CHECK ("status" IN ('pending', 'approved', 'rejected', 'deactivated'))
        DEFAULT 'pending',
    "must_change_password" BOOLEAN NOT NULL DEFAULT FALSE
);


